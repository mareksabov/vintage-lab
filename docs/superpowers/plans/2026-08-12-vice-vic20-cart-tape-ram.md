# VIC-20 via VICE + cart/tape/RAM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Commodore VIC-20 machine (VICE `xvic`) and extend the shared VICE driver with cartridge, tape and RAM-expansion support, so both `c64` and `vic20` gain them.

**Architecture:** The VICE driver selects its binary from the machine's declared `model` (`x64sc`/`xvic`) joined onto a wrapped VICE `bin/` directory. A generic `options` mapping on `Machine` carries `model` and `ram` from `machine.toml`; the driver reads them. New media slots (`tape`, `cart`, `autostart`) extend the existing slot→flag map; the `ram` knob maps per-model to `-memory`/`-reu` flags.

**Tech Stack:** Python 3.11 (stdlib only, `tomllib`), pytest, Nix flake, VICE 3.9.

## Global Constraints

- Python 3.11, standard library only — no new runtime dependencies.
- No copyrighted ROMs, OS images, or disk/tape/cart media in git.
- Docs and code comments in English.
- Behavior-preserving for the 86Box path and for the committed `c64` boot-to-`READY.` path.
- VICE binaries live in one `bin/` dir per platform: `${pkgs.vice}/bin` (Linux), `${vice-macos}/vice/bin` (aarch64-darwin). Verified present: `x64sc`, `xvic`.
- Verified VICE 3.9 flags (both `x64sc` and `xvic` unless noted): `-8`, `-1`, `-cartcrt`, `-autostart`, `-config`, and `-memory <none|3k|8k|16k|24k|all>` (xvic), `-reu` (x64sc).

---

### Task 1: Generic `options` mapping on `Machine`

**Files:**
- Modify: `src/vintage/machine.py`
- Test: `tests/test_machine.py`

**Interfaces:**
- Produces: `Machine.options: Mapping[str, object]` — all top-level `machine.toml` keys except the known core keys (`name`, `emulator`, `config`, `media`). Excluded from dataclass comparison/hash.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_machine.py`:

```python
def test_load_machine_captures_extra_keys_in_options(tmp_path):
    d = tmp_path / "vic20"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "VIC-20"\nemulator = "vice"\nmodel = "vic20"\n'
        'config = "vicerc"\nram = "24k"\n'
    )
    (d / "vicerc").write_text("# bare\n")
    m = load_machine(d)
    assert m.options == {"model": "vic20", "ram": "24k"}


def test_load_machine_without_extra_keys_has_empty_options(machine_root):
    m = load_machine(machine_root / "optiplex-gx")
    assert m.options == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `nix develop -c pytest tests/test_machine.py::test_load_machine_captures_extra_keys_in_options -v`
Expected: FAIL — `Machine` has no attribute `options`.

- [ ] **Step 3: Write minimal implementation**

In `src/vintage/machine.py`, add `field` to the dataclasses import and a compare-excluded `options` field, then populate it in `load_machine`:

```python
from dataclasses import dataclass, field
```

Add to the `Machine` dataclass (after `media`):

```python
    options: Mapping[str, object] = field(default_factory=dict, compare=False)
```

Add the import at the top:

```python
from typing import Mapping
```

In `load_machine`, after building `media`, compute options and pass it:

```python
    core = {"name", "emulator", "config", "media"}
    options = {k: v for k, v in data.items() if k not in core}
    return Machine(
        id=path.name,
        path=path,
        name=data["name"],
        emulator=data["emulator"],
        config=data["config"],
        media=media,
        options=options,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `nix develop -c pytest tests/test_machine.py -v`
Expected: PASS (all machine tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add src/vintage/machine.py tests/test_machine.py
git commit -m "feat(machine): capture non-core machine.toml keys in options mapping"
```

---

### Task 2: Model → VICE binary resolution

**Files:**
- Modify: `src/vintage/drivers/vice.py`
- Test: `tests/test_driver_vice.py`, `tests/test_run.py`

