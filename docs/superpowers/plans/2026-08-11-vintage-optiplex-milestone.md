# Vintage — OptiPlex Milestone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible, Nix-packaged `vintage` CLI that boots a faithful Dell OptiPlex (Pentium II) replica in 86Box from its own self-contained folder, with persistent state and easy duplication.

**Architecture:** Each machine is a folder holding a small `machine.toml` (metadata + inserted media) and a native `86box.cfg` (hardware). A Python CLI discovers machines, and a per-emulator driver prepares a persistent VM directory under `state/`, injects media paths into the config, links the ROM set, and launches the emulator. A Nix flake pins the emulator, the ROM set, and the CLI so the same setup reproduces on macOS and Linux.

**Tech Stack:** Nix flakes, `nixpkgs#_86box` (86Box 6.0, prebuilt for aarch64-darwin), `github:86Box/roms` (flake input, `flake = false`), Python 3.11+ (stdlib only: `tomllib`, `configparser`, `argparse`), pytest.

## Global Constraints

- **English only** in all committed docs, code comments, identifiers, and CLI copy. (Conversation with the user stays Slovak; the repo is English.)
- **No copyrighted binaries in git.** `media/` and `state/` (OS/disk/floppy images, NVRAM) and ROMs are never committed. ROMs come from the `86Box/roms` flake input; media is user-provided into `media/`.
- **Reproducible via flake** for `aarch64-darwin` and `x86_64-linux` / `aarch64-linux` — no macOS-specific code paths in the CLI.
- **No global installs.** Everything runs through `nix run` / the flake; user data lives in the repo working dir.
- **Nixpkgs attribute is `_86box`** (renamed from `_86Box`); the installed program binary is named `86Box`.
- **Python core, stdlib only** — no third-party runtime dependencies, so Nix packaging stays trivial.

---

## File Structure

```
vintage/
├── flake.nix                     # inputs (nixpkgs, roms), packages (emulator, vintage), apps
├── flake.lock
├── pyproject.toml                # setuptools package metadata for `vintage`
├── .gitignore                    # media/ and state/ everywhere
├── src/vintage/
│   ├── __init__.py
│   ├── machine.py                # Machine/Media dataclasses, load_machine, discover_machines
│   ├── cfg.py                    # set_values(): targeted 86box.cfg edits via configparser
│   ├── cli.py                    # argparse: list / run / new / duplicate; main()
│   └── drivers/
│       ├── __init__.py
│       └── emu86box.py           # prepare_vmdir, apply_media, link_roms, build_argv
├── machines/
│   └── optiplex-gx/
│       ├── machine.toml          # metadata + media slots
│       ├── 86box.cfg             # Pentium II hardware template (authored in Task 2)
│       ├── media/.gitkeep        # user drops win98.iso / dos-boot.img here
│       └── state/.gitkeep        # 86Box writes 86box.cfg copy, nvr/, hdd image here
├── tests/
│   ├── conftest.py               # fixtures: temp machine roots
│   ├── test_machine.py
│   ├── test_cfg.py
│   ├── test_driver_86box.py
│   └── test_cli.py
├── docs/
│   └── 86box-runtime-notes.md    # ROM wiring + cfg media keys discovered in Task 2
└── README.md
```

**Runtime wiring (how the packaged CLI finds things):** the Nix wrapper sets `VINTAGE_86BOX_BIN` (absolute path to the `86Box` binary) and `VINTAGE_ROMS_86BOX` (absolute path to the ROM set). The CLI reads these from the environment, falling back to `86Box` on `PATH` for local dev. The machines root defaults to `./machines` relative to the current directory (overridable via `VINTAGE_MACHINES`), because machines are user data in the working repo, not in the Nix store.

---

### Task 1: Repo scaffold, `.gitignore`, and flake skeleton

