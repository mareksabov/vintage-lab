#!/usr/bin/env bash
# state-sync.sh — copy machine state to/from a shared (Samba) location.
#
#   restore : pull state FROM the share into this repo (run this BEFORE you start
#             the machine on this computer)
#   store   : push state FROM this repo TO the share (run this AFTER you shut the
#             machine down)
#
# Config: utils/state-sync.conf  (SAMBA_DIR, MACHINES, SYNC_DIRS, SYNC_EXCLUDES)
#
# WARNING: only run this while the emulator is NOT running, and only run a given
# machine on ONE computer at a time — shared state can corrupt if two machines
# write it. Both commands mirror with --delete, so the destination becomes an
# exact copy of the source (extra files on the destination are removed).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="${STATE_SYNC_CONFIG:-$SCRIPT_DIR/state-sync.conf}"

die() { echo "error: $*" >&2; exit 1; }

usage() {
  echo "usage: $(basename "$0") {store|restore} [machine] [-y]"
  echo "  restore   pull state from the share to this repo (before running)"
  echo "  store     push state from this repo to the share (after running)"
  echo "  machine   sync only this machine (must be one of MACHINES);"
  echo "            omit to sync every machine in MACHINES"
  echo "  -y        do not ask for confirmation"
  exit 2
}

command -v rsync >/dev/null 2>&1 || die "rsync is required but was not found on PATH"
[ -f "$CONFIG" ] || die "config not found: $CONFIG (copy state-sync.conf.example to state-sync.conf and edit it)"
# shellcheck disable=SC1090
. "$CONFIG"

: "${SAMBA_DIR:?set SAMBA_DIR in $CONFIG}"
: "${MACHINES:?set MACHINES in $CONFIG}"
SYNC_DIRS="${SYNC_DIRS:-state}"
# Names never synced. `state/roms` is a symlink into the Nix store created by the
# driver (it re-links itself on every run), so it is local-only by nature — and a
# CIFS share cannot store a symlink at all, which fails the whole transfer.
# Excluded names are also protected from --delete, so restore leaves them alone.
SYNC_EXCLUDES="${SYNC_EXCLUDES:-roms}"

EXCLUDE_ARGS=()
for x in $SYNC_EXCLUDES; do
  EXCLUDE_ARGS+=("--exclude=$x")
done

[ $# -ge 1 ] || usage
ACTION="$1"; shift

# Remaining args, in any order: an optional single machine name (to sync just
# that one instead of all of MACHINES) and the optional -y flag.
ASSUME_YES=0
ONLY_MACHINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    -y) ASSUME_YES=1 ;;
    -*) usage ;;
    *)  [ -n "$ONLY_MACHINE" ] && die "specify at most one machine (got '$ONLY_MACHINE' and '$1')"
        ONLY_MACHINE="$1" ;;
  esac
  shift
done

# Resolve which machines to sync: the requested one, or all configured ones.
SYNC_MACHINES="$MACHINES"
if [ -n "$ONLY_MACHINE" ]; then
  found=0
  for m in $MACHINES; do [ "$m" = "$ONLY_MACHINE" ] && found=1; done
  [ "$found" = 1 ] || die "machine '$ONLY_MACHINE' is not in MACHINES ($MACHINES) — add it in $CONFIG or pick one of those"
  SYNC_MACHINES="$ONLY_MACHINE"
fi

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  printf "%s [y/N] " "$1"
  read -r ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ]
}

# Map a local machine subdir to its group folder on the share:
#   state -> states/<machine>    media -> media/<machine>
remote_dir() {
  # $1 = machine, $2 = sync dir
  local group
  case "$2" in
    state) group="states" ;;
    *)     group="$2" ;;
  esac
  echo "$SAMBA_DIR/$group/$1"
}

SYNCED=0

sync_one() {
  # $1 = source dir, $2 = destination dir, $3 = human label
  local src="$1" dst="$2" label="$3"
  if [ ! -d "$src" ]; then
    echo "  skip: source missing ($src)"
    return 0
  fi
  mkdir -p "$dst"

  # Progress by polling the destination size against the source total. Works
  # with any rsync (macOS openrsync ignores --progress; this does not).
  local total_kb done_kb pct rc=0
  total_kb=$(du -sk "$src" 2>/dev/null | awk '{print $1}') || true
  total_kb=${total_kb:-0}

  rsync -a --delete ${EXCLUDE_ARGS[@]+"${EXCLUDE_ARGS[@]}"} "$src/" "$dst/" &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    done_kb=$(du -sk "$dst" 2>/dev/null | awk '{print $1}') || true
    done_kb=${done_kb:-0}
    if [ "$total_kb" -gt 0 ]; then
      pct=$(( done_kb * 100 / total_kb ))
      [ "$pct" -gt 100 ] && pct=100
      printf '\r  %s: %d/%d MB (%d%%)      ' "$label" "$((done_kb/1024))" "$((total_kb/1024))" "$pct"
    else
      printf '\r  %s: %d MB      ' "$label" "$((done_kb/1024))"
    fi
    sleep 2
  done
  wait "$pid" || rc=$?

  if [ "$rc" -eq 0 ]; then
    SYNCED=$((SYNCED + 1))
    printf '\r  ok:   %s (%d MB)                         \n' "$label" "$((total_kb/1024))"
  else
    printf '\r  FAIL: %s (rsync exit %d)                 \n' "$label" "$rc"
  fi
  return "$rc"
}

# The share must already be mounted. We deliberately do NOT create SAMBA_DIR:
# on an unmounted mount point that would silently write to the local disk
# instead of the share.
require_share() {
  [ -d "$SAMBA_DIR" ] || die "cannot reach $SAMBA_DIR — is the share mounted on this computer?
       SAMBA_DIR is per-computer; check it in $CONFIG
       (macOS mounts under /Volumes/<share>, Linux wherever you mounted the CIFS share)"
}

case "$ACTION" in
  store)
    require_share
    confirm "Push local state -> $SAMBA_DIR (overwrites the share). Continue?" || exit 1
    for m in $SYNC_MACHINES; do
      echo "$m:"
      for d in $SYNC_DIRS; do
        sync_one "$REPO_ROOT/machines/$m/$d" "$(remote_dir "$m" "$d")" "$m/$d  ->  share"
      done
    done
    ;;
  restore)
    require_share
    confirm "Pull state from $SAMBA_DIR -> local (overwrites local). Continue?" || exit 1
    for m in $SYNC_MACHINES; do
      echo "$m:"
      for d in $SYNC_DIRS; do
        sync_one "$(remote_dir "$m" "$d")" "$REPO_ROOT/machines/$m/$d" "share  ->  $m/$d"
      done
    done
    [ "$SYNCED" -gt 0 ] \
      || die "the share is reachable but holds nothing for: $SYNC_MACHINES — run 'store' on the computer that has the state"
    ;;
  *)
    usage
    ;;
esac

echo "done."
