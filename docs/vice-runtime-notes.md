# VICE runtime notes

Facts recorded while wiring the C64 machine against VICE on `aarch64-darwin`.

## Binary

The C64 emulator binary is `x64sc` (cycle-accurate). Its source differs per
platform (see Platform availability):

- **Linux**: `${pkgs.vice}/bin/x64sc` from nixpkgs.
- **aarch64-darwin**: `x64sc` from the official prebuilt VICE arm64 SDL2 macOS
  build (see the `vice-macos` derivation in `flake.nix`).
- **x86_64-darwin**: not wired (the author's Macs are Apple Silicon).

The flake sets `VINTAGE_VICE_BIN` accordingly via `wrapProgram`; the VICE
driver just execs whatever that env var points at.

## ROMs

VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs; `x64sc` locates them relative
to its own location. No ROM env var or symlink is needed — in contrast with the
86Box driver which requires a `state/roms` symlink. On macOS the bundled ROMs
live under `VICE.app/Contents/Resources/share/vice/<MACHINE>/` inside the
prebuilt app and are found automatically.

## Config / persistence

`x64sc -config <state/vicerc>` reads and writes that file. The launcher copies
the versioned template into the machine's gitignored `state/` on first run, so
runtime tweaks persist there. Media is attached on the command line (`-8
<disk.d64>`), not via the config file.

## Platform availability

### nixpkgs `vice` is Linux-only

`pkgs.vice` in `nixpkgs-unstable` (vice-3.10) declares
`meta.platforms = lib.platforms.linux`. Attempting to evaluate it on
`aarch64-darwin` throws:

```
error: Refusing to evaluate package 'vice-3.10' …
       because it is not available on the requested hostPlatform:
         hostPlatform.system = "aarch64-darwin"
```

This is not stale metadata: the package genuinely depends on Linux-only inputs
(`alsa-lib`, `pulseaudio`, `libevdev`) and GTK3, which does not build cleanly
on Darwin in nixpkgs. Overriding `meta.platforms` alone does not make it build.
So macOS needs a different source for `x64sc`.

### macOS: the official prebuilt VICE app (implemented)

The flake packages the official VICE arm64 SDL2 macOS build as the `vice-macos`
derivation:

- `fetchurl` of `vice-arm64-sdl2-3.9.dmg` from the VICE project's SourceForge
  release directory, pinned by hash.
- Unpacked with `pkgs.undmg` (the DMG is a zlib/HFS+ UDIF image, which undmg
  handles; it also tolerates the `Applications -> /Applications` symlink that
  trips `7zz` without `-snld`).
- `dontFixup = true` / `stdenvNoCC`: the app's Mach-O binaries are code-signed
  by the VICE team. On Apple Silicon the kernel refuses to run a Mach-O whose
  signature was invalidated, so we copy the distribution **verbatim** and never
  run `strip`/`install_name_tool`, keeping the signatures valid.
- `VINTAGE_VICE_BIN` points at `${vice-macos}/vice/bin/x64sc`, which is the
  distribution's wrapper script. That script resolves `VICE.app` relative to its
  own directory (`dirname "$0"`), so it must be referenced at its real path — a
  `bin/` symlink would break `dirname`. Hence no symlink; the env var holds the
  full store path.

The per-platform selection lives in the `viceBin` binding in `flake.nix`:
Linux → `pkgs.vice`; `aarch64-darwin` → `vice-macos`; otherwise `null` (and
`VINTAGE_VICE_BIN` is simply not set, so the 86Box path still works).

### Licensing note

The official DMG bundles the original Commodore ROMs. This does not violate the
repo's "no copyrighted ROMs in git" rule: the ROMs arrive through the Nix store
(fetchurl from upstream), never into git — the same shape as the 86Box ROMs,
which come via a flake input. VICE is GPL-2.0+.

## Verified on aarch64-darwin (this host, 2026-08-12, Apple M3)

Linux-only-guard evaluation (86Box path unaffected):
- `nix flake check --no-build` → `all checks passed!` (no vice throw).
- `nix eval --raw .#packages.aarch64-darwin.vintage.outPath` → success.

macOS VICE packaging:
- `nix build .#packages.aarch64-darwin.vintage` builds `vice-macos` (fetches +
  extracts the DMG) and wires
  `VINTAGE_VICE_BIN=/nix/store/…-vice-macos-bin-3.9/vice/bin/x64sc`.
- `codesign -v` on the store copy of `x64sc` → exit 0 (signature preserved
  through the `cp -R`; `dontFixup` left the Mach-O untouched).
- `x64sc` runs from `/nix/store`: it loads its keymaps/config/ROMs from the
  copied bundle and reads the machine's `vicerc`. Byte-for-byte identical
  behaviour to the same binary run from the mounted DMG (verified side by side)
  — the packaging is a faithful copy, not a corrupted one.
- Test suite unchanged: `pytest -q` → 37 passed.

### Not verifiable from a headless context

`x64sc` is an SDL2 GUI app and needs a WindowServer (Aqua) session to create its
window. Run from a non-GUI context (the agent's shell, `SDL_VIDEODRIVER=dummy`,
or a detached process) it segfaults at display init — and the **official DMG
binary segfaults identically** in the same context, confirming this is an
environment limitation, not a packaging defect. The final visual confirmation —
`vintage run c64` opening the blue `READY.` BASIC screen — must be done in an
interactive desktop session.