**Files:**
- Create: `.gitignore`, `flake.nix`, `pyproject.toml`, `src/vintage/__init__.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a flake exposing `packages.<system>.emulator86box` (the 86Box package) and the `roms86box` input path; `pyproject.toml` declaring the `vintage` package (used by Task 9).

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Never commit machine media or persistent state (may include copyrighted images)
**/media/
**/state/
# but keep the placeholder dirs
!**/media/.gitkeep
!**/state/.gitkeep

# Python
__pycache__/
*.pyc
.pytest_cache/
result
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "vintage"
version = "0.1.0"
description = "Reproducible retro machine launcher"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
vintage = "vintage.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Write `src/vintage/__init__.py`**

```python
"""vintage: reproducible retro machine launcher."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write `flake.nix` skeleton (emulator + roms only; CLI added in Task 9)**

```nix
{
  description = "Reproducible retro machine launcher";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    roms86box = {
      url = "github:86Box/roms";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, roms86box }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f system nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAll (system: pkgs: {
        emulator86box = pkgs._86box;
      });

      # The 86Box ROM set, exposed for inspection / driver wiring.
      romsPath = roms86box;
    };
}
```

- [ ] **Step 5: Verify the flake evaluates and the emulator resolves**

Run: `nix flake check --extra-experimental-features 'nix-command flakes'`
Then: `nix build --extra-experimental-features 'nix-command flakes' '.#emulator86box' && ls -la result/bin/86Box`
Expected: `flake check` passes; `result/bin/86Box` exists (fetched from cache, no long compile).

- [ ] **Step 6: Verify the ROM set fetches and has a plausible layout**

Run: `nix build --extra-experimental-features 'nix-command flakes' '.#romsPath' --out-link roms-result && ls roms-result | head`
Expected: directory of machine ROM subfolders (e.g. per-motherboard BIOS folders). Record nothing yet — Task 2 confirms how 86Box consumes it.

- [ ] **Step 7: Commit**

```bash
git add .gitignore flake.nix flake.lock pyproject.toml src/vintage/__init__.py
git commit -m "chore: scaffold repo, gitignore, and flake with 86Box + roms inputs"
```

---

### Task 2: Author the OptiPlex machine and pin 86Box runtime facts (spike)

This is an exploratory infra/authoring task, not TDD — it produces committed artifacts (the hardware config template) and records the two 86Box runtime unknowns the driver depends on: **how ROMs are located** and **which cfg keys hold floppy/CD/HDD image paths**. The Python tasks that follow consume these recorded facts.

**Files:**
- Create: `machines/optiplex-gx/86box.cfg`, `machines/optiplex-gx/media/.gitkeep`, `machines/optiplex-gx/state/.gitkeep`, `docs/86box-runtime-notes.md`

**Interfaces:**
- Consumes: `.#emulator86box` and `.#romsPath` from Task 1.
- Produces: a valid `86box.cfg` hardware template; `docs/86box-runtime-notes.md` recording (a) the ROM-location mechanism the driver will use and (b) the exact `[section] key` names for floppy A/B and CD-ROM image paths. **Task 6's `SLOT_KEYS` map must match what is recorded here.**

- [ ] **Step 1: Create an authoring VM directory and link ROMs into it**

```bash
BOX=$(nix build --print-out-paths --extra-experimental-features 'nix-command flakes' '.#emulator86box')/bin/86Box
ROMS=$(nix build --print-out-paths --extra-experimental-features 'nix-command flakes' '.#romsPath')
mkdir -p /tmp/optiplex-authoring
ln -sfn "$ROMS" /tmp/optiplex-authoring/roms
```

- [ ] **Step 2: Launch 86Box against that VM path and confirm ROM discovery**

```bash
"$BOX" -P /tmp/optiplex-authoring
```
In the GUI: open Settings. If machine/BIOS lists are populated, the `<vmdir>/roms` symlink is a valid ROM source — record this as the mechanism. If BIOS lists are empty, try 86Box's documented ROM locations (e.g. a `roms` dir beside the binary, or a user data dir) and record whichever populates the lists.
Expected: a mechanism that makes machine/BIOS options appear. Write it into `docs/86box-runtime-notes.md`.

- [ ] **Step 3: Configure the OptiPlex hardware and a blank disk**

In Settings, model a period-appropriate Pentium II OptiPlex: a Slot 1 / Socket 370-class Pentium II machine + chipset, RAM (e.g. 64–128 MB), a Floppy A (3.5" 1.44M), a CD-ROM drive, and create **a new blank hard disk image of a period-correct size** (e.g. 4 GB) stored **inside the VM dir**. Save settings. Quit 86Box.

- [ ] **Step 4: Capture the config as the machine template**

```bash
cp /tmp/optiplex-authoring/86box.cfg machines/optiplex-gx/86box.cfg
mkdir -p machines/optiplex-gx/media machines/optiplex-gx/state
touch machines/optiplex-gx/media/.gitkeep machines/optiplex-gx/state/.gitkeep
```
Then edit `machines/optiplex-gx/86box.cfg`: make the hard-disk image path **relative** (a bare filename like `hdd.img`) so it resolves inside each machine's own `state/` dir rather than pointing at `/tmp`.

- [ ] **Step 5: Discover the media cfg keys**

Relaunch `"$BOX" -P /tmp/optiplex-authoring`, mount any file as Floppy A and as a CD image via the GUI menus, quit, then inspect the diff:
```bash
grep -nE 'fdd_|cdrom_|hdd_' /tmp/optiplex-authoring/86box.cfg
```
Record the exact `[section]` and key names that now hold the floppy and CD-ROM image paths into `docs/86box-runtime-notes.md` (e.g. `[Floppy and CD-ROM drives] fdd_01_image_path`). These become Task 6's `SLOT_KEYS`.

- [ ] **Step 6: Write `docs/86box-runtime-notes.md`**

Document: the ROM-location mechanism chosen in Step 2; the exact media cfg keys from Step 5; and that the hdd path in the template is relative to the VM dir. Keep it short and factual.

- [ ] **Step 7: Commit (config template + notes only — never the disk image)**

```bash
git add machines/optiplex-gx/86box.cfg machines/optiplex-gx/media/.gitkeep \
        machines/optiplex-gx/state/.gitkeep docs/86box-runtime-notes.md
git status   # confirm NO hdd.img / *.iso / nvr staged
git commit -m "feat: author OptiPlex 86Box hardware template and record runtime facts"
```

---

### Task 3: `machine.toml` model, loading, and discovery

**Files:**
- Create: `src/vintage/machine.py`, `tests/conftest.py`, `tests/test_machine.py`
- Create: `machines/optiplex-gx/machine.toml`

**Interfaces:**
- Consumes: nothing from prior Python tasks.
- Produces:
  - `class Media` (frozen dataclass): `slot: str`, `file: str`.
  - `class Machine` (frozen dataclass): `id: str`, `path: Path`, `name: str`, `emulator: str`, `config: str`, `media: tuple[Media, ...]`; properties `state_dir -> Path` (`path/"state"`), `media_dir -> Path` (`path/"media"`).
  - `load_machine(path: Path) -> Machine` — parses `<path>/machine.toml`; `id` is the folder name.
  - `discover_machines(root: Path) -> list[Machine]` — every immediate subdir of `root` containing a `machine.toml`, sorted by `id`.

- [ ] **Step 1: Write `machines/optiplex-gx/machine.toml`**

```toml
name     = "Dell OptiPlex GX — Pentium II"
emulator = "86box"
config   = "86box.cfg"

[[media]]
slot = "cdrom"
file = "media/win98se.iso"

[[media]]
slot = "floppy_a"
file = "media/dos-boot.img"
```

- [ ] **Step 2: Write the failing tests**

`tests/conftest.py`:
```python
from pathlib import Path
import pytest


def _write_machine(root: Path, mid: str, toml: str) -> Path:
    d = root / mid
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(toml)
    (d / "86box.cfg").write_text("[General]\n")
    return d


@pytest.fixture
def machine_root(tmp_path: Path) -> Path:
    _write_machine(
        tmp_path,
        "optiplex-gx",
        'name = "Dell OptiPlex GX"\n'
        'emulator = "86box"\n'
        'config = "86box.cfg"\n'
        "[[media]]\n"
        'slot = "cdrom"\n'
        'file = "media/win98se.iso"\n',
    )
    _write_machine(
        tmp_path,
        "c64",
        'name = "Commodore 64"\nemulator = "vice"\nconfig = "vice.cfg"\n',
    )
    (tmp_path / "not-a-machine").mkdir()  # ignored: no machine.toml
    return tmp_path
```

`tests/test_machine.py`:
```python
from pathlib import Path
from vintage.machine import Machine, Media, load_machine, discover_machines


def test_load_machine_parses_fields_and_media(machine_root: Path):
    m = load_machine(machine_root / "optiplex-gx")
    assert m.id == "optiplex-gx"
    assert m.name == "Dell OptiPlex GX"
    assert m.emulator == "86box"
    assert m.config == "86box.cfg"
    assert m.media == (Media(slot="cdrom", file="media/win98se.iso"),)


def test_machine_dir_properties(machine_root: Path):
    m = load_machine(machine_root / "optiplex-gx")
    assert m.state_dir == machine_root / "optiplex-gx" / "state"
    assert m.media_dir == machine_root / "optiplex-gx" / "media"


def test_load_machine_without_media_gives_empty_tuple(machine_root: Path):
    m = load_machine(machine_root / "c64")
    assert m.media == ()


def test_discover_machines_sorted_ignores_non_machines(machine_root: Path):
    ids = [m.id for m in discover_machines(machine_root)]
    assert ids == ["c64", "optiplex-gx"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_machine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vintage'` or import errors.

- [ ] **Step 4: Implement `src/vintage/machine.py`**

```python
"""Machine model, loading, and discovery."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Media:
    slot: str
    file: str


