# VICE runtime notes

Facts recorded while wiring the C64 machine against VICE on `aarch64-darwin`.

## Binary

The C64 emulator binary is `x64sc` (cycle-accurate). On Linux, the flake
wires `VINTAGE_VICE_BIN = ${pkgs.vice}/bin/x64sc` via `wrapProgram`. On macOS
this env var is NOT set (see Platform availability below).

## ROMs

VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs; `x64sc` locates them via its
own data directory (wrapped in by nixpkgs). No ROM env var or symlink is needed
— in contrast with the 86Box driver which requires a `state/roms` symlink.

## Config / persistence

`x64sc -config <state/vicerc>` reads and writes that file. The launcher copies
the versioned template into the machine's gitignored `state/` on first run, so
runtime tweaks persist there. Media is attached on the command line (`-8
<disk.d64>`), not via the config file.

## Platform availability

### nixpkgs `vice` is Linux-only

`pkgs.vice` in `nixpkgs-unstable` (vice-3.10) declares
`meta.platforms = [ "x86_64-linux" "aarch64-linux" ... ]` — Linux only.
Attempting to evaluate it on `aarch64-darwin` throws:

```
error: Refusing to evaluate package 'vice-3.10' …
       because it is not available on the requested hostPlatform:
         hostPlatform.system = "aarch64-darwin"
```

### How the flake handles this (as of this fix)

The flake wires `VINTAGE_VICE_BIN` **only on Linux** using
`nixpkgs.lib.optionalString pkgs.stdenv.isLinux`. Because this is a pure Nix
string expression evaluated at derivation-build time (not IFD), `pkgs.vice` is
never forced on Darwin — Nix laziness keeps the Darwin outputs clean.

Result:
- On **Linux**: `wrapProgram` sets `VINTAGE_VICE_BIN=/nix/store/.../bin/x64sc`.
  `vintage run c64` works as designed.
- On **macOS**: `VINTAGE_VICE_BIN` is absent from the wrapper environment.
  The VICE driver falls back to its default behaviour — looking for `x64sc` on
  `PATH`. If `x64sc` is not on `PATH`, the driver will fail to launch; the user
  will see a "binary not found" / "VINTAGE_VICE_BIN is not set" style error
  from the launcher. The **86Box path is unaffected** and continues to work.

Verified on `aarch64-darwin` (this host, 2026-08-12):
- `nix eval --raw .#packages.aarch64-darwin.vintage.outPath` →
  `/nix/store/1k64lnzqims6fkc0s4rrbz6a4csrzqwh-vintage` (success)
- `nix flake check --no-build` → `all checks passed!` (no vice throw)
- `nix eval --raw .#packages.x86_64-linux.vintage.outPath` →
  `/nix/store/a6bjhpm3r8kdsh6b1vkxrgy268sjrpgd-vintage` (success; vice arg
  included in the Linux derivation string; does not force a build of vice)

### macOS VICE support — open decision

Running `vintage run c64` on macOS currently fails at emulator launch because
`VINTAGE_VICE_BIN` is unset and `x64sc` is unlikely to be on `PATH`. Options
for macOS support (none implemented; controller decision required):

1. **Remote Linux builder**: build the Linux closure on a Linux host and deploy
   to macOS (no macOS VICE binary needed; closest to the current nixpkgs path).
2. **Separate macOS VICE binary input**: add a flake input or overlay that
   provides a Darwin-compatible `x64sc` build (e.g. sourced from a third-party
   flake or built from source with macOS-compatible deps).
3. **Homebrew shim**: document that users install VICE via Homebrew (`brew
   install vice`) and add `x64sc` to `PATH` before calling `vintage run c64`.
   The launcher will pick it up without any flake changes.
4. **Accept Linux-only for VICE**: guard the C64 driver with an explicit
   platform check; document `vintage run c64` as Linux-only.

## What was NOT verified (requires build + runtime)

Because `pkgs.vice` does not evaluate on this host, the following facts could
NOT be confirmed and remain expected / pending verification on a Linux host:

- ROM discovery actually works at runtime (VICE finds its bundled ROMs through
  the nixpkgs wrapper without any extra flags).
- `x64sc -config state/vicerc` boots to the blue `READY.` BASIC screen.
- Media attachment via `-8 <disk.d64>` loads correctly.
- The `vicerc` template in `machines/c64/vicerc` is accepted without error by
  the version of VICE that nixpkgs ships.

## Verified on aarch64-darwin (this host)

- `PYTHONPATH=src pytest -q` → 37 passed (full suite green).
- `nix flake check --no-build` → all checks passed (no vice throw; Darwin 86Box
  path evaluates cleanly).
- Both `aarch64-darwin.vintage` and `x86_64-linux.vintage` outPaths evaluate
  successfully.
- `flake.nix` evaluates correctly for `packages.aarch64-darwin.emulator86box`
  and `packages.aarch64-darwin.vintage-unwrapped`.
