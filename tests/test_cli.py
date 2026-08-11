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