@dataclass(frozen=True)
class Machine:
    id: str
    path: Path
    name: str
    emulator: str
    config: str
    media: tuple[Media, ...] = ()

    @property
    def state_dir(self) -> Path:
        return self.path / "state"

    @property
    def media_dir(self) -> Path:
        return self.path / "media"


def load_machine(path: Path) -> Machine:
    data = tomllib.loads((path / "machine.toml").read_text())
    media = tuple(
        Media(slot=entry["slot"], file=entry["file"])
        for entry in data.get("media", [])
    )
    return Machine(
        id=path.name,
        path=path,
        name=data["name"],
        emulator=data["emulator"],
        config=data["config"],
        media=media,
    )


def discover_machines(root: Path) -> list[Machine]:
    machines = [
        load_machine(child)
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "machine.toml").is_file()
    ]
    return machines
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_machine.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/vintage/machine.py tests/conftest.py tests/test_machine.py machines/optiplex-gx/machine.toml
git commit -m "feat: machine.toml model, loading, and discovery"
```

---

### Task 4: `set_values` — targeted 86box.cfg edits

**Files:**
- Create: `src/vintage/cfg.py`, `tests/test_cfg.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `set_values(cfg_text: str, values: dict[tuple[str, str], str]) -> str` — returns cfg text with each `(section, key)` set to its value, preserving key case, creating missing sections, leaving other keys intact.

