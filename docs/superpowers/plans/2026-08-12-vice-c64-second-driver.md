# C64 via VICE (Second Driver) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Commodore 64 (VICE / `x64sc`) as a second emulator, proving the launcher's driver abstraction by replacing the hardcoded `86box` dispatch with a real driver registry.

**Architecture:** Each driver exposes one entry point `run(machine, *, env, runner) -> int` and owns its full lifecycle (prepare VM dir, wire ROMs/media, validate its own env, build argv, invoke the runner). `run.py` becomes a thin registry dispatcher keyed by `machine.emulator`. The VICE driver bundles ROMs (none wired) and attaches media as CLI flags (`-8 disk.d64`), in contrast to 86Box which injects media by editing its `.cfg`.

**Tech Stack:** Python 3.11 (stdlib only), pytest, Nix flake, VICE (`x64sc`), 86Box.

## Global Constraints

- Python **3.11+**, **standard library only** — no runtime third-party dependencies (`pyproject.toml` `dependencies = []`).
- All code, comments, and docs in **English**.
- **No copyrighted ROMs or media in git.** VICE bundles C64 ROMs (none added). `media/` and `state/` contents stay gitignored (existing `.gitignore` rules cover this; only `.gitkeep` is tracked).
- Behavior-preserving for the existing 86Box path: `vintage run optiplex-gx` and all current tests keep working.
- Driver entry-point signature is exactly `run(machine: Machine, *, env: Mapping[str, str], runner: Callable[[list[str]], int]) -> int`.
- Run the test suite from the repo root with `PYTHONPATH=src pytest` (see `.envrc` / devShell; the package lives under `src/`).

---

### Task 1: Driver registry + `emu86box.run()` (behavior-preserving)

Open the first seam: move 86Box-specific env handling out of the core and into the 86Box driver, and turn `run.py` into a registry dispatcher. After this task only `86box` is registered; an unknown emulator errors with the supported set. All existing tests stay green.

**Files:**
- Modify: `src/vintage/drivers/emu86box.py` (add `run()`)
- Modify: `src/vintage/run.py` (replace hardcoded branch with registry)
- Test: `tests/test_run.py` (add unknown-emulator test; existing tests unchanged)

**Interfaces:**
- Produces: `emu86box.run(machine, *, env, runner) -> int` — validates `VINTAGE_ROMS_86BOX`, reads `VINTAGE_86BOX_BIN` (default `"86Box"`), prepares the VM dir, links ROMs, applies media, calls `runner(argv)`.
- Produces: `run.DRIVERS: dict[str, Callable]` — registry mapping emulator name → driver `run`.
- Consumes: existing `emu86box.prepare_vmdir/link_roms/apply_media/build_argv`, `machine.load_machine`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_run.py`:

```python
def test_run_unknown_emulator_lists_supported(tmp_path, capsys):
    d = tmp_path / "amiga"
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "Amiga"\nemulator = "fs-uae"\nconfig = "c.cfg"\n'
    )
    (d / "c.cfg").write_text("")
    rc = run.cmd_run(tmp_path, "amiga", env={}, runner=lambda argv: 0)
    assert rc == 1
    err = capsys.readouterr().err
    assert "fs-uae" in err
    assert "86box" in err  # supported set is listed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_run.py::test_run_unknown_emulator_lists_supported -v`
Expected: FAIL — current `cmd_run` prints `unsupported emulator 'fs-uae'` but does not list the supported set, so `assert "86box" in err` fails.

- [ ] **Step 3: Add `run()` to the 86Box driver**

In `src/vintage/drivers/emu86box.py`, update the imports at the top:

```python
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Mapping

from ..cfg import set_values
from ..machine import Machine
```

Append this function at the end of the module:

```python
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
```

- [ ] **Step 4: Convert `run.py` to a registry dispatcher**

Replace the entire contents of `src/vintage/run.py` with:

```python
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
```

- [ ] **Step 5: Run the full suite to verify green**

