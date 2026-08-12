"""86Box driver: prepare the VM directory, wire ROMs and media, build argv."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Mapping

from ..cfg import set_values
from ..machine import Machine

# Media slot -> (section, key) in 86box.cfg.
# Verified against 86Box 6.0 output; see docs/86box-runtime-notes.md.
# Note: 86Box stores the mounted floppy image under `fdd_NN_fn`, but the
# mounted CD-ROM image under `cdrom_NN_image_path` (not `_fn`).
SLOT_KEYS: dict[str, tuple[str, str]] = {
    "floppy_a": ("Floppy and CD-ROM drives", "fdd_01_fn"),
    "floppy_b": ("Floppy and CD-ROM drives", "fdd_02_fn"),
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
        resolved = (machine.path / m.file).resolve()
        if not (machine.path / m.file).exists():
            print(
                f"warning: media file not found: {resolved} (slot {m.slot!r})",
                file=sys.stderr,
            )
        values[SLOT_KEYS[m.slot]] = str(resolved)
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
    # 86Box resolves a relative -P against its own userfiles dir (~/Library/86Box
    # on macOS), not the CWD, so a relative path misses our state/roms symlink.
    # Always pass an absolute path.
    return [box_bin, "-P", str(vmdir.resolve())]


def run(
    machine: Machine,
    *,
    env: Mapping[str, str],
    runner: Callable[[list[str]], int],
) -> int:
    """Prepare the 86Box VM dir and launch it. Owns 86Box-specific env."""
    roms = env.get("VINTAGE_ROMS_86BOX")
    if not roms:
        print("error: VINTAGE_ROMS_86BOX is not set", file=sys.stderr)
        return 1
    box_bin = env.get("VINTAGE_86BOX_BIN", "86Box")
    vmdir = prepare_vmdir(machine)
    link_roms(vmdir, Path(roms))
    apply_media(machine)
    return runner(build_argv(box_bin, vmdir))