- [ ] **Step 1: Write the failing tests**

`tests/test_cfg.py`:
```python
from vintage.cfg import set_values


def test_sets_existing_key_in_existing_section():
    text = "[Floppy and CD-ROM drives]\nfdd_01_image_path = old.img\n"
    out = set_values(text, {("Floppy and CD-ROM drives", "fdd_01_image_path"): "/a/new.img"})
    assert "fdd_01_image_path = /a/new.img" in out
    assert "old.img" not in out


def test_creates_missing_section():
    out = set_values("[General]\nvid = 1\n", {("Hard disks", "hdd_01_fn"): "hdd.img"})
    assert "[Hard disks]" in out
    assert "hdd_01_fn = hdd.img" in out


def test_preserves_other_keys_and_key_case():
    text = "[General]\nWindowedMode = 1\nvid_resize = 0\n"
    out = set_values(text, {("General", "vid_resize"): "1"})
    assert "WindowedMode = 1" in out       # untouched, case preserved
    assert "vid_resize = 1" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cfg.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vintage.cfg'`.

- [ ] **Step 3: Implement `src/vintage/cfg.py`**

```python
"""Targeted edits to 86Box-style INI config files."""

from __future__ import annotations

import configparser
import io


def set_values(cfg_text: str, values: dict[tuple[str, str], str]) -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # preserve key case (86Box keys are case-sensitive)
    parser.read_string(cfg_text)
    for (section, key), value in values.items():
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, value)
    out = io.StringIO()
    parser.write(out, space_around_delimiters=True)
    return out.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cfg.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/vintage/cfg.py tests/test_cfg.py
git commit -m "feat: targeted 86box.cfg value editing"
```

---

### Task 5: 86Box driver — VM dir, ROM link, argv

**Files:**
- Create: `src/vintage/drivers/__init__.py`, `src/vintage/drivers/emu86box.py`, `tests/test_driver_86box.py`

