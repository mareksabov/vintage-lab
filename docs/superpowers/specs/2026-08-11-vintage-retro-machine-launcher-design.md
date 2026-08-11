# Vintage — Reproducible Retro Machine Launcher (Design)

**Date:** 2026-08-11
**Status:** Approved design, ready for implementation planning

## Summary

`vintage` is a long-term hobby project for running faithful replicas of retro
computers. Each machine lives in its own self-contained folder that describes
the hardware and holds its persistent state. A small launcher, packaged with
Nix, reads that folder and boots the correct emulator. Everything is
reproducible across machines (macOS today, Linux and, later, a remote server)
via a Nix flake.

The first milestone is a faithful replica of a Dell OptiPlex-class Pentium II
that can boot into plain DOS and into Windows 98, matching the author's
original machine.

A web frontend and remote access are explicitly **future layers built on top of
the core** — not part of this design beyond making sure the core does not block
them.

## Goals

- **Replicable, not portable.** The architecture must not be macOS-specific. The
  same flake must produce an identical setup on macOS and Linux, and later on a
  server. Reproducibility comes from Nix; it does not mean "copy a ZIP to
  Windows and run".
- **Model the whole machine, not just an OS.** Correct CPU class, RAM, disk
  size, and drives — a believable replica, not necessarily a cycle-exact one.
- **Self-contained per machine.** One folder per machine. Duplicating a machine
  is `cp -r` of its folder (recipe + installed state come along).
- **Persistent state.** Installed system, disk contents, and NVRAM survive
  across runs.
- **Extensible.** Adding another machine is a new folder; adding another
  emulator (VICE for Commodore, FS-UAE for Amiga) is a new driver. No global
  installs — everything lives in this repo plus the Nix store.
- **Public repository.** All documentation, code comments, and descriptions are
  in English. Copyrighted media (ROMs, OS install images, disk images) must
  never enter the repository.

## Non-Goals (for now)

- Web frontend / nice GUI — a later layer over the core.
- Remote access / display streaming (VNC/WebRTC) — a later layer.
- Automated/scripted OS installation — the user installs the OS live from
  inserted media (authentic, and far simpler than scripting a period installer).
- A universal hardware-config schema across all emulators — premature while we
  have one emulator (YAGNI). Hardware detail stays in each emulator's native
  config.

## Emulator Choice

**86Box** for the first machine. Unlike DOSBox (which emulates DOS, not a
machine), 86Box emulates a concrete PC: motherboard, chipset, CPU, BIOS, disk
size, and floppy/CD drives. It boots whatever the user installs, so a dual-boot
DOS + Windows 98 machine models naturally as a single disk image — exactly like
the original hardware. Later emulators (VICE, FS-UAE) join as additional drivers
behind the same launcher.

## Architecture

Chosen approach: **hybrid driver + native config**.

- A small, human-readable `machine.toml` holds **metadata only**: name, which
  emulator, the inserted media, and where state lives.
- The emulator's **native config file** (for 86Box, an INI `.cfg`) holds the
  **hardware detail**, where it belongs.
- The launcher reads `machine.toml`, dispatches to the driver named by
  `emulator`, and the driver injects the media and state paths into the native
  config before launching the emulator from Nix.

This keeps a single unified catalog and launch path across emulators while
avoiding a leaky universal hardware schema. "Inserting media" becomes a
first-class, emulator-agnostic concept that a future web frontend can drive.

### Folder structure

```
vintage/
├── flake.nix            # pins emulators + launcher; outputs for macOS and Linux
├── flake.lock
├── .gitignore           # excludes media/ and state/ everywhere
├── lib/                 # launcher core + drivers
│   ├── vintage          # CLI: list / run / new / duplicate
│   └── drivers/
│       └── 86box        # knows how to launch 86Box
├── machines/
│   └── optiplex-gx/
│       ├── machine.toml # metadata: name, emulator=86box, media, state paths
│       ├── 86box.cfg    # native hardware config (Pentium II, disk size, drives)
│       ├── media/       # user-provided images (win98.iso, dos-boot.img) — gitignored
│       └── state/       # persistent: hdd.img, nvram — gitignored
├── docs/
└── README.md
```

