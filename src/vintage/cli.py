"""vintage command-line interface."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping, TextIO

from .machine import discover_machines

# Emulator -> (native config filename, starter config body, extra machine.toml).
_EMULATOR_TEMPLATES: dict[str, tuple[str, str, str]] = {
    "86box": ("86box.cfg", "[General]\n", ""),
    "vice": (
        "vicerc",
        "# VICE configuration; hardware defaults come from VICE.\n",
        'model    = "c64"\n',
    ),
}


def _machine_toml(name: str, emulator: str, config: str, extra: str = "") -> str:
    return (
        f'name     = "{name}"\n'
        f'emulator = "{emulator}"\n'
        f'{extra}'
        f'config   = "{config}"\n'
    )


def machines_root(env: Mapping[str, str] | None = None) -> Path:
    env = env if env is not None else {}
    override = env.get("VINTAGE_MACHINES")
    return Path(override) if override else Path("machines")


def cmd_list(root: Path, out: TextIO) -> int:
    for m in discover_machines(root):
        out.write(f"{m.id}\t{m.name}\n")
    return 0


def cmd_new(root: Path, name: str, emulator: str = "86box") -> int:
    template = _EMULATOR_TEMPLATES.get(emulator)
    if template is None:
        supported = ", ".join(sorted(_EMULATOR_TEMPLATES))
        print(
            f"error: unknown emulator {emulator!r} (supported: {supported})",
            file=sys.stderr,
        )
        return 1
    dest = root / name
    if dest.exists():
        print(f"error: machine {name!r} already exists", file=sys.stderr)
        return 1
    config_name, config_body, extra_toml = template
    (dest / "media").mkdir(parents=True)
    (dest / "state").mkdir(parents=True)
    (dest / "machine.toml").write_text(
        _machine_toml(name, emulator, config_name, extra_toml)
    )
    (dest / config_name).write_text(config_body)
    return 0


def cmd_duplicate(root: Path, src: str, dst: str) -> int:
    src_dir = root / src
    dst_dir = root / dst
    if not (src_dir / "machine.toml").is_file():
        print(f"error: no machine {src!r}", file=sys.stderr)
        return 1
    if dst_dir.exists():
        print(f"error: machine {dst!r} already exists", file=sys.stderr)
        return 1
    shutil.copytree(src_dir, dst_dir, symlinks=True)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vintage")
    parser.add_argument("--machines", help="path to machines directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list machines")
    p_new = sub.add_parser("new", help="scaffold a new machine")
    p_new.add_argument("name")
    p_new.add_argument(
        "--emulator",
        default="86box",
        choices=sorted(_EMULATOR_TEMPLATES),
        help="emulator for the new machine (default: 86box)",
    )
    p_dup = sub.add_parser("duplicate", help="copy a machine")
    p_dup.add_argument("src")
    p_dup.add_argument("dst")
    p_run = sub.add_parser("run", help="boot a machine")
    p_run.add_argument("machine")
    p_mk = sub.add_parser(
        "mkfloppy", help="build a 1.44MB floppy image from a folder"
    )
    p_mk.add_argument("src", help="source folder whose contents go on the floppy")
    p_mk.add_argument("out", help="output image path (e.g. .../media/pop.img)")
    p_mk.add_argument("--label", default="FLOPPY", help="volume label (<=11 chars)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.machines) if args.machines else machines_root(os.environ)

    if args.command == "list":
        return cmd_list(root, sys.stdout)
    if args.command == "new":
        return cmd_new(root, args.name, args.emulator)
    if args.command == "duplicate":
        return cmd_duplicate(root, args.src, args.dst)
    if args.command == "run":
        from .run import cmd_run

        return cmd_run(root, args.machine, env=os.environ)
    if args.command == "mkfloppy":
        from .mkfloppy import make_floppy

        return make_floppy(Path(args.src), Path(args.out), label=args.label)
    return 2