**Interfaces:**
- Consumes: `Machine` from Task 3; `set_values` from Task 4; the recorded `SLOT_KEYS` from Task 2.
- Produces:
  - `SLOT_KEYS: dict[str, tuple[str, str]]` mapping media slot → `(section, key)`.
  - `prepare_vmdir(machine: Machine) -> Path` — ensures `state/` exists and copies the `86box.cfg` template into `state/86box.cfg` on first run (never overwrites an existing one).
  - `apply_media(machine: Machine) -> None` — writes each media file's absolute path into `state/86box.cfg` via `SLOT_KEYS`.
  - `link_roms(vmdir: Path, roms_path: Path) -> None` — ensures `vmdir/roms` symlinks to `roms_path` (no-op if present).
  - `build_argv(box_bin: str, vmdir: Path) -> list[str]` — returns `[box_bin, "-P", str(vmdir)]`.

**Note:** the `SLOT_KEYS` values below are the expected 86Box 6.0 keys; **reconcile them with `docs/86box-runtime-notes.md` from Task 2** and adjust if the recorded keys differ. The ROM mechanism here (a `roms` symlink inside the VM dir) must also match what Task 2 recorded; if Task 2 found a different mechanism, implement `link_roms` accordingly.

- [ ] **Step 1: Write the failing tests**

`tests/test_driver_86box.py`:
```python
from pathlib import Path
import pytest
from vintage.machine import load_machine
from vintage.drivers import emu86box


@pytest.fixture
def machine(tmp_path: Path):
    d = tmp_path / "optiplex-gx"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "media" / "boot.img").write_text("floppy")
    (d / "machine.toml").write_text(
        'name = "OptiPlex"\nemulator = "86box"\nconfig = "86box.cfg"\n'
        '[[media]]\nslot = "floppy_a"\nfile = "media/boot.img"\n'
    )
    (d / "86box.cfg").write_text("[General]\nvid_resize = 0\n")
    return load_machine(d)


def test_prepare_vmdir_copies_template_once(machine):
    vm = emu86box.prepare_vmdir(machine)
    assert vm == machine.state_dir
    assert (vm / "86box.cfg").read_text() == "[General]\nvid_resize = 0\n"
    # user edits persist: a second prepare must not overwrite
    (vm / "86box.cfg").write_text("[General]\nvid_resize = 1\n")
    emu86box.prepare_vmdir(machine)
    assert "vid_resize = 1" in (vm / "86box.cfg").read_text()


def test_apply_media_writes_absolute_path_to_mapped_key(machine):
    emu86box.prepare_vmdir(machine)
    emu86box.apply_media(machine)
    section, key = emu86box.SLOT_KEYS["floppy_a"]
    text = (machine.state_dir / "86box.cfg").read_text()
    expected = str((machine.path / "media" / "boot.img").resolve())
    assert f"[{section}]" in text
    assert f"{key} = {expected}" in text


def test_link_roms_creates_symlink(tmp_path):
    vm = tmp_path / "state"
    vm.mkdir()
    roms = tmp_path / "roms"
    roms.mkdir()
    emu86box.link_roms(vm, roms)
    assert (vm / "roms").is_symlink()
    assert (vm / "roms").resolve() == roms.resolve()
    emu86box.link_roms(vm, roms)  # idempotent, no error


def test_build_argv():
    assert emu86box.build_argv("/nix/store/x/bin/86Box", Path("/vm")) == [
        "/nix/store/x/bin/86Box", "-P", "/vm",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_driver_86box.py -v`
Expected: FAIL with import error for `vintage.drivers.emu86box`.

- [ ] **Step 3: Implement the driver**

`src/vintage/drivers/__init__.py`:
```python
"""Emulator drivers."""
```

`src/vintage/drivers/emu86box.py`:
```python
"""86Box driver: prepare the VM directory, wire ROMs and media, build argv."""

from __future__ import annotations

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
    link = vmdir / "roms"
    if link.is_symlink() or link.exists():
        return
    link.symlink_to(roms_path)


def build_argv(box_bin: str, vmdir: Path) -> list[str]:
    return [box_bin, "-P", str(vmdir)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_driver_86box.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/vintage/drivers/__init__.py src/vintage/drivers/emu86box.py tests/test_driver_86box.py
git commit -m "feat: 86Box driver — vmdir prep, rom link, media injection, argv"
```

