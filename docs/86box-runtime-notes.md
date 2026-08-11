# 86Box runtime notes

Facts recorded while authoring the OptiPlex machine against 86Box 6.0 on
`aarch64-darwin`. These pin the two runtime unknowns the driver depends on.

## ROM location

86Box finds its ROM set through a `roms` directory inside the VM directory
passed via `-P`. The driver creates `state/roms` as a symlink to the
`86Box/roms` flake input's store path (`link_roms`). Confirmed working: with
`state/roms -> <store>/source`, 86Box's machine/BIOS lists are populated and a
machine boots. No global ROM path or environment variable is required.

## VM directory / persistence

`86Box -P <dir>` treats `<dir>` as the VM: it reads and writes `<dir>/86box.cfg`,
stores NVRAM under `<dir>/nvr/`, and resolves relative disk-image paths against
`<dir>`. The launcher points `-P` at each machine's `state/`, so the installed
system and CMOS persist there. The hard-disk image path in the config is kept
relative (`hdd_01_fn = hdd.img`) so it resolves inside `state/`.

## Media config keys (verified)

Mounted-image paths live in the `[Floppy and CD-ROM drives]` section. The key
names are NOT symmetric between floppy and CD-ROM:

| Slot        | Section                        | Key                    |
|-------------|--------------------------------|------------------------|
| `floppy_a`  | `Floppy and CD-ROM drives`     | `fdd_01_fn`            |
| `floppy_b`  | `Floppy and CD-ROM drives`     | `fdd_02_fn`            |
| `cdrom`     | `Floppy and CD-ROM drives`     | `cdrom_01_image_path`  |

The initial provisional guess used `fdd_01_image_path` for the floppy; the real
key is `fdd_01_fn`. 86Box also writes a per-drive `cdrom_01_image_history_NN`
with recently-used absolute paths — this is host-specific and must not be
committed to the machine template.

## OptiPlex GX hardware profile (authored)

- Machine: `p2bls` — ASUS P2B-LS, Intel 440BX, Slot 1 (period stand-in for the
  Dell OptiPlex GX1; no Dell-specific board ships with 86Box).
- CPU: `pentium2_deschutes` at 400 MHz; internal FPU; dynarec on.
- Memory: 128 MB (`mem_size = 131072`).
- Video: S3 ViRGE/DX PCI (`virge_dx_pci`).
- Floppy A: 3.5" 1.44M (`35_2hd`). CD-ROM 1: ATAPI on IDE `1:0`.
- Hard disk: onboard IDE `0:0`, `hdd.img` (relative), ~4 GB geometry.
- Sound: Sound Blaster 16.
