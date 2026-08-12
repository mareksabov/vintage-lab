# Vintage — Commodore 64 via VICE (Second Driver) — Design

**Date:** 2026-08-12
**Status:** Approved design, ready for implementation planning

## Summary

Add a second emulator to `vintage`: a Commodore 64 running under **VICE**
(`x64sc`). The C64 is not a goal in itself — it is the first real test of the
driver abstraction. The launcher was built around a single emulator (86Box) and,
despite the "adding an emulator is a new driver" intent in the original design,
the dispatch is still hardcoded to `86box` in three places. Introducing a second,
genuinely different emulator forces those seams open and proves (or disproves)
that the abstraction holds across two platforms.

A bare C64 is an ideal test target because it exposes deliberate contrasts with
the OptiPlex/86Box machine:

- **No external ROMs.** VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs, so there
  is no copyrighted ROM flake input and no `roms` symlink — proving the core does
  not assume every emulator needs externally-wired ROMs.
- **No user media required.** A bare C64 boots to the `READY.` BASIC prompt from
  bundled ROMs alone. Unlike the OptiPlex (which needs install ISOs), the C64
  definition of done requires zero user-provided, copyrighted files.
- **Different media mechanism.** 86Box has no stable CLI for media, so its driver
  injects media by editing the native `.cfg`. VICE has first-class CLI media
  flags (`-8 disk.d64`), so its driver attaches media via `argv`. The same
  declarative `[[media]]` contract in `machine.toml` maps to a different
  mechanism per driver — exactly the seam the abstraction must absorb.

## Goals

- **Open the dispatch seam.** Replace the hardcoded `if machine.emulator != "86box"`
  branch with a real driver registry, so a second (and later third) emulator plugs
  in without touching core control flow.
- **Add a working VICE driver** that boots a faithful C64 and can attach a disk
  image on request.
- **Ship a `c64` machine** that runs out of the box (`vintage run c64` → `READY.`)
  with no user-provided media.
- **Preserve existing behavior.** The OptiPlex/86Box path and its tests keep
  working; the refactor is behavior-preserving for 86Box.
- **Public repository.** No copyrighted ROMs or media enter git; documentation and
  comments in English.

## Non-Goals (for now)

- Tapes, cartridges, drive 9, and PRG autostart — the driver models drive 8 only;
  the slot map is extensible but we do not build unused slots (YAGNI).
- A universal hardware schema across emulators — hardware detail stays in each
  emulator's native config, as before.
- Live media swapping / `vintage insert` — still a future layer.
- Web frontend / remote access — unchanged future layers.

## Emulator Choice

**VICE**, binary **`x64sc`** (cycle-accurate C64; the plain `x64` is faster but
less accurate — accuracy fits the "faithful replica" ethos). VICE is the standard,
actively maintained C64 emulator, is packaged in nixpkgs, and bundles the C64 ROM
set, so it needs no separate ROM input.

## Architecture

### The three hardcoded seams to open

1. `src/vintage/run.py` — `cmd_run` hardcodes `if machine.emulator != "86box"`,
   imports `emu86box` directly, and handles 86Box-specific `VINTAGE_ROMS_86BOX` /
   `VINTAGE_86BOX_BIN` env in the core.
2. `src/vintage/cli.py` — `_TEMPLATE_TOML` and `cmd_new` hardcode `emulator = "86box"`
   and write `86box.cfg`.
3. `flake.nix` — wires only the 86Box binary and ROM input.

### Driver registry (core change)

Each driver exposes a single entry point:

```python
def run(machine: Machine, *, env: Mapping[str, str],
        runner: Callable[[list[str]], int]) -> int
```

The driver owns its full lifecycle: prepare the VM dir, wire ROMs/media as it sees
fit, validate its own environment variables, build argv, and invoke `runner`.
Emulator-specific environment handling (e.g. `VINTAGE_ROMS_86BOX`) moves **out of
the core and into the driver**, because it is not a universal concept.

`run.py` becomes a thin dispatcher over a registry:

```python
DRIVERS = {"86box": emu86box.run, "vice": vice.run}
```

`cmd_run` loads the machine, looks up `DRIVERS[machine.emulator]`, and calls it.
An unknown emulator prints an error naming the emulator and the supported set, and
returns a non-zero code.

The existing 86Box helper functions (`prepare_vmdir`, `link_roms`, `apply_media`,
`build_argv`) are unchanged in behavior; they are wrapped by a new
`emu86box.run(...)` that also performs the ROM/bin env checks previously living in
`run.py`.

### VICE driver (`src/vintage/drivers/vice.py`)