Run: `PYTHONPATH=src pytest -q`
Expected: PASS. The new test passes; `test_run_prepares_state_links_roms_and_calls_runner`, `test_run_errors_without_roms_env`, and `test_run_rejects_non_86box` still pass (an unregistered `vice` is rejected as an unknown emulator, and `'vice'` still appears in the error message).

- [ ] **Step 6: Commit**

```bash
git add src/vintage/drivers/emu86box.py src/vintage/run.py tests/test_run.py
git commit -m "refactor(run): driver registry; move 86box env handling into its driver"
```

---

### Task 2: VICE driver module

Add the VICE driver as an isolated, fully unit-tested module. Not yet wired into the registry (that is Task 3), so it changes no dispatch behavior. Media is attached as CLI flags; the native config (`machine.config`, e.g. `vicerc`) is copied into `state/` once and passed via `-config`.

**Files:**
- Create: `src/vintage/drivers/vice.py`
- Test: `tests/test_driver_vice.py`

**Interfaces:**
- Produces: `vice.prepare_vmdir(machine) -> Path` — ensures `state/` exists and copies `machine.config` into it once (never overwrites).
- Produces: `vice.media_args(machine) -> list[str]` — maps each `[[media]]` entry to VICE flags via `SLOT_FLAGS`; absolute paths; warns on missing file; raises `ValueError` on unknown slot.
- Produces: `vice.build_argv(vice_bin, config_path, media) -> list[str]` → `[vice_bin, "-config", <abs config>, *media]`.
- Produces: `vice.run(machine, *, env, runner) -> int` — reads `VINTAGE_VICE_BIN` (default `"x64sc"`), prepares the VM dir, builds argv, calls runner. No ROMs are wired (VICE bundles them).
- Produces: `vice.SLOT_FLAGS: dict[str, str]` — `{"drive8": "-8"}`.
- Consumes: `machine.Machine` (`state_dir`, `config`, `path`, `media`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_driver_vice.py`:

```python
from pathlib import Path
import pytest
from vintage.machine import load_machine
from vintage.drivers import vice


def _make_c64(root: Path, *, media: str = "") -> Path:
    d = root / "c64"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "Commodore 64"\nemulator = "vice"\nconfig = "vicerc"\n' + media
    )
    (d / "vicerc").write_text("# bare C64\n")
    return d


def test_prepare_vmdir_copies_template_once(tmp_path):
    m = load_machine(_make_c64(tmp_path))
    vm = vice.prepare_vmdir(m)
    assert vm == m.state_dir
    assert (vm / "vicerc").read_text() == "# bare C64\n"
    # User edits to the working copy must survive a second prepare.
    (vm / "vicerc").write_text("# edited\n")
    vice.prepare_vmdir(m)
    assert (vm / "vicerc").read_text() == "# edited\n"


def test_media_args_maps_drive8_to_flag_with_absolute_path(tmp_path):
    m = load_machine(
        _make_c64(
            tmp_path,
            media='[[media]]\nslot = "drive8"\nfile = "media/demo.d64"\n',
        )
    )
    (m.path / "media" / "demo.d64").write_text("d64")
    args = vice.media_args(m)
    expected = str((m.path / "media" / "demo.d64").resolve())
    assert args == ["-8", expected]
    assert Path(args[1]).is_absolute()


def test_media_args_warns_on_missing_file_but_still_emits_flag(tmp_path, capsys):
    m = load_machine(
        _make_c64(
            tmp_path,
            media='[[media]]\nslot = "drive8"\nfile = "media/missing.d64"\n',
        )
    )
    args = vice.media_args(m)  # file deliberately absent
    assert args[0] == "-8"
    assert "missing.d64" in capsys.readouterr().err


def test_media_args_unknown_slot_raises(tmp_path):
    m = load_machine(
        _make_c64(
            tmp_path,
            media='[[media]]\nslot = "tape"\nfile = "media/x.tap"\n',
        )
    )
    with pytest.raises(ValueError, match="tape"):
        vice.media_args(m)


