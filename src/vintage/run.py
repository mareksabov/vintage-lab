"""The `run` command: prepare a machine and launch its emulator."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

from .drivers import emu86box
from .machine import load_machine


def _default_runner(argv: list[str]) -> int:
    return subprocess.run(argv).returncode


def cmd_run(
    root: Path,
    machine_id: str,
    *,
    env: Mapping[str, str],
    runner: Callable[[list[str]], int] = _default_runner,
) -> int:
    machine = load_machine(root / machine_id)
    if machine.emulator != "86box":
        print(f"error: unsupported emulator {machine.emulator!r}", file=sys.stderr)
        return 1
    roms = env.get("VINTAGE_ROMS_86BOX")
    if not roms:
        print("error: VINTAGE_ROMS_86BOX is not set", file=sys.stderr)
        return 1
    box_bin = env.get("VINTAGE_86BOX_BIN", "86Box")

    vmdir = emu86box.prepare_vmdir(machine)
    emu86box.link_roms(vmdir, Path(roms))
    emu86box.apply_media(machine)
    return runner(emu86box.build_argv(box_bin, vmdir))