- **Binary:** from `VINTAGE_VICE_BIN`, default `x64sc`.
- **Native config (parity with 86Box):** `prepare_vmdir` copies the machine's
  `vicerc` template into `state/` on first run and never overwrites it afterwards,
  so user edits persist — mirroring `emu86box.prepare_vmdir`. VICE launches with
  `-config <abs path to state/vicerc>`.
- **Media as argv:** each `[[media]]` entry maps to VICE CLI flags rather than
  config edits. Slot map (extensible):

  | Slot     | VICE flag |
  |----------|-----------|
  | `drive8` | `-8 <abs path>` |

  Paths are resolved to absolute (VICE resolves relative paths against its own CWD,
  not the machine dir). A missing media file emits a stderr warning but still
  passes the flag — matching `emu86box.apply_media` behavior.
- **ROMs:** none wired. VICE finds its bundled ROMs via its own data directory
  (compiled/wrapped in by nixpkgs). No flake input, no symlink.
- **argv shape:** `[vice_bin, "-config", <abs vicerc>, <media flags...>]`.

### `c64` machine folder

```
machines/c64/
├── machine.toml   # emulator = "vice", config = "vicerc", NO [[media]] (boots to READY.)
├── vicerc         # bare C64 native config (versioned)
├── media/.gitkeep # gitignored contents (user .d64 files)
└── state/.gitkeep # gitignored contents (working vicerc + any disk write-back)
```

`machine.toml`:

```toml
name     = "Commodore 64"
emulator = "vice"
config   = "vicerc"

# Optional: attach a disk in drive 8 (user-provided, gitignored):
# [[media]]
# slot = "drive8"
# file = "media/demo.d64"
```

The committed machine has no `[[media]]`, so `vintage run c64` boots straight to
`READY.` with zero user files.

### `vintage new --emulator`

`cmd_new` gains `--emulator {86box,vice}` (default `86box`, preserving current
behavior). A small per-emulator map provides the `machine.toml` template and the
native config filename (`86box.cfg` vs `vicerc`) plus a minimal starter config
body. This removes the last hardcoded `86box` assumption from the CLI.

### Flake wiring

Add `pkgs.vice` and extend the `vintage` wrapper:

```
--set VINTAGE_VICE_BIN ${pkgs.vice}/bin/x64sc
```

No ROM input is added for VICE.

## Definition of Done

- `vintage run c64` launches `x64sc` and boots to the C64 BASIC `READY.` prompt
  with no user-provided media.
- Attaching a disk works: a `[[media]] slot = "drive8"` entry makes the driver
  pass `-8 <abs .d64>` and the disk is available in the running C64.
- `nix run .#vintage -- run c64` works through the flake on the author's machine.
- The OptiPlex/86Box path is unchanged and its tests pass.
- No copyrighted ROMs or media in git.

## Testing

- **Registry dispatch (`tests/test_run.py`):** unknown emulator → error naming the
  supported set; `vice` dispatches to the VICE driver (fake runner captures argv);
  86Box still dispatches and links ROMs as before. The existing
  `test_run_rejects_non_86box` is rewritten to the new contract (vice is now
  accepted, not rejected).
- **VICE driver (`tests/test_driver_vice.py`), golden-style pure logic:**
  - `prepare_vmdir` copies the `vicerc` template once and does not overwrite user
    edits on a second call.
  - `build_argv` includes `-config <abs vicerc>` and, for a `drive8` media entry,
    `-8 <resolved absolute path>`.
  - A missing media file emits a stderr warning but the flag is still emitted.
  - An unknown slot raises `ValueError`.
- **86Box driver tests** remain green (behavior-preserving refactor).

The running emulator itself is not unit-tested (as before); only launcher and
config/argv generation logic is.

## Risks / Open Items (verify at implementation time)

1. **VICE on `aarch64-darwin` via nixpkgs.** SDL-based build; confirm `pkgs.vice`
   is available (ideally from the binary cache) and that `x64sc` runs on
   `aarch64-darwin`. This is the primary technical risk — mirror the 86Box spike:
   a dry-run/build check before committing to the driver.
2. **Binary name and ROM discovery.** Confirm the C64 binary is `x64sc` in the nix
   package and that it locates its bundled ROMs without an explicit `-directory`
   (nixpkgs typically wraps this in). If not, wire the data dir in the driver/flake.
3. **`-config` path semantics.** Confirm VICE accepts an absolute `-config` path
   and reads/writes that file; the driver always passes an absolute path.
4. **Media write-back.** VICE writes back to an attached, non-read-only `.d64`.
   Since attached disks live under the user's (gitignored) `media/`, write-back
   stays out of git naturally; note this behavior but do not build persistence
   machinery for it now.
