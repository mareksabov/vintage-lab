"""VICE driver: Commodore machines under VICE (x64sc).

Two deliberate contrasts with the 86Box driver, exercising the abstraction:
- No ROMs are wired. VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs, so there
  is no ROM env var and no `roms` symlink.
- Media is attached via VICE's CLI flags (e.g. `-8 disk.d64`), not by editing
  the native config, because VICE takes media on the command line.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Mapping

from ..machine import Machine

# Media slot -> VICE command-line flag.
SLOT_FLAGS: dict[str, str] = {
    "drive8": "-8",
}


def prepare_vmdir(machine: Machine) -> Path:
    """Ensure state/ exists and holds a working copy of the native config.

    Copies machine.config into state/ once; never overwrites, so user edits to
    the working copy (VICE reads and writes it) persist across runs.
    """
    vmdir = machine.state_dir
    vmdir.mkdir(parents=True, exist_ok=True)
    cfg_dst = vmdir / machine.config
    if not cfg_dst.exists():
        cfg_dst.write_text((machine.path / machine.config).read_text())
    return vmdir


def media_args(machine: Machine) -> list[str]:
    """Translate the declarative [[media]] set into VICE CLI flags."""
    args: list[str] = []
    for m in machine.media:
        flag = SLOT_FLAGS.get(m.slot)
        if flag is None:
            raise ValueError(f"unknown media slot: {m.slot!r}")
        resolved = (machine.path / m.file).resolve()
        if not (machine.path / m.file).exists():
            print(
                f"warning: media file not found: {resolved} (slot {m.slot!r})",
                file=sys.stderr,
            )
        args += [flag, str(resolved)]
    return args


def build_argv(vice_bin: str, config_path: Path, media: list[str]) -> list[str]:
    # VICE resolves a relative -config against its own CWD, not the machine
    # dir, so always pass an absolute path.
    return [vice_bin, "-config", str(config_path.resolve()), *media]


def run(
    machine: Machine,
    *,
    env: Mapping[str, str],
    runner: Callable[[list[str]], int],
) -> int:
    vice_bin = env.get("VINTAGE_VICE_BIN", "x64sc")
    vmdir = prepare_vmdir(machine)
    config_path = vmdir / machine.config
    return runner(build_argv(vice_bin, config_path, media_args(machine)))
