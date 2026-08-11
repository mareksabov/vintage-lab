"""Build a 1.44MB FAT12 floppy image from a folder, via mtools.

A small helper to get host files (e.g. a DOS game) into an emulated machine:
point it at a folder, get a floppy image you can insert. mtools does the work
(`mformat`/`mcopy`), so no mounting or root is needed and it works the same on
macOS and Linux. The flake wrapper puts mtools on PATH.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 1.44MB 3.5" floppy: mformat's "-f 1440" shorthand (80 tracks, 18 sec, 2 heads).
FLOPPY_FORMAT = "1440"


def make_floppy(src_dir: Path, out_path: Path, label: str = "FLOPPY") -> int:
    src_dir = Path(src_dir)
    out_path = Path(out_path)

    if not src_dir.is_dir():
        print(f"error: source folder not found: {src_dir}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    # DOS volume labels are at most 11 uppercase characters.
    volume = label.upper()[:11]
    entries = sorted(src_dir.iterdir())

    try:
        subprocess.run(
            ["mformat", "-C", "-f", FLOPPY_FORMAT, "-v", volume, "-i", str(out_path), "::"],
            check=True,
        )
        if entries:
            subprocess.run(
                ["mcopy", "-i", str(out_path), "-s", "-Q", *[str(e) for e in entries], "::"],
                check=True,
            )
    except FileNotFoundError:
        print(
            "error: mtools (mformat/mcopy) not found on PATH; run via 'nix run' "
            "or add nixpkgs#mtools to your shell",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError:
        print(
            "error: failed to build the floppy image "
            "(do the files exceed 1.44MB?)",
            file=sys.stderr,
        )
        out_path.unlink(missing_ok=True)
        return 1

    print(f"created {out_path} ({out_path.stat().st_size} bytes) from {src_dir}")
    return 0
