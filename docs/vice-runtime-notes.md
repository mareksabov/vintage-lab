# VICE runtime notes

Facts recorded while wiring the C64 machine against VICE on `aarch64-darwin`.

## Binary

The C64 emulator binary is `x64sc` (cycle-accurate). The flake wires
`VINTAGE_VICE_BIN = ${pkgs.vice}/bin/x64sc`.

## ROMs

VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs; `x64sc` locates them via its
own data directory (wrapped in by nixpkgs). No ROM env var or symlink is needed
— in contrast with the 86Box driver which requires a `state/roms` symlink.

## Config / persistence

`x64sc -config <state/vicerc>` reads and writes that file. The launcher copies
the versioned template into the machine's gitignored `state/` on first run, so
runtime tweaks persist there. Media is attached on the command line (`-8
<disk.d64>`), not via the config file.

## Platform availability — KNOWN ISSUE (aarch64-darwin)

`pkgs.vice` in `nixpkgs-unstable` (vice-3.10) declares
`meta.platforms = [ "x86_64-linux" "aarch64-linux" ... ]` — Linux only.
On this host (`aarch64-darwin`) the evaluation fails:

```
error: Refusing to evaluate package 'vice-3.10' …
       because it is not available on the requested hostPlatform:
         hostPlatform.system = "aarch64-darwin"
```

Confirmed by:
- `nix flake check --no-build` → exits with error on `packages.aarch64-darwin.emulatorVice`
- `nix eval --raw .#packages.aarch64-darwin.emulatorVice.outPath` → same error

The flake.nix edit is applied exactly as specified (Task 6 brief):
`emulatorVice = pkgs.vice;` and `--set VINTAGE_VICE_BIN ${emulatorVice}/bin/x64sc \`
are in place for when a Linux build host (or a future darwin-compatible VICE
package) is used.

**Action required by the controller:** decide how to proceed on aarch64-darwin.
Options include:
1. Build VICE from source with `pkgs.vice.override { ... }` bypassing the
   platform guard (risky; SDL2 / X11 deps may not build cleanly on macOS).
2. Use a Linux remote builder / nix build farm for the `emulatorVice` derivation.
3. Source VICE for macOS via Homebrew or a separate flake input, referencing the
   macOS binary and stubbing out the nixpkgs attribute for darwin.
4. Accept that `vintage run c64` is Linux-only for now; guard the driver with a
   platform check and document accordingly.

## What was NOT verified (requires build + runtime)

Because `pkgs.vice` does not evaluate on this host, the following facts from the
spec could NOT be confirmed and remain expected / to be confirmed by the
controller's build + first run on a supported platform:

- ROM discovery actually works at runtime (VICE finds its bundled ROMs through
  the nixpkgs wrapper without any extra flags).
- `x64sc -config state/vicerc` boots to the blue `READY.` BASIC screen.
- Media attachment via `-8 <disk.d64>` loads correctly.
- The `vicerc` template in `machines/c64/vicerc` is accepted without error by
  the version of VICE that nixpkgs ships.

## Verified on aarch64-darwin

- `PYTHONPATH=src pytest -q` → 37 passed (full suite green).
- `flake.nix` evaluates correctly for `packages.aarch64-darwin.emulator86box`
  and `packages.aarch64-darwin.vintage-unwrapped`; only `emulatorVice` is
  blocked by the platform guard.
- The wrapProgram call is syntactically correct and would set `VINTAGE_VICE_BIN`
  on platforms where `pkgs.vice` is available.
