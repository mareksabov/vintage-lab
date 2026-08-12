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


def test_run_errors_without_roms_env(tmp_path, capsys):
    _make_machine(tmp_path)
    rc = run.cmd_run(tmp_path, "optiplex-gx", env={}, runner=lambda argv: 0)
    assert rc == 1
    assert "VINTAGE_ROMS_86BOX" in capsys.readouterr().err


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
