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

`prepare_vmdir` copies the versioned config into `state/86box.cfg` **only when
that file does not yet exist** — it seeds the VM once, then leaves it alone so
86Box owns it. Editing the versioned template therefore has no effect on a
machine that has already been booted: the same edit has to be made in
`state/86box.cfg` too, or made in the 86Box UI and back-ported to the template.

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

## Networking (verified)

Network adapters live in the `[Network]` section, one numbered slot per card
(`net_01_` … `net_04_`). Two keys are enough for user-mode NAT:

```ini
[Network]
net_01_card = pcnetpci
net_01_net_type = slirp
```

- `net_01_card` takes a device *internal* name. `pcnetpci` is the AMD PCnet-PCI
  II (Am79C970A), which enumerates as `PCI\VEN_1022&DEV_2000` — the ID Windows
  98 SE's in-box `netamd.inf` binds to, so the guest needs no driver disk. The
  `p2bls` board has no onboard NIC in 86Box (no `MACHINE_NIC` flag), so the card
  goes into a PCI slot.
- `net_01_net_type` is a string: `slirp`, `pcap`, `vde`, `tap`, `nlswitch` or
  `nrswitch`. Absent or unrecognised means no networking. The nixpkgs `_86box`
  build links `libslirp.so.0` directly, so SLiRP works with no privileges and no
  host TAP device. (`libpcap` is dlopened and the wrapper puts it on
  `LD_LIBRARY_PATH`, so bridged mode is available too, but it needs
  `CAP_NET_RAW`.)
- `net_01_link` is a link-state bitmask whose default is every speed enabled.
  86Box *deletes* the key when it equals that default, so leaving it out is the
  correct way to say "link up at any speed". The old `net_01_link = 0` line was
  a leftover from having no card at all.

SLiRP addressing for the first card is fixed: guest `10.0.0.15`, gateway
`10.0.0.2`, DNS `10.0.0.3`, mask `/24`. Override the subnet with
`net_01_addr` if it collides with the host LAN. Guest-side `ping` works only if
the host allows unprivileged ICMP sockets (`net.ipv4.ping_group_range` covering
the user's gid).

Once a card is configured, 86Box adds a per-instance section holding a generated
MAC (`[AMD PCnet-PCI II #1]` / `mac = ...`). Like `cdrom_01_image_history_NN`,
this is generated state and belongs in `state/`, not in the machine template.

## OptiPlex GX hardware profile (authored)

- Machine: `p2bls` — ASUS P2B-LS, Intel 440BX, Slot 1 (period stand-in for the
  Dell OptiPlex GX1; no Dell-specific board ships with 86Box).
- CPU: `pentium2_deschutes` at 400 MHz; internal FPU; dynarec on.
- Memory: 128 MB (`mem_size = 131072`).
- Video: S3 ViRGE/DX PCI (`virge_dx_pci`).
- Floppy A: 3.5" 1.44M (`35_2hd`). CD-ROM 1: ATAPI on IDE `1:0`.
- Hard disk: onboard IDE `0:0`, `hdd.img` (relative), ~4 GB geometry.
- Sound: Sound Blaster 16.
- Network: AMD PCnet-PCI II (`pcnetpci`) on SLiRP user-mode NAT.