---

### Task 6: CLI — `list`, `new`, `duplicate`

**Files:**
- Create: `src/vintage/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `discover_machines` (Task 3).
- Produces:
  - `machines_root(env: Mapping[str, str] | None = None) -> Path` — `VINTAGE_MACHINES` or `./machines`.
  - `cmd_list(root: Path, out: TextIO) -> int` — prints `id` and `name` per machine; `0`.
  - `cmd_new(root: Path, name: str) -> int` — scaffolds `root/<name>/` with `machine.toml`, empty `86box.cfg`, `media/`, `state/`; errors (`return 1`, message to stderr) if it exists.
  - `cmd_duplicate(root: Path, src: str, dst: str) -> int` — copies `root/src` to `root/dst` including `state/`; errors if `dst` exists or `src` missing.
  - `main(argv: list[str] | None = None) -> int` — argparse dispatcher for `list`/`new`/`duplicate` (and `run`, added in Task 7).

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
import io
from pathlib import Path
from vintage import cli


def test_machines_root_defaults_and_env(tmp_path):
    assert cli.machines_root({}) == Path("machines")
    assert cli.machines_root({"VINTAGE_MACHINES": str(tmp_path)}) == tmp_path


def test_cmd_list_prints_machines(machine_root):
    out = io.StringIO()
    rc = cli.cmd_list(machine_root, out)
    assert rc == 0
    text = out.getvalue()
    assert "optiplex-gx" in text
    assert "Dell OptiPlex GX" in text


def test_cmd_new_scaffolds_machine(tmp_path):
    rc = cli.cmd_new(tmp_path, "dos622")
    assert rc == 0
    d = tmp_path / "dos622"
    assert (d / "machine.toml").is_file()
    assert (d / "86box.cfg").is_file()
    assert (d / "media").is_dir()
    assert (d / "state").is_dir()


def test_cmd_new_refuses_existing(tmp_path, capsys):
    (tmp_path / "dup").mkdir()
    rc = cli.cmd_new(tmp_path, "dup")
    assert rc == 1
    assert "exists" in capsys.readouterr().err


def test_cmd_duplicate_copies_state(tmp_path):
    src = tmp_path / "src"
    (src / "state").mkdir(parents=True)
    (src / "media").mkdir()
    (src / "machine.toml").write_text('name = "S"\nemulator = "86box"\nconfig = "86box.cfg"\n')
    (src / "86box.cfg").write_text("[General]\n")
    (src / "state" / "hdd.img").write_text("disk")
    rc = cli.cmd_duplicate(tmp_path, "src", "dst")
    assert rc == 0
    assert (tmp_path / "dst" / "state" / "hdd.img").read_text() == "disk"


def test_main_list_dispatch(machine_root, capsys):
    rc = cli.main(["--machines", str(machine_root), "list"])
    assert rc == 0
    assert "optiplex-gx" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with import error for `vintage.cli`.

- [ ] **Step 3: Implement `src/vintage/cli.py` (list/new/duplicate + dispatcher; `run` stubbed until Task 7)**

```python
"""vintage command-line interface."""

from __future__ import annotations

import argparse
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
    return parser


def main(argv: list[str] | None = None) -> int:
    import os

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
    return 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (6 tests). (`run` is not exercised yet; `vintage.run` arrives in Task 7.)

- [ ] **Step 5: Commit**

```bash
git add src/vintage/cli.py tests/test_cli.py
git commit -m "feat: CLI list/new/duplicate with argparse dispatcher"
```

---

### Task 7: `run` — wire discovery, driver, and launch

**Files:**
- Create: `src/vintage/run.py`, `tests/test_run.py`

