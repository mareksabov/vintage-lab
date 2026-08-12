# Vintage — Commodore VIC-20 via VICE, plus cart/tape/RAM for both Commodore machines — Design

**Date:** 2026-08-12
**Status:** Approved design, ready for implementation planning

## Summary

Add a **Commodore VIC-20** machine running under **VICE** (`xvic`), and while
doing so extend the shared VICE driver so **both** Commodore machines (`c64` and
the new `vic20`) gain **cartridge**, **tape (datasette)**, and **RAM expansion**
support.

The VIC-20 is a second machine on the same driver as the C64. It exposes one new
seam the C64 did not: VICE is a *suite* of emulators and each machine is a
different binary (`x64sc` for the C64, `xvic` for the VIC-20). The existing
driver hardcodes a single binary via `VINTAGE_VICE_BIN`. This design opens that
seam so any VICE machine selects its binary by a declared `model`, without a
new driver per machine.

The cart/tape/RAM work is added to the shared driver (not duplicated), so the
existing `c64` machine benefits at the same time.

## Goals

- **Ship a `vic20` machine** that runs out of the box: `vintage run vic20` boots
  to the VIC-20 BASIC `READY.` prompt with no user-provided media.
- **Select the VICE binary by machine model** (`x64sc` vs `xvic`) from one
  wrapped VICE distribution, so adding further VICE machines (xpet, xplus4, …)
  later needs no flake change.
- **Add cartridge, tape, and autostart media slots** to the shared VICE driver,
  usable by both `c64` and `vic20`.
- **Add a model-aware RAM-expansion knob** in `machine.toml` (VIC-20 memory
  blocks; C64 REU).
- **Preserve existing behavior.** The 86Box path and the C64 boot-to-`READY.`
  path keep working; the C64's existing drive-8 behavior is unchanged.
- **Public repository.** No copyrighted ROMs or media enter git; docs and code
  comments in English.

## Non-Goals (for now)

- A universal hardware schema across emulators — hardware detail stays in each
  emulator's native config, except the small `ram` knob which maps to CLI flags.
- Drive 9, raw non-CRT cartridge ROM formats (`-cartgeneric`/`-cartA`…), and
  cartridge type autodetection — `cart` means a CRT-format image; raw programs
  go through the `autostart` slot.
- A `--model` flag on `vintage new` — the vice starter writes a default `model`;
  users edit it. (YAGNI.)
- Live media swapping / `vintage insert`, web frontend, remote access — unchanged
  future layers.

## Emulator / binary

VICE **`xvic`** for the VIC-20 (the standard, actively maintained VIC-20
emulator; bundles the VIC-20 ROM set, so no separate ROM input — same as the
C64). Both `x64sc` and `xvic` ship in the same VICE distribution already wired in
the flake: `pkgs.vice` on Linux and the official arm64 SDL2 app on macOS both
contain `xvic` alongside `x64sc` in one `bin/` directory.

## Architecture

### Binary selection by model

Today `flake.nix` wires `VINTAGE_VICE_BIN` to a concrete `.../bin/x64sc`, and the
driver reads that single path. Change to wiring the **directory**:

- Flake env: `VINTAGE_VICE_BIN_DIR` = `${pkgs.vice}/bin` (Linux) or
  `${vice-macos}/vice/bin` (aarch64-darwin). Unset on unsupported platforms
  (evaluation stays lazy, as today).
- Driver: `MODEL_BINARIES = {"c64": "x64sc", "vic20": "xvic"}`. It resolves the
  binary name from the machine's `model`, then joins it onto
  `VINTAGE_VICE_BIN_DIR`. When the env var is absent (dev shell / tests), it
  falls back to the bare binary name and relies on `PATH`.

This replaces `VINTAGE_VICE_BIN` (an internal contract with no external users:
read only by the driver, set only by the flake, referenced only in tests). The
alternative — one env var per binary, mirroring `VINTAGE_86BOX_BIN` — was
rejected because a bin directory is more extensible (new VICE machines need no
flake change).

### `machine.toml` — new keys for vice machines

```toml
name     = "Commodore VIC-20"
emulator = "vice"
model    = "vic20"     # NEW: selects the VICE binary and interprets `ram`
config   = "vicerc"
ram      = "24k"       # NEW, optional: RAM expansion (model-aware)
```

The core loader stays emulator-agnostic. `Machine` keeps its known fields
(`id`, `path`, `name`, `emulator`, `config`, `media`) and gains a generic
**`options`** mapping holding every other top-level scalar key from
`machine.toml` (here: `model`, `ram`). Drivers read what they need from
`options`; the 86Box driver ignores it. `options` is excluded from dataclass
comparison/hash (`field(compare=False)`) so `Machine` stays hashable and equality
is unaffected.

When a vice machine omits `model`, the driver defaults to `"c64"` (preserving the
current C64 machine, which has no `model` today, until its file is updated).

### VICE driver changes (`src/vintage/drivers/vice.py`)

**Media slot map (shared across models; these flags are identical in `x64sc`
and `xvic`):**

| Slot        | VICE flag     | Meaning                                    |
|-------------|---------------|--------------------------------------------|
| `drive8`    | `-8`          | disk image in drive 8 (existing)           |
| `tape`      | `-1`          | attach datasette tape image (load by hand) |
| `cart`      | `-cartcrt`    | attach a CRT-format cartridge image        |
| `autostart` | `-autostart`  | attach and auto-run a program/image (.prg…)|

