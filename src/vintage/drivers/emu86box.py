"""86Box driver: prepare the VM directory, wire ROMs and media, build argv."""

from __future__ import annotations

import os
from pathlib import Path

from ..cfg import set_values
from ..machine import Machine

# Media slot -> (section, key) in 86box.cfg.
# Reconcile with docs/86box-runtime-notes.md (Task 2) before relying on these.
SLOT_KEYS: dict[str, tuple[str, str]] = {
    "floppy_a": ("Floppy and CD-ROM drives", "fdd_01_image_path"),
    "floppy_b": ("Floppy and CD-ROM drives", "fdd_02_image_path"),
    "cdrom": ("Floppy and CD-ROM drives", "cdrom_01_image_path"),
}


def prepare_vmdir(machine: Machine) -> Path:
    vmdir = machine.state_dir
    vmdir.mkdir(parents=True, exist_ok=True)
    cfg_dst = vmdir / "86box.cfg"
    if not cfg_dst.exists():
        cfg_dst.write_text((machine.path / machine.config).read_text())
    return vmdir


def apply_media(machine: Machine) -> None:
    cfg_path = machine.state_dir / "86box.cfg"
    values: dict[tuple[str, str], str] = {}
    for m in machine.media:
        if m.slot not in SLOT_KEYS:
            raise ValueError(f"unknown media slot: {m.slot!r}")
        values[SLOT_KEYS[m.slot]] = str((machine.path / m.file).resolve())
    if values:
        cfg_path.write_text(set_values(cfg_path.read_text(), values))


def link_roms(vmdir: Path, roms_path: Path) -> None:
    """Create or repair the vmdir/roms symlink so it points at roms_path.

    Rules:
    - Correct existing symlink (target == roms_path) → no-op.
    - Symlink pointing elsewhere OR broken/dangling → remove and re-create.
    - Non-symlink entry (real dir/file) → raise RuntimeError to protect user data.
    - Missing → create.
    """
    link = vmdir / "roms"
    if link.is_symlink():
        # os.readlink works even for dangling symlinks; .resolve() does not.
        current_target = Path(os.readlink(link))
        if current_target == roms_path or current_target == roms_path.resolve():
            return
        link.unlink()
    elif link.exists():
        raise RuntimeError(
            f"{link} exists as a non-symlink (real file or directory). "
            "Remove it manually before letting the driver manage it."
        )
    link.symlink_to(roms_path)


def build_argv(box_bin: str, vmdir: Path) -> list[str]:
    return [box_bin, "-P", str(vmdir)]