**Interfaces:**
- Consumes: `load_machine` (Task 3); `emu86box` driver (Task 5).
- Produces: `cmd_run(root: Path, machine_id: str, *, env: Mapping[str, str], runner: Callable[[list[str]], int] = _default_runner) -> int` — loads the machine, rejects non-`86box` emulators, prepares the vmdir, links ROMs from `VINTAGE_ROMS_86BOX`, applies media, resolves the binary from `VINTAGE_86BOX_BIN` (default `"86Box"`), and invokes `runner(argv)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_run.py`:
```python
from pathlib import Path
import pytest
from vintage import run


def _make_machine(root: Path):
    d = root / "optiplex-gx"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "media" / "boot.img").write_text("f")
    (d / "machine.toml").write_text(
        'name = "OptiPlex"\nemulator = "86box"\nconfig = "86box.cfg"\n'
        '[[media]]\nslot = "floppy_a"\nfile = "media/boot.img"\n'
    )
    (d / "86box.cfg").write_text("[General]\n")
    return d


def test_run_prepares_state_links_roms_and_calls_runner(tmp_path):
    _make_machine(tmp_path)
    roms = tmp_path / "roms-src"
    roms.mkdir()
    calls = []
    rc = run.cmd_run(
        tmp_path,
        "optiplex-gx",
        env={"VINTAGE_ROMS_86BOX": str(roms), "VINTAGE_86BOX_BIN": "/bin/86Box"},
        runner=lambda argv: calls.append(argv) or 0,
    )
    assert rc == 0
    vmdir = tmp_path / "optiplex-gx" / "state"
    assert calls == [["/bin/86Box", "-P", str(vmdir)]]
    assert (vmdir / "86box.cfg").is_file()          # template copied
    assert (vmdir / "roms").resolve() == roms.resolve()
    assert "boot.img" in (vmdir / "86box.cfg").read_text()  # media injected


def test_run_rejects_non_86box(tmp_path, capsys):
    d = tmp_path / "c64"
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text('name = "C64"\nemulator = "vice"\nconfig = "v.cfg"\n')
    (d / "v.cfg").write_text("")
    rc = run.cmd_run(tmp_path, "c64", env={}, runner=lambda argv: 0)
    assert rc == 1
    assert "vice" in capsys.readouterr().err


def test_run_errors_without_roms_env(tmp_path, capsys):
    _make_machine(tmp_path)
    rc = run.cmd_run(tmp_path, "optiplex-gx", env={}, runner=lambda argv: 0)
    assert rc == 1
    assert "VINTAGE_ROMS_86BOX" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_run.py -v`
Expected: FAIL with import error for `vintage.run`.

- [ ] **Step 3: Implement `src/vintage/run.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_run.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/vintage/run.py tests/test_run.py
git commit -m "feat: run command wires driver and launches 86Box"
```

---

### Task 8: Package the CLI in the flake and wire runtime env

**Files:**
- Modify: `flake.nix`

**Interfaces:**
- Consumes: `pyproject.toml` (Task 1); `emulator86box` and `roms86box` (Task 1).
- Produces: `packages.<system>.vintage` (a wrapped executable with `VINTAGE_86BOX_BIN` and `VINTAGE_ROMS_86BOX` baked in) and `apps.<system>.default` / `apps.<system>.vintage` pointing at it.

- [ ] **Step 1: Extend `flake.nix` to build and wrap the CLI**

Replace the `packages` output block with:
```nix
      packages = forAll (system: pkgs: rec {
        emulator86box = pkgs._86box;

        vintage-unwrapped = pkgs.python3Packages.buildPythonApplication {
          pname = "vintage";
          version = "0.1.0";
          src = ./.;
          pyproject = true;
          build-system = [ pkgs.python3Packages.setuptools ];
          # No runtime Python deps (stdlib only).
          doCheck = false;
        };

        vintage = pkgs.symlinkJoin {
          name = "vintage";
          paths = [ vintage-unwrapped ];
          nativeBuildInputs = [ pkgs.makeWrapper ];
          postBuild = ''
            wrapProgram $out/bin/vintage \
              --set VINTAGE_86BOX_BIN ${emulator86box}/bin/86Box \
              --set VINTAGE_ROMS_86BOX ${roms86box}
          '';
        };

        default = vintage;
      });

      apps = forAll (system: pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${system}.vintage}/bin/vintage";
        };
        vintage = self.apps.${system}.default;
      });
```
(Keep the existing `inputs` and `romsPath` output.)

- [ ] **Step 2: Verify the CLI builds and lists machines through Nix**

Run: `nix build --extra-experimental-features 'nix-command flakes' '.#vintage'`
Then: `nix run --extra-experimental-features 'nix-command flakes' '.#vintage' -- list`
Expected: builds; `list` prints `optiplex-gx    Dell OptiPlex GX — Pentium II`.

- [ ] **Step 3: Verify env wiring is baked in**