The recipe (`machine.toml` + native config) is versioned in git. `media/` and
`state/` are binary and large and are **gitignored**. Copying the folder on disk
carries both the recipe and the installed state; git carries only the recipe.

### `machine.toml` (metadata only)

```toml
name     = "Dell OptiPlex GX — Pentium II"
emulator = "86box"
config   = "86box.cfg"

[[media]]
slot = "cdrom"
file = "media/win98se.iso"

[[media]]
slot = "floppy_a"
file = "media/dos-boot.img"
```

### Launcher core (Python, packaged via Nix)

Python is chosen for comfortable TOML parsing and cross-platform behavior; it is
available from the flake, so it adds no global dependency.

Responsibilities:

1. Resolve the machine directory.
2. Parse `machine.toml`.
3. Select the driver by `emulator`.
4. Driver: take the native config, inject the media paths (from `machine.toml`)
   and the state paths (disk image, NVRAM under `state/`), producing the
   effective runtime config.
5. Launch the emulator binary from Nix with that config and the correct working
   directory so relative paths resolve.

CLI surface:

- `vintage list` — list machines in `machines/`.
- `vintage run <machine>` — boot a machine.
- `vintage new <name>` — scaffold a new machine folder.
- `vintage duplicate <src> <dst>` — copy an existing machine into a new folder.

### Role of Nix

`flake.nix` pins `_86Box` (with its ROM/BIOS set), the `vintage` launcher, and
later `vice` and `fs-uae`. Running is `nix run .#vintage -- run optiplex-gx`.
The same flake yields an identical result on macOS and Linux, which is what
makes machines replicable. No global installs: everything lives in this repo and
the Nix store.

## First Milestone — Definition of Done (OptiPlex)

- `vintage run optiplex-gx` boots the modeled Pentium II from inserted media.
- The user installs DOS/Windows 98 live; on shutdown the disk image and NVRAM
  persist under `state/`.
- A subsequent run boots the already-installed system.
- `cp -r machines/optiplex-gx machines/optiplex-2` yields an independent second
  machine.
- No global installs; everything runs via Nix and this folder.

## Risks / Open Items

De-risking spike results (2026-08-11, on `aarch64-darwin`):

1. **86Box on macOS via nixpkgs — RESOLVED.** The package is available as a
   prebuilt binary in the Nix binary cache for `aarch64-darwin` (a dry-run only
   fetches ~50 MiB, nothing compiles) and nixpkgs ships a dedicated
   `darwin.patch`. The primary technical risk is retired.
   - **Note:** the attribute was renamed `_86Box` → `_86box`; the main program
     binary is `86Box`. Use the new attribute name in the flake.
2. **86Box ROM/BIOS set — DECIDED.** The 86Box package does **not** bundle ROMs,
   and there is no roms attribute in nixpkgs. ROMs live in the upstream
   `86Box/roms` repository and are copyrighted, so they must not be committed to
   this public repo. Approach: pin `github:86Box/roms` as a flake input with
   `flake = false`. ROMs are then reproducible (they live in the Nix store /
   flake input, not in git), and the 86Box driver points the emulator at that
   store path. Verify at implementation time that the repo path and 86Box's
   expected roms directory layout line up.
3. **Media provenance.** OS/boot images are provided by the user for hardware
   they owned, and are kept out of the public repository via `.gitignore`.

## Testing

Running the emulator cannot be unit-tested, but the launcher logic can:

- **Config generation (pure functions):** parsing `machine.toml` and the
  driver's config transformation (media injection, state-path rewriting) are
  tested with golden files — given `machine.toml` + a template `.cfg`, assert the
  expected effective `.cfg`.
- **Smoke tests:** `list`, `new`, and `duplicate` against a fixture machine.

## Future Layers (out of scope, kept unblocked)

- Web frontend: a thin UI over the same core (list, run, insert media).
- Remote access: display streaming so a server-hosted machine is usable
  remotely.
- Media upload: uploading disk/floppy images through the frontend instead of
  copying files in by hand.