**Interfaces:**
- Consumes: `Machine.options` (Task 1).
- Produces:
  - `MODEL_BINARIES: dict[str, str]` = `{"c64": "x64sc", "vic20": "xvic"}`.
  - `resolve_binary(model: str, env: Mapping[str, str]) -> str` — returns `<VINTAGE_VICE_BIN_DIR>/<binary>` when the env var is set, else the bare binary name; raises `ValueError` for an unknown model.
  - `run(...)` now derives `model = machine.options.get("model", "c64")` and uses `resolve_binary`. The env var is `VINTAGE_VICE_BIN_DIR` (replaces `VINTAGE_VICE_BIN`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_driver_vice.py`:

```python
def test_resolve_binary_c64_and_vic20_join_bin_dir():
    env = {"VINTAGE_VICE_BIN_DIR": "/opt/vice/bin"}
    assert vice.resolve_binary("c64", env) == "/opt/vice/bin/x64sc"
    assert vice.resolve_binary("vic20", env) == "/opt/vice/bin/xvic"


def test_resolve_binary_falls_back_to_bare_name_without_env():
    assert vice.resolve_binary("vic20", {}) == "xvic"


def test_resolve_binary_unknown_model_raises():
    with pytest.raises(ValueError, match="unknown vice model"):
        vice.resolve_binary("plus4", {})


def test_run_uses_vic20_binary_from_model(tmp_path):
    d = tmp_path / "vic20"
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "VIC-20"\nemulator = "vice"\nmodel = "vic20"\nconfig = "vicerc"\n'
    )
    (d / "vicerc").write_text("# bare\n")
    m = load_machine(d)
    calls = []
    rc = vice.run(
        m,
        env={"VINTAGE_VICE_BIN_DIR": "/opt/vice/bin"},
        runner=lambda argv: calls.append(argv) or 0,
    )
    assert rc == 0
    cfg = (m.state_dir / "vicerc").resolve()
    assert calls == [["/opt/vice/bin/xvic", "-config", str(cfg)]]
