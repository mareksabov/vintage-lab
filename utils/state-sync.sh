#!/usr/bin/env bash
# state-sync.sh — copy machine state to/from a shared (Samba) location.
#
#   restore : pull state FROM the share into this repo (run this BEFORE you start
#             the machine on this computer)
#   store   : push state FROM this repo TO the share (run this AFTER you shut the
#             machine down)
#
# Config: utils/state-sync.conf  (SAMBA_DIR, MACHINES, SYNC_DIRS)
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
  echo "usage: $(basename "$0") {store|restore} [-y]"
  echo "  restore  pull state from the share to this repo (before running)"
  echo "  store    push state from this repo to the share (after running)"
  echo "  -y       do not ask for confirmation"
  exit 2
}

command -v rsync >/dev/null 2>&1 || die "rsync is required but was not found on PATH"
[ -f "$CONFIG" ] || die "config not found: $CONFIG (copy state-sync.conf.example to state-sync.conf and edit it)"
# shellcheck disable=SC1090
. "$CONFIG"

: "${SAMBA_DIR:?set SAMBA_DIR in $CONFIG}"
: "${MACHINES:?set MACHINES in $CONFIG}"
SYNC_DIRS="${SYNC_DIRS:-state}"

[ $# -ge 1 ] || usage
ACTION="$1"; shift
ASSUME_YES=0
[ "${1:-}" = "-y" ] && ASSUME_YES=1

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

sync_one() {
  # $1 = source dir, $2 = destination dir, $3 = human label
  local src="$1" dst="$2" label="$3"
  if [ ! -d "$src" ]; then
    echo "  skip: source missing ($src)"
    return 0
  fi
  mkdir -p "$dst"
  rsync -a --delete "$src/" "$dst/"
  echo "  ok:   $label"
}

case "$ACTION" in
  store)
    confirm "Push local state -> $SAMBA_DIR (overwrites the share). Continue?" || exit 1
    mkdir -p "$SAMBA_DIR" 2>/dev/null \
      || die "cannot reach/create $SAMBA_DIR (is the share mounted and writable?)"
    for m in $MACHINES; do
      echo "$m:"
      for d in $SYNC_DIRS; do
        sync_one "$REPO_ROOT/machines/$m/$d" "$(remote_dir "$m" "$d")" "$m/$d  ->  share"
      done
    done
    ;;
  restore)
    [ -d "$SAMBA_DIR" ] \
      || { echo "nothing on the share yet ($SAMBA_DIR) — run 'store' first"; exit 0; }
    confirm "Pull state from $SAMBA_DIR -> local (overwrites local). Continue?" || exit 1
    for m in $MACHINES; do
      echo "$m:"
      for d in $SYNC_DIRS; do
        sync_one "$(remote_dir "$m" "$d")" "$REPO_ROOT/machines/$m/$d" "share  ->  $m/$d"
      done
    done
    ;;
  *)
    usage
    ;;
esac

echo "done."
