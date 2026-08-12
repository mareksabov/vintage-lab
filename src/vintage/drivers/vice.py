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

# Media slot -> VICE command-line flag. Flags are identical in x64sc and xvic.
SLOT_FLAGS: dict[str, str] = {
    "drive8": "-8",             # disk image in drive 8
    "tape": "-1",              # datasette tape image (attach; load by hand)
    "cart": "-cartcrt",        # CRT-format cartridge image
    "autostart": "-autostart",  # attach and auto-run a program/image
}

# VICE machine model -> emulator binary name (all live in one bin/ dir).
MODEL_BINARIES: dict[str, str] = {
    "c64": "x64sc",
    "vic20": "xvic",
}

# Config section holding VICE's own version stamp (see stamp_version).
VERSION_SECTION = "Version"


def resolve_binary(model: str, env: Mapping[str, str]) -> str:
    """Resolve the VICE binary for a machine model.

    Joins the binary name onto VINTAGE_VICE_BIN_DIR when set (Nix wiring);
    otherwise returns the bare name for a PATH lookup (dev shell / tests).
    """
    try:
        name = MODEL_BINARIES[model]
    except KeyError:
        known = ", ".join(sorted(MODEL_BINARIES))
        raise ValueError(f"unknown vice model: {model!r} (known: {known})")
    bindir = env.get("VINTAGE_VICE_BIN_DIR")
    return str(Path(bindir) / name) if bindir else name


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


# VIC-20 memory-expansion specs accepted by `xvic -memory <spec>`.
VIC20_MEMORY: frozenset[str] = frozenset({"3k", "8k", "16k", "24k", "all"})


def ram_args(machine: Machine) -> list[str]:
    """Translate the optional `ram` knob into VICE flags (model-aware)."""
    ram = machine.options.get("ram")
    if ram is None:
        return []
    model = str(machine.options.get("model", "c64"))
    if model == "vic20":
        if ram not in VIC20_MEMORY:
            choices = ", ".join(sorted(VIC20_MEMORY))
            raise ValueError(f"unsupported ram {ram!r} for vic20 (choose: {choices})")
        return ["-memory", str(ram)]
    if model == "c64":
        if ram != "reu":
            raise ValueError(f"unsupported ram {ram!r} for c64 (choose: reu)")
        return ["-reu"]
    raise ValueError(f"ram not supported for vice model {model!r}")


def stamp_version(config_path: Path, version: str) -> None:
    """Append VICE's `[Version]` tag to the working copy if it has none.

    VICE stamps `ConfigVersion` into every config it saves and warns on load
    when the tag is missing ("No version tag found in configuration file") —
    which is every fresh copy of our template. The tag belongs in state/, not
    in the versioned template: the expected value is whichever VICE the flake
    pinned for this platform (3.10 on Linux, 3.9 on macOS), and a wrong value
    trades the missing-tag warning for a version-mismatch one.

    An existing tag is left alone: VICE wrote it when the user saved settings,
    and a mismatch after a VICE bump is a real signal, not ours to suppress.
    """
    text = config_path.read_text()
    if any(line.strip() == f"[{VERSION_SECTION}]" for line in text.splitlines()):
        return
    lead = "" if text.endswith("\n") or not text else "\n"
    config_path.write_text(
        f"{text}{lead}\n[{VERSION_SECTION}]\nConfigVersion={version}\n"
    )


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
    model = str(machine.options.get("model", "c64"))
    vice_bin = resolve_binary(model, env)
    vmdir = prepare_vmdir(machine)
    config_path = vmdir / machine.config
    version = env.get("VINTAGE_VICE_VERSION")
    if version:
        stamp_version(config_path, version)
    extra = ram_args(machine) + media_args(machine)
    return runner(build_argv(vice_bin, config_path, extra))
