# vintage

A reproducible launcher for retro-computer replicas. Each machine lives in its
own self-contained folder that describes the hardware and holds its persistent
state. A small Nix-packaged CLI reads that folder and boots the right emulator.
The same Nix flake reproduces an identical setup on macOS and Linux.

The first supported machine is a Dell OptiPlex-class Pentium II running in
[86Box](https://86box.net/) — a machine that can boot plain DOS and Windows 98,
just like the original hardware.

> **Status:** the launcher core and Nix packaging are complete and tested. The
> shipped OptiPlex hardware profile and the exact 86Box media-config keys are
> authored interactively (see [Authoring a machine](#authoring-a-machine)).

## Requirements

- [Nix](https://nixos.org/download) with flakes enabled
  (`experimental-features = nix-command flakes`). Nothing else is installed
  system-wide — the emulator and the CLI come from the flake.

The 86Box binary is fetched from the Nix binary cache (no compilation).

## Quick start

```bash
# List the machines defined under ./machines
nix run .#vintage -- list

# Boot a machine (opens the 86Box window)
nix run .#vintage -- run optiplex-gx

# Scaffold a new machine folder
nix run .#vintage -- new dos622

# Duplicate a machine, including its installed state
nix run .#vintage -- duplicate optiplex-gx optiplex-clone
```

The machines directory defaults to `./machines`. Override it with the
`VINTAGE_MACHINES` environment variable.

### Development shell

A dev shell provides Python 3.11 and pytest with `PYTHONPATH` preset:

```bash
direnv allow          # loads the flake dev shell automatically (uses .envrc)
# or, without direnv:
nix develop -c pytest tests/ -v
```

## How it works

Each machine is a folder. It separates the **recipe** (versioned, text) from the
**persistent state** (binary, git-ignored):

```
machines/optiplex-gx/
├── machine.toml   # metadata: name, emulator, inserted media          (versioned)
├── 86box.cfg      # native 86Box hardware config (CPU, RAM, disk, ...)  (versioned)
├── media/         # your disk/CD images — win98.iso, dos-boot.img       (git-ignored)
└── state/         # 86Box VM dir: installed disk image, nvram, cfg copy (git-ignored)
```

`machine.toml` is deliberately small — hardware detail lives in the emulator's
own config file:

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

On `run`, the launcher:

1. copies the `86box.cfg` template into `state/` on first run only (so your
   installed system and its settings are never overwritten afterwards),
2. links the 86Box ROM set into `state/roms` (self-healing if the Nix store path
   changes),
3. injects the `machine.toml` media paths into the state config, and
4. launches 86Box with `state/` as its VM directory, so the hard-disk image and
   NVRAM persist there.

**Duplicating** a machine is just copying the folder (`vintage duplicate`, or
`cp -r`): the clone carries both the recipe and the installed system, and runs
independently.

### Media precedence

`machine.toml` is the source of truth for inserted media. Its media paths are
re-asserted into the config on **every** `run`. Ejecting a disk in the 86Box GUI
does not persist across runs — edit `machine.toml` to change what is inserted. If
a referenced media file is missing, the launcher warns on stderr and continues
(the drive simply shows empty).

## Authoring a machine

86Box models a concrete machine, so the hardware profile (`86box.cfg`) is created
by configuring it once in the 86Box UI:

1. Launch 86Box against a scratch VM directory and configure the machine
   (motherboard/chipset, CPU, RAM, floppy and CD drives) and create a **blank
   hard-disk image of a period-correct size** stored inside that directory.
2. Copy the resulting `86box.cfg` into the machine folder and make the hard-disk
   image path **relative** (e.g. `hdd.img`) so it resolves inside each machine's
   own `state/`.
3. Drop your own OS/boot media into `media/` matching the `machine.toml` slots,
   then `run` the machine and install the system live. The install persists in
   `state/`.

## A note on media and ROMs

This project distributes **no** BIOS ROMs, operating systems, or disk images. The
86Box machine ROM set is pulled reproducibly from the upstream
[`86Box/roms`](https://github.com/86Box/roms) repository via a flake input and is
never committed here. You supply your own OS and boot media, for hardware you own,
into each machine's git-ignored `media/` folder.

## Roadmap

- A web frontend over the same core (list, run, insert media).
- Remote access, so a server-hosted machine is usable from another device.
- More emulators behind the same launcher (Commodore via VICE, Amiga via FS-UAE).
- Uploading media through the frontend instead of copying files in by hand.

## License

See the design and plan documents under `docs/superpowers/` for the full
architecture and rationale.