Each `[[media]]` entry maps to `<flag> <abs path>`. Paths resolve to absolute
(VICE resolves relative paths against its own CWD). A missing file emits a stderr
warning but still passes the flag — matching existing behavior. An unknown slot
raises `ValueError` (unchanged).

**RAM knob (model-aware, not a media slot — it is hardware):** read `ram` from
`options`. Translate per model:

- `model = "vic20"`: `ram` ∈ `{3k, 8k, 16k, 24k, all}` → `["-memory", <spec>]`.
- `model = "c64"`: `ram = "reu"` → `["-reu"]` (enable REU at VICE's default size).
- Unknown/unsupported `ram` value for the model → `ValueError` naming the
  accepted set.
- `ram` absent → no flag.

**argv shape:** `[bin, "-config", <abs vicerc>, *ram_flags, *media_flags]`.
`bin` comes from model→binary resolution above. Deterministic order (ram before
media) for golden-style tests.

ROMs: none wired (VICE bundles them), as for the C64.

### `vic20` machine folder

```
machines/vic20/
├── machine.toml   # emulator=vice, model=vic20, config=vicerc, NO [[media]]
├── vicerc         # bare VIC-20 native config (versioned)
├── media/.gitkeep # gitignored contents (user .d64/.crt/.tap/.prg)
└── state/.gitkeep # gitignored contents (working vicerc + write-back)
```

`machine.toml` ships with no `[[media]]` and no `ram`, so `vintage run vic20`
boots straight to `READY.` on a bare (unexpanded) VIC-20. Commented examples show
how to attach a disk / cartridge / tape / autostart program and how to set `ram`.

### `c64` machine update

Add `model = "c64"` to `machines/c64/machine.toml` and a commented `ram = "reu"`
example plus commented `cart`/`tape`/`autostart` media examples. Behavior for the
committed machine is unchanged (still boots to `READY.`).

### CLI (`vintage new --emulator vice`)

The vice starter template writes `model = "c64"` into the scaffolded
`machine.toml` so a freshly-scaffolded vice machine has a valid model. No new
flag. The 86Box template is unchanged.

### Flake wiring

Replace the `VINTAGE_VICE_BIN` wiring with `VINTAGE_VICE_BIN_DIR` pointing at the
VICE `bin` directory (`viceBinDir` computed the same way `viceBin` is today, minus
the trailing `/x64sc`). No ROM input for VICE.

## Definition of Done

- `vintage run vic20` launches `xvic` and boots to the VIC-20 BASIC `READY.`
  prompt with no user-provided media.
- `nix run .#vintage -- run vic20` works through the flake on the author's
  machine (aarch64-darwin).
- Attaching each slot works: `drive8` → `-8`, `tape` → `-1`, `cart` → `-cartcrt`,
  `autostart` → `-autostart`, each with a resolved absolute path.
- `ram = "24k"` on the VIC-20 adds `-memory 24k`; `ram = "reu"` on the C64 adds
  `-reu`.
- The C64 boot-to-`READY.` path and the 86Box path are unchanged; all existing
  tests pass.
- No copyrighted ROMs or media in git.

## Testing

- **VICE driver (`tests/test_driver_vice.py`), golden-style pure logic:**
  - Model → binary: `model="c64"` resolves `x64sc`, `model="vic20"` resolves
    `xvic`; with `VINTAGE_VICE_BIN_DIR` set the path is `<dir>/<binary>`; unset
    falls back to the bare binary name. Missing `model` defaults to `c64`.
  - Media slots: `drive8/-8`, `tape/-1`, `cart/-cartcrt`, `autostart/-autostart`
    each emit `<flag> <resolved abs path>`; a missing file warns on stderr but
    still emits the flag; an unknown slot raises `ValueError`.
  - RAM knob: vic20 `ram="24k"` → `-memory 24k`; c64 `ram="reu"` → `-reu`; an
    unsupported value for the model raises `ValueError`; no `ram` → no flag.
  - `prepare_vmdir` still copies `vicerc` once and never overwrites (unchanged).
- **Machine model (`tests/test_machine.py`):** `options` captures `model`/`ram`
  and excludes the known core keys; a machine with no extra keys has empty
  `options`.
- **Dispatch (`tests/test_run.py`):** `vic20` dispatches to the vice driver;
  86Box dispatch and ROM linking unchanged.
- **86Box driver tests** remain green (untouched).

The running emulator itself is not unit-tested (as before); only launcher and
argv/config generation logic is. Final functional check is a live
`nix run .#vintage -- run vic20` to `READY.`.

## Risks / Open Items (verify at implementation time)

1. **`xvic` present in both VICE distributions.** Confirm `xvic` exists next to
   `x64sc` in `pkgs.vice/bin` (Linux) and in the macOS arm64 SDL2 app bundle. It
   is a standard VICE binary, so expected — verify by listing the bin dir.
2. **VIC-20 `-memory` spec syntax.** Confirm `xvic -memory 24k` (and `3k/8k/16k/
   all`) is accepted by the pinned VICE 3.9. Adjust the accepted-value → flag
   mapping if the syntax differs (e.g. block lists).
3. **`-cartcrt` on `xvic`.** Confirm `xvic` accepts `-cartcrt` for CRT images.
   If VIC-20 CRT handling needs a different flag, keep the `cart` slot but branch
   the flag per model in the slot resolution.
4. **`-config` absolute path & write-back.** Unchanged from the C64 design;
   already validated there.
