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
