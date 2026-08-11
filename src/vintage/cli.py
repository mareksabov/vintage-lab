"""vintage command-line interface."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping, TextIO

from .machine import discover_machines

_TEMPLATE_TOML = (
    'name     = "{name}"\n'
    'emulator = "86box"\n'
    'config   = "86box.cfg"\n'
)


def machines_root(env: Mapping[str, str] | None = None) -> Path:
    env = env if env is not None else {}
    override = env.get("VINTAGE_MACHINES")
    return Path(override) if override else Path("machines")


def cmd_list(root: Path, out: TextIO) -> int:
    for m in discover_machines(root):
        out.write(f"{m.id}\t{m.name}\n")
    return 0


def cmd_new(root: Path, name: str) -> int:
    dest = root / name
    if dest.exists():
        print(f"error: machine {name!r} already exists", file=sys.stderr)
        return 1
    (dest / "media").mkdir(parents=True)
    (dest / "state").mkdir(parents=True)
    (dest / "machine.toml").write_text(_TEMPLATE_TOML.format(name=name))
    (dest / "86box.cfg").write_text("[General]\n")
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
        return cmd_new(root, args.name)
    if args.command == "duplicate":
        return cmd_duplicate(root, args.src, args.dst)
    if args.command == "run":
        from .run import cmd_run

        return cmd_run(root, args.machine, env=os.environ)
    if args.command == "mkfloppy":
        from .mkfloppy import make_floppy

        return make_floppy(Path(args.src), Path(args.out), label=args.label)
    return 2