```

Update the existing `test_run_dispatches_with_default_binary` (env-less default is still `x64sc` via the c64 fallback — no change needed to its body; keep it).

Update `tests/test_run.py::test_run_dispatches_vice_and_builds_config_argv` to the new env var:

```python
    rc = run.cmd_run(
        tmp_path,
        "c64",
        env={"VINTAGE_VICE_BIN_DIR": "/bin"},
        runner=lambda argv: calls.append(argv) or 0,
    )
    assert rc == 0
    vmdir = tmp_path / "c64" / "state"
    assert calls == [["/bin/x64sc", "-config", str((vmdir / "vicerc").resolve())]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `nix develop -c pytest tests/test_driver_vice.py -k resolve_binary -v`
Expected: FAIL — `resolve_binary` not defined.

- [ ] **Step 3: Write minimal implementation**

In `src/vintage/drivers/vice.py`, add near the top (after `SLOT_FLAGS`):

```python
# VICE machine model -> emulator binary name (all live in one bin/ dir).
MODEL_BINARIES: dict[str, str] = {
    "c64": "x64sc",
    "vic20": "xvic",
}


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
```

Replace the binary lookup in `run` (currently `vice_bin = env.get("VINTAGE_VICE_BIN", "x64sc")`):

```python
    model = str(machine.options.get("model", "c64"))
    vice_bin = resolve_binary(model, env)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `nix develop -c pytest tests/test_driver_vice.py tests/test_run.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vintage/drivers/vice.py tests/test_driver_vice.py tests/test_run.py
git commit -m "feat(vice): select emulator binary from machine model (x64sc/xvic)"
```

---

### Task 3: Cartridge, tape and autostart media slots

**Files:**
- Modify: `src/vintage/drivers/vice.py`
- Test: `tests/test_driver_vice.py`

**Interfaces:**
- Produces: extended `SLOT_FLAGS` = `{"drive8": "-8", "tape": "-1", "cart": "-cartcrt", "autostart": "-autostart"}`. `media_args` unchanged in signature.

- [ ] **Step 1: Write the failing tests**

The existing `test_media_args_unknown_slot_raises` uses `slot = "tape"` as its "unknown" example — `tape` is now valid, so change that test's slot to a truly unknown one and add coverage for the new slots. Replace that test and add:

```python
def test_media_args_unknown_slot_raises(tmp_path):
    m = load_machine(
        _make_c64(
            tmp_path,
            media='[[media]]\nslot = "printer"\nfile = "media/x.bin"\n',
        )
    )
    with pytest.raises(ValueError, match="printer"):
        vice.media_args(m)


@pytest.mark.parametrize(
    "slot,flag,fname",
    [
        ("tape", "-1", "game.tap"),
        ("cart", "-cartcrt", "game.crt"),
        ("autostart", "-autostart", "game.prg"),
    ],
)
def test_media_args_new_slots_map_to_flags(tmp_path, slot, flag, fname):
    m = load_machine(
        _make_c64(
            tmp_path,
            media=f'[[media]]\nslot = "{slot}"\nfile = "media/{fname}"\n',
        )
    )
    (m.path / "media" / fname).write_text("x")
    args = vice.media_args(m)
    expected = str((m.path / "media" / fname).resolve())
    assert args == [flag, expected]
    assert Path(args[1]).is_absolute()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `nix develop -c pytest tests/test_driver_vice.py -k "new_slots or unknown_slot" -v`
Expected: FAIL — new slots raise `ValueError` (not yet in `SLOT_FLAGS`).

- [ ] **Step 3: Write minimal implementation**

In `src/vintage/drivers/vice.py`, extend `SLOT_FLAGS`:

```python
# Media slot -> VICE command-line flag. Flags are identical in x64sc and xvic.
SLOT_FLAGS: dict[str, str] = {
    "drive8": "-8",          # disk image in drive 8
    "tape": "-1",            # datasette tape image (attach; load by hand)
    "cart": "-cartcrt",      # CRT-format cartridge image
    "autostart": "-autostart",  # attach and auto-run a program/image
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `nix develop -c pytest tests/test_driver_vice.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vintage/drivers/vice.py tests/test_driver_vice.py
git commit -m "feat(vice): add tape, cart and autostart media slots"
```

---

### Task 4: Model-aware RAM-expansion knob

**Files:**
- Modify: `src/vintage/drivers/vice.py`
- Test: `tests/test_driver_vice.py`

**Interfaces:**
- Consumes: `Machine.options` `model` and `ram`.
- Produces:
  - `ram_args(machine: Machine) -> list[str]` — `[]` when no `ram`; for `vic20` maps `ram ∈ {3k,8k,16k,24k,all}` to `["-memory", ram]`; for `c64` maps `ram == "reu"` to `["-reu"]`; raises `ValueError` on an unsupported value for the model.
  - `run` composes `extra = ram_args(machine) + media_args(machine)` and passes it to `build_argv` (ram flags before media flags).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_driver_vice.py` a small helper builder for a vic20 machine, plus tests:

```python
def _make_vice(root: Path, *, model: str, extra: str = "") -> Path:
    d = root / model
    (d / "media").mkdir(parents=True)
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        f'name = "{model}"\nemulator = "vice"\nmodel = "{model}"\n'
        f'config = "vicerc"\n' + extra
    )
    (d / "vicerc").write_text("# bare\n")
    return d


def test_ram_args_none_when_absent(tmp_path):
    m = load_machine(_make_vice(tmp_path, model="vic20"))
    assert vice.ram_args(m) == []


def test_ram_args_vic20_memory(tmp_path):
    m = load_machine(_make_vice(tmp_path, model="vic20", extra='ram = "24k"\n'))
    assert vice.ram_args(m) == ["-memory", "24k"]


def test_ram_args_c64_reu(tmp_path):
    m = load_machine(_make_vice(tmp_path, model="c64", extra='ram = "reu"\n'))
    assert vice.ram_args(m) == ["-reu"]


def test_ram_args_vic20_bad_value_raises(tmp_path):
    m = load_machine(_make_vice(tmp_path, model="vic20", extra='ram = "reu"\n'))
    with pytest.raises(ValueError, match="vic20"):
        vice.ram_args(m)


def test_run_places_ram_before_media(tmp_path):
    d = _make_vice(
        tmp_path,
        model="vic20",
        extra='ram = "24k"\n[[media]]\nslot = "drive8"\nfile = "media/g.d64"\n',
    )
    (d / "media" / "g.d64").write_text("x")
    m = load_machine(d)
    calls = []
    vice.run(m, env={}, runner=lambda argv: calls.append(argv) or 0)
    argv = calls[0]
    assert argv[0] == "xvic"
    assert "-memory" in argv and "-8" in argv
    assert argv.index("-memory") < argv.index("-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `nix develop -c pytest tests/test_driver_vice.py -k ram -v`
Expected: FAIL — `ram_args` not defined.

- [ ] **Step 3: Write minimal implementation**

In `src/vintage/drivers/vice.py`, add the accepted VIC-20 memory specs and `ram_args`:

```python
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
```

In `run`, compose ram before media:

```python
    extra = ram_args(machine) + media_args(machine)
    return runner(build_argv(vice_bin, config_path, extra))
```

(Replace the previous `return runner(build_argv(vice_bin, config_path, media_args(machine)))`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `nix develop -c pytest tests/ -v`
Expected: PASS (whole suite).

- [ ] **Step 5: Commit**

```bash
git add src/vintage/drivers/vice.py tests/test_driver_vice.py
git commit -m "feat(vice): model-aware RAM-expansion knob (vic20 -memory, c64 -reu)"
```

---

### Task 5: `vic20` machine, `c64` update, and `new` template

**Files:**
- Create: `machines/vic20/machine.toml`, `machines/vic20/vicerc`, `machines/vic20/media/.gitkeep`, `machines/vic20/state/.gitkeep`
- Modify: `machines/c64/machine.toml`, `src/vintage/cli.py`
- Test: `tests/test_machine.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `options`/driver behavior from Tasks 1–4.
- Produces: a shipped `vic20` machine (`model = "vic20"`, no `[[media]]`, no `ram` → boots bare to `READY.`); `vintage new --emulator vice` writes `model = "c64"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_machine.py`:

```python
def test_shipped_vic20_machine_loads():
    repo_machines = Path(__file__).resolve().parents[1] / "machines"
    m = load_machine(repo_machines / "vic20")
    assert m.emulator == "vice"
    assert m.options.get("model") == "vic20"
    assert m.config == "vicerc"
    assert m.media == ()  # boots to READY. bare
    assert (repo_machines / "vic20" / "vicerc").is_file()
```

Check the existing `tests/test_cli.py` for how `new --emulator vice` is asserted; add (or extend) a test that the scaffolded vice `machine.toml` contains a model line:

```python
def test_new_vice_machine_writes_model(tmp_path):
    from vintage.cli import cmd_new
    assert cmd_new(tmp_path, "myvice", emulator="vice") == 0
    toml = (tmp_path / "myvice" / "machine.toml").read_text()
    assert 'model    = "c64"' in toml
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `nix develop -c pytest tests/test_machine.py::test_shipped_vic20_machine_loads tests/test_cli.py::test_new_vice_machine_writes_model -v`
Expected: FAIL — no `machines/vic20`; template has no model line.

- [ ] **Step 3: Create the machine and update the template**

Create `machines/vic20/machine.toml`:

```toml
name     = "Commodore VIC-20"
emulator = "vice"
model    = "vic20"
config   = "vicerc"

# Optional RAM expansion (VIC-20 memory blocks: 3k / 8k / 16k / 24k / all).
# ram = "24k"

# Optional media (user-provided, gitignored). Slots -> VICE flags:
#   drive8    -8         disk image
#   cart      -cartcrt   CRT cartridge image
#   tape      -1         datasette tape (LOAD manually)
#   autostart -autostart attach and auto-run (.prg / .d64 / .crt / .tap)
# [[media]]
# slot = "drive8"
# file = "media/game.d64"
```

Create `machines/vic20/vicerc`:

```
# VICE configuration for a bare Commodore VIC-20 (xvic).
# Hardware defaults come from VICE. The launcher copies this file into the
# machine's gitignored state/ on first run; VICE reads and writes that working
# copy, so runtime tweaks persist there without touching this template.
```

Create the two placeholders:

```bash
: > machines/vic20/media/.gitkeep
: > machines/vic20/state/.gitkeep
```

Update `machines/c64/machine.toml` to declare its model and document the shared knobs (replace the whole file):

```toml
name     = "Commodore 64"
emulator = "vice"
model    = "c64"
config   = "vicerc"

# Optional RAM expansion (C64 REU): ram = "reu"

# Optional media (user-provided, gitignored). Slots -> VICE flags:
#   drive8    -8         disk image
#   cart      -cartcrt   CRT cartridge image
#   tape      -1         datasette tape (LOAD manually)
#   autostart -autostart attach and auto-run (.prg / .d64 / .crt / .tap)
# [[media]]
# slot = "drive8"
# file = "media/demo.d64"
```

Update the vice template in `src/vintage/cli.py`. Change `_EMULATOR_TEMPLATES` values to carry an extra TOML fragment, and `_machine_toml` to accept it:

```python
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
```

And in `cmd_new`, unpack the third element and pass it:

```python
    config_name, config_body, extra_toml = template
    (dest / "media").mkdir(parents=True)
    (dest / "state").mkdir(parents=True)
    (dest / "machine.toml").write_text(
        _machine_toml(name, emulator, config_name, extra_toml)
    )
    (dest / config_name).write_text(config_body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `nix develop -c pytest tests/ -v`
Expected: PASS (whole suite, including existing `test_cli.py`).

- [ ] **Step 5: Commit**

```bash
git add machines/vic20 machines/c64/machine.toml src/vintage/cli.py tests/test_machine.py tests/test_cli.py
git commit -m "feat(machines): ship vic20 machine; declare model on c64; new writes model"
```

---

### Task 6: Flake wiring (`VINTAGE_VICE_BIN_DIR`) and live verification

**Files:**
- Modify: `flake.nix`, `README.md`

**Interfaces:**
- Consumes: `resolve_binary` reads `VINTAGE_VICE_BIN_DIR`.
- Produces: the wrapped `vintage` sets `VINTAGE_VICE_BIN_DIR` to the VICE `bin/` dir on Linux and aarch64-darwin.

- [ ] **Step 1: Rewire the flake**

In `flake.nix`, replace the `viceBin` derivation-of-a-binary with a bin **directory**:

```nix
          # Directory holding the VICE binaries (x64sc, xvic, ...): nixpkgs on
          # Linux, the prebuilt app on aarch64-darwin, nothing elsewhere. The
          # driver joins the per-model binary name onto this dir.
          viceBinDir =
            if pkgs.stdenv.isLinux then "${pkgs.vice}/bin"
            else if system == "aarch64-darwin" then "${vice-macos}/vice/bin"
            else null;
```

Replace the `viceArg` wiring:

```nix
            viceArg = nixpkgs.lib.optionalString (viceBinDir != null)
              "--set VINTAGE_VICE_BIN_DIR ${viceBinDir}";
```

(The `wrapProgram` line already interpolates `${viceArg}`, so no other change there.)

- [ ] **Step 2: Build the flake**

Run: `nix build .#vintage --no-link --print-out-paths`
Expected: builds; prints a store path (no evaluation error on aarch64-darwin).

- [ ] **Step 3: Verify the wiring is set**

Run: `grep -r VINTAGE_VICE_BIN_DIR $(nix build .#vintage --no-link --print-out-paths)/bin/vintage`
Expected: the wrapper exports `VINTAGE_VICE_BIN_DIR` pointing at a `.../bin` path that contains `xvic`.

- [ ] **Step 4: Live boot the VIC-20**

Run: `nix run .#vintage -- run vic20`
Expected: an `xvic` window opens and the VIC-20 boots to its BASIC `READY.` prompt (bare machine, no media). Close the window to end.

- [ ] **Step 5: Update the README**

In `README.md`, add VIC-20 alongside the C64 in the supported-machines / Commodore notes (one or two lines: `vintage run vic20` boots a bare VIC-20; cart/tape/RAM knobs available), and move the "Commodore via VICE" roadmap bullet to reflect that C64 **and** VIC-20 now ship.

- [ ] **Step 6: Commit**

```bash
git add flake.nix README.md
git commit -m "feat(flake): wire VINTAGE_VICE_BIN_DIR for per-model VICE binaries; document vic20"
```

---

## Self-Review

**Spec coverage:**
- Ship `vic20` boot-to-`READY.` → Task 5 (machine) + Task 6 (live verify). ✓
- Binary-by-model (`x64sc`/`xvic`) from one distribution → Task 2 + Task 6 flake. ✓
- Cart/tape/autostart media slots → Task 3. ✓
- Model-aware `ram` knob (VIC-20 `-memory`, C64 `-reu`) → Task 4. ✓
- `options` mapping, loader agnostic → Task 1. ✓
- `new --emulator vice` writes model → Task 5. ✓
- Flake `VINTAGE_VICE_BIN_DIR` → Task 6. ✓
- Preserve 86Box + C64 behavior → existing tests kept green in Tasks 2–5; only the C64 env-var test is updated to the new contract. ✓
- No ROMs/media in git → only `.gitkeep` placeholders added (Task 5). ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete content. ✓

**Type consistency:** `resolve_binary(model, env) -> str`, `ram_args(machine) -> list[str]`, `MODEL_BINARIES`, `SLOT_FLAGS`, `VIC20_MEMORY`, `Machine.options`, and `build_argv(vice_bin, config_path, extra)` are used consistently across tasks. `run` composes `ram_args + media_args` into `extra`. ✓