def test_build_argv_has_config_then_media(tmp_path):
    cfg = tmp_path / "state" / "vicerc"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("# c\n")
    argv = vice.build_argv("x64sc", cfg, ["-8", "/abs/demo.d64"])
    assert argv == ["x64sc", "-config", str(cfg.resolve()), "-8", "/abs/demo.d64"]


def test_run_dispatches_with_default_binary(tmp_path):
    m = load_machine(_make_c64(tmp_path))
    calls = []
    rc = vice.run(m, env={}, runner=lambda argv: calls.append(argv) or 0)
    assert rc == 0
    cfg = (m.state_dir / "vicerc").resolve()
    assert calls == [["x64sc", "-config", str(cfg)]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_driver_vice.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vintage.drivers.vice'`.

- [ ] **Step 3: Write the VICE driver**

Create `src/vintage/drivers/vice.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_driver_vice.py -v`
Expected: PASS (all six tests).

- [ ] **Step 5: Commit**

```bash
git add src/vintage/drivers/vice.py tests/test_driver_vice.py
git commit -m "feat(drivers): add VICE driver (bundled ROMs, media via argv)"
```

---

### Task 3: Register VICE in the dispatcher

Wire the VICE driver into the registry so `vintage run <c64>` dispatches to it. Rewrite the now-obsolete `test_run_rejects_non_86box` (which asserted `vice` is rejected) into a positive dispatch test.

**Files:**
- Modify: `src/vintage/run.py` (import + register `vice`)
- Test: `tests/test_run.py` (replace the reject test with a dispatch test)

**Interfaces:**
- Consumes: `vice.run` (Task 2), `emu86box.run` (Task 1).
- Produces: `run.DRIVERS == {"86box": emu86box.run, "vice": vice.run}`.

- [ ] **Step 1: Replace the reject test with a dispatch test**

In `tests/test_run.py`, delete `test_run_rejects_non_86box` and add:

```python
def test_run_dispatches_vice_and_builds_config_argv(tmp_path):
    d = tmp_path / "c64"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "C64"\nemulator = "vice"\nconfig = "vicerc"\n'
    )
    (d / "vicerc").write_text("# bare C64\n")
    calls = []
    rc = run.cmd_run(
        tmp_path,
        "c64",
        env={"VINTAGE_VICE_BIN": "/bin/x64sc"},
        runner=lambda argv: calls.append(argv) or 0,
    )
    assert rc == 0
    vmdir = tmp_path / "c64" / "state"
    assert calls == [["/bin/x64sc", "-config", str((vmdir / "vicerc").resolve())]]
    assert (vmdir / "vicerc").is_file()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_run.py::test_run_dispatches_vice_and_builds_config_argv -v`
Expected: FAIL with rc 1 — `vice` is not yet in `DRIVERS`, so `cmd_run` reports an unsupported emulator instead of dispatching.

- [ ] **Step 3: Register the VICE driver**

In `src/vintage/run.py`, update the import and registry:

```python
from .drivers import emu86box, vice
```

```python
DRIVERS: dict[str, Callable[..., int]] = {
    "86box": emu86box.run,
    "vice": vice.run,
}
```

- [ ] **Step 4: Run the full suite to verify green**

Run: `PYTHONPATH=src pytest -q`
Expected: PASS across all test files.

- [ ] **Step 5: Commit**

```bash
git add src/vintage/run.py tests/test_run.py
git commit -m "feat(run): register VICE driver in the dispatch registry"
```

---

### Task 4: Ship the `c64` machine folder

Add a ready-to-run C64 machine to the repo. With no `[[media]]`, `vintage run c64` boots to the BASIC `READY.` prompt with zero user files. The versioned `vicerc` is comment-only; VICE writes its defaults into the gitignored working copy `state/vicerc`.

**Files:**
- Create: `machines/c64/machine.toml`
- Create: `machines/c64/vicerc`
- Create: `machines/c64/media/.gitkeep`
- Create: `machines/c64/state/.gitkeep`
- Test: `tests/test_machine.py` (guard the shipped folder)

**Interfaces:**
- Consumes: `machine.load_machine`, `machine.discover_machines`.

- [ ] **Step 1: Write the failing guard test**

Add to `tests/test_machine.py` (note the existing imports already cover `load_machine`):

```python
def test_shipped_c64_machine_loads():
    repo_machines = Path(__file__).resolve().parents[1] / "machines"
    m = load_machine(repo_machines / "c64")
    assert m.emulator == "vice"
    assert m.config == "vicerc"
    assert m.media == ()  # boots to READY. with no user media
    assert (repo_machines / "c64" / "vicerc").is_file()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_machine.py::test_shipped_c64_machine_loads -v`
Expected: FAIL — `machines/c64/` does not exist yet (`FileNotFoundError` reading `machine.toml`).

- [ ] **Step 3: Create the machine folder**

Create `machines/c64/machine.toml`:

```toml
name     = "Commodore 64"
emulator = "vice"
config   = "vicerc"

# Optional: attach a disk image in drive 8 (user-provided, gitignored).
# [[media]]
# slot = "drive8"
# file = "media/demo.d64"
```

Create `machines/c64/vicerc`:

```
# VICE configuration for a bare Commodore 64 (x64sc).
# Hardware defaults come from VICE. The launcher copies this file into the
# machine's gitignored state/ on first run; VICE reads and writes that working
# copy, so runtime tweaks persist there without touching this template.
```

Create the two placeholders (empty files):

```bash
: > machines/c64/media/.gitkeep
: > machines/c64/state/.gitkeep
```

- [ ] **Step 4: Verify the guard test passes and the machine is discoverable**

Run: `PYTHONPATH=src pytest tests/test_machine.py::test_shipped_c64_machine_loads -v`
Expected: PASS.

Run: `PYTHONPATH=src python -m vintage.cli --machines machines list`
Expected output (order sorted): includes both lines —
```
c64	Commodore 64
optiplex-gx	Dell OptiPlex GX — Pentium II
```

- [ ] **Step 5: Confirm gitignore keeps media/state contents out**

Run: `git add machines/c64 && git status --short machines/c64`
Expected: staged files are exactly `machine.toml`, `vicerc`, `media/.gitkeep`, `state/.gitkeep` — no other files under `media/` or `state/`. (Existing `.gitignore` rules `**/media/*` and `**/state/*` with `.gitkeep` negations already cover this; no `.gitignore` change is needed.)

- [ ] **Step 6: Commit**

```bash
git add machines/c64 tests/test_machine.py
git commit -m "feat(machines): ship a bare Commodore 64 machine (boots to READY.)"
```

---

### Task 5: `vintage new --emulator`

Remove the last hardcoded `86box` assumption from the CLI: `vintage new` picks the native config filename and starter body per emulator, defaulting to `86box` so current behavior is preserved.

**Files:**
- Modify: `src/vintage/cli.py` (`cmd_new`, template, parser, `main` dispatch)
- Test: `tests/test_cli.py` (add VICE and unknown-emulator cases)

**Interfaces:**
- Produces: `cli.cmd_new(root, name, emulator="86box") -> int`.
- Produces: `cli._EMULATOR_TEMPLATES: dict[str, tuple[str, str]]` — emulator → (config filename, starter body).
- Consumes: `argparse` (adds `--emulator` to the `new` subcommand).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_cmd_new_vice_scaffolds_vicerc(tmp_path):
    rc = cli.cmd_new(tmp_path, "c64", emulator="vice")
    assert rc == 0
    d = tmp_path / "c64"
    toml = (d / "machine.toml").read_text()
    assert 'emulator = "vice"' in toml
    assert 'config   = "vicerc"' in toml
    assert (d / "vicerc").is_file()
    assert not (d / "86box.cfg").exists()


def test_cmd_new_rejects_unknown_emulator(tmp_path, capsys):
    rc = cli.cmd_new(tmp_path, "x", emulator="atari")
    assert rc == 1
    assert "atari" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_main_new_emulator_flag(tmp_path):
    rc = cli.main(["--machines", str(tmp_path), "new", "c64", "--emulator", "vice"])
    assert rc == 0
    assert (tmp_path / "c64" / "vicerc").is_file()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_cli.py -k "vice or unknown_emulator or emulator_flag" -v`
Expected: FAIL — `cmd_new` takes no `emulator` argument (`TypeError`), and the `new` subcommand has no `--emulator` flag.

- [ ] **Step 3: Update `cli.py`**

In `src/vintage/cli.py`, replace the `_TEMPLATE_TOML` constant (lines 14–18) with:

```python
# Emulator -> (native config filename, starter config body).
_EMULATOR_TEMPLATES: dict[str, tuple[str, str]] = {
    "86box": ("86box.cfg", "[General]\n"),
    "vice": (
        "vicerc",
        "# VICE configuration; hardware defaults come from VICE.\n",
    ),
}


def _machine_toml(name: str, emulator: str, config: str) -> str:
    return (
        f'name     = "{name}"\n'
        f'emulator = "{emulator}"\n'
        f'config   = "{config}"\n'
    )
```

Replace `cmd_new` with:

```python
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
    config_name, config_body = template
    (dest / "media").mkdir(parents=True)
    (dest / "state").mkdir(parents=True)
    (dest / "machine.toml").write_text(_machine_toml(name, emulator, config_name))
    (dest / config_name).write_text(config_body)
    return 0
```

In `_build_parser`, add the flag to the `new` subcommand (after `p_new.add_argument("name")`):

```python
    p_new.add_argument(
        "--emulator",
        default="86box",
        choices=sorted(_EMULATOR_TEMPLATES),
        help="emulator for the new machine (default: 86box)",
    )
```

In `main`, update the `new` dispatch:

```python
    if args.command == "new":
        return cmd_new(root, args.name, args.emulator)
```

- [ ] **Step 4: Run the full suite to verify green**

Run: `PYTHONPATH=src pytest -q`
Expected: PASS. The new tests pass and `test_cmd_new_scaffolds_machine` (default emulator `86box`) is unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/vintage/cli.py tests/test_cli.py
git commit -m "feat(cli): vintage new --emulator {86box,vice}"
```

---

### Task 6: Flake wiring + end-to-end verification

Pin VICE in the flake and wire `VINTAGE_VICE_BIN`, then verify the whole thing builds and boots. This task resolves the primary technical risk (VICE on `aarch64-darwin`).

**Files:**
- Modify: `flake.nix` (add `vice` package, wrap `VINTAGE_VICE_BIN`)
- Modify: `docs/86box-runtime-notes.md` → add a sibling note, or create `docs/vice-runtime-notes.md` recording verified facts.

**Interfaces:**
- Produces: the `vintage` wrapper sets `VINTAGE_VICE_BIN=<vice>/bin/x64sc`.

- [ ] **Step 1: Wire VICE into the flake**

In `flake.nix`, inside the `packages = forAll (system: pkgs: rec {` block, add next to `emulator86box`:

```nix
        emulatorVice = pkgs.vice;
```

Extend the `wrapProgram` call in the `vintage` derivation's `postBuild` to add one line before the `--prefix PATH` line:

```nix
              --set VINTAGE_VICE_BIN ${emulatorVice}/bin/x64sc \
```

So the wrapper reads:

```nix
          postBuild = ''
            wrapProgram $out/bin/vintage \
              --set VINTAGE_86BOX_BIN ${emulator86box}/bin/86Box \
              --set VINTAGE_ROMS_86BOX ${roms86box} \
              --set VINTAGE_VICE_BIN ${emulatorVice}/bin/x64sc \
              --prefix PATH : ${pkgs.mtools}/bin
          '';
```

- [ ] **Step 2: Verify the flake evaluates and VICE is available for this system**

Run: `nix flake check --no-build 2>&1 | tail -20` (evaluation only) and then confirm the VICE package resolves:
Run: `nix eval --raw .#packages.$(nix eval --impure --raw --expr 'builtins.currentSystem').emulatorVice.outPath 2>&1 | tail -5`
Expected: prints a `/nix/store/...vice...` path (evaluation succeeds).

If VICE does not evaluate/build on `aarch64-darwin`, STOP and record the failure in the runtime notes (Step 5); this is the known risk and the user must decide how to proceed (e.g. build from a different channel). Do not fake success.

- [ ] **Step 3: Build the wrapper (pulls VICE) and smoke-test the CLI**

Run: `nix build .#vintage 2>&1 | tail -20`
Expected: builds without error (fetches/builds `vice`).

Run: `./result/bin/vintage --machines machines list`
Expected: lists both `c64` and `optiplex-gx`.

Run: `./result/bin/vintage --machines machines run c64 &` then observe, or launch directly:
Run: `VINTAGE_VICE_BIN=$(nix eval --raw .#packages.$(nix eval --impure --raw --expr 'builtins.currentSystem').emulatorVice.outPath)/bin/x64sc PYTHONPATH=src python -m vintage.cli --machines machines run c64`
Expected: `x64sc` opens and the C64 boots to the blue `READY.` BASIC screen. (This is a GUI step; the user confirms visually. Close the emulator window to exit.)

- [ ] **Step 4: Run the full test suite one final time**

Run: `PYTHONPATH=src pytest -q`
Expected: PASS, whole suite.

- [ ] **Step 5: Record verified runtime facts**

Create `docs/vice-runtime-notes.md` capturing what was confirmed on this host:

```markdown
# VICE runtime notes

Facts recorded while wiring the C64 machine against VICE on <system>.

## Binary
The C64 emulator binary is `x64sc` (cycle-accurate). The flake wires
`VINTAGE_VICE_BIN = ${pkgs.vice}/bin/x64sc`.

## ROMs
VICE bundles the C64 KERNAL/BASIC/CHARGEN ROMs; `x64sc` locates them via its
own data directory (wrapped in by nixpkgs). No ROM env var or symlink is needed
— the contrast with the 86Box driver.

## Config / persistence
`x64sc -config <state/vicerc>` reads and writes that file. The launcher copies
the versioned template into the machine's gitignored `state/` on first run, so
runtime tweaks persist there. Media is attached on the command line (`-8
<disk.d64>`), not via the config file.

## Verified on <system>
- `nix build .#vintage` succeeds and pulls `vice`.
- `vintage run c64` boots to the READY. prompt with no user media.
```

Fill `<system>` with the actual platform and note any deviations discovered (e.g. an explicit data-dir flag if `x64sc` could not find its ROMs).

- [ ] **Step 6: Commit**

```bash
git add flake.nix docs/vice-runtime-notes.md
git commit -m "feat(flake): pin VICE and wire VINTAGE_VICE_BIN; add runtime notes"
```

---

## Self-Review Notes

- **Spec coverage:** registry refactor (Task 1) → spec §"Driver registry"; VICE driver incl. bundled ROMs + media-as-argv (Task 2) → spec §"VICE driver"; registration + dispatch test rewrite (Task 3) → spec §Testing; shipped `c64` machine (Task 4) → spec §"c64 machine folder" + DoD; `vintage new --emulator` (Task 5) → spec §"vintage new --emulator"; flake wiring + darwin-risk verification + runtime notes (Task 6) → spec §"Flake wiring" + §Risks.
- **Behavior preservation:** 86Box path unchanged; `test_run_prepares_state_links_roms_and_calls_runner`, `test_run_errors_without_roms_env`, `test_cmd_new_scaffolds_machine` remain valid. The only intentionally removed test is `test_run_rejects_non_86box` (its premise — vice is unsupported — is exactly what this work reverses), replaced in Task 3.
- **Type consistency:** driver entry point `run(machine, *, env, runner) -> int` is identical for `emu86box` and `vice`; `DRIVERS` values are those callables; `cmd_run` calls `driver(machine, env=env, runner=runner)`.
- **No copyrighted assets:** no ROM inputs added; `media/`/`state/` contents remain gitignored; only `.gitkeep`, `machine.toml`, and the comment-only `vicerc` are committed.