Run: `grep -o 'VINTAGE_[A-Z0-9_]*' $(nix build --print-out-paths --extra-experimental-features 'nix-command flakes' '.#vintage')/bin/vintage | sort -u`
Expected: `VINTAGE_86BOX_BIN` and `VINTAGE_ROMS_86BOX` present in the wrapper.

- [ ] **Step 4: Commit**

```bash
git add flake.nix flake.lock
git commit -m "feat: package vintage CLI in flake with baked-in emulator and rom paths"
```

---

### Task 9: End-to-end boot verification and README

This task proves the milestone's definition of done on real hardware emulation and documents usage. The boot itself is manual (needs user-provided media and a GUI); the steps below are the acceptance script.

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: user-facing docs; a verified working OptiPlex.

- [ ] **Step 1: Drop in media and boot**

The user places their own images into `machines/optiplex-gx/media/` (e.g. `dos-boot.img`, `win98se.iso`) matching the `machine.toml` slots, then:
```bash
nix run --extra-experimental-features 'nix-command flakes' '.#vintage' -- run optiplex-gx
```
Expected: 86Box opens, the modeled Pentium II POSTs, and boots from the inserted floppy/CD. Install DOS / Windows 98 live. Shut down.

- [ ] **Step 2: Verify persistence**

Confirm `machines/optiplex-gx/state/` now holds the hard-disk image and `nvr/`. Run `run optiplex-gx` again.
Expected: boots straight into the installed system. Confirm `git status` shows nothing under `state/` or `media/` staged (gitignore working).

- [ ] **Step 3: Verify duplication**

Run:
```bash
nix run '.#vintage' -- duplicate optiplex-gx optiplex-clone
nix run '.#vintage' -- run optiplex-clone
```
Expected: the clone boots the same installed system independently; changes in one do not affect the other.

- [ ] **Step 4: Write `README.md` (English)**

Cover: what the project is; requirements (Nix with flakes); quick start (`nix run .#vintage -- list` / `run <id>`); the machine-folder format (`machine.toml` + native `<emulator>.cfg`, `media/`, `state/`); how to add media; how to duplicate (CLI or `cp -r`); a clear note that OS/BIOS/ROM images are **not** distributed and users must supply media for hardware they own; and a short roadmap (web frontend, remote access, more emulators). No non-English text.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage, machine format, and legal note"
```

---

## Self-Review

**Spec coverage:**
- Replicable / multi-OS via flake → Tasks 1, 8 (flake for the three systems, no OS-specific code).
- Model the whole machine (86Box) → Task 2 authors real Pentium II hardware.
- Self-contained per machine, `cp -r` duplication → Tasks 3, 6 (`duplicate`), 9 (verify).
- Persistent state → Task 5 (`state/` vmdir), 9 (verify).
- Extensible (drivers/machines) → Task 5 driver seam, `SLOT_KEYS`, emulator dispatch in Task 7.
- Public repo, English, no copyrighted binaries → `.gitignore` (Task 1), README legal note (Task 9), ROMs via flake input (Tasks 1–2).
- `_86box` rename + ROM approach (spike outcome) → Tasks 1, 2, 8.
- Hybrid config (machine.toml metadata + native cfg) → Tasks 3, 4, 5.
- Testing (golden cfg + smoke) → Tasks 4, 6, 7.
- Future layers unblocked → CLI/driver seam keeps `run` a thin wrapper a frontend can call.

**Placeholder scan:** No TBD/TODO in code. Task 2 (spike) and Task 9 (manual boot) are intentionally exploratory/acceptance tasks with concrete commands and recorded outputs, not placeholders. The one deliberate uncertainty — exact 86Box cfg media keys and ROM-location mechanism — is isolated to Task 2's recorded facts and Task 5's `SLOT_KEYS`, with an explicit reconciliation instruction rather than a vague "figure it out".

**Type consistency:** `Machine`/`Media` fields and `state_dir`/`media_dir` properties are used identically across Tasks 3, 5, 7. Driver functions (`prepare_vmdir`, `apply_media`, `link_roms`, `build_argv`) and `SLOT_KEYS` match between Task 5's definition and Task 7's use. `cmd_run` signature matches between Task 7 (definition) and Task 6 (call site in `cli.main`). `machines_root`/`cmd_*` signatures consistent across Task 6 and its tests.
