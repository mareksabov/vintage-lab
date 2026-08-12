"""The `run` command: dispatch a machine to its emulator driver."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

from .drivers import emu86box
from .machine import load_machine

# Emulator name (from machine.toml) -> driver entry point.
DRIVERS: dict[str, Callable[..., int]] = {
    "86box": emu86box.run,
}


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
    driver = DRIVERS.get(machine.emulator)
    if driver is None:
        supported = ", ".join(sorted(DRIVERS))
        print(
            f"error: unsupported emulator {machine.emulator!r} "
            f"(supported: {supported})",
            file=sys.stderr,
        )
        return 1
    return driver(machine, env=env, runner=runner)
