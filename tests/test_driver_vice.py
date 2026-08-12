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
    assert len(args) == 2
    assert Path(args[1]).is_absolute()
    assert args[1] == str((m.path / "media" / "missing.d64").resolve())


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


def test_run_stamps_config_version_from_env(tmp_path):
    # Without a [Version] tag VICE pops a warning dialog on every boot.
    m = load_machine(_make_c64(tmp_path))
    vice.run(m, env={"VINTAGE_VICE_VERSION": "3.10"}, runner=lambda argv: 0)
    text = (m.state_dir / "vicerc").read_text()
    assert text.startswith("# bare C64\n")  # template body untouched
    assert "[Version]" in text
    assert "ConfigVersion=3.10" in text


def test_version_stamp_written_only_once(tmp_path):
    m = load_machine(_make_c64(tmp_path))
    env = {"VINTAGE_VICE_VERSION": "3.10"}
    vice.run(m, env=env, runner=lambda argv: 0)
    first = (m.state_dir / "vicerc").read_text()
    vice.run(m, env=env, runner=lambda argv: 0)
    assert (m.state_dir / "vicerc").read_text() == first
    assert first.count("[Version]") == 1


def test_existing_version_tag_is_never_rewritten(tmp_path):
    # A config VICE itself saved carries its own tag; a mismatch is a real
    # signal for the user, not something the launcher should paper over.
    m = load_machine(_make_c64(tmp_path))
    cfg = m.state_dir / "vicerc"
    cfg.write_text("[Version]\nConfigVersion=3.9\n")
    vice.run(m, env={"VINTAGE_VICE_VERSION": "3.10"}, runner=lambda argv: 0)
    assert cfg.read_text() == "[Version]\nConfigVersion=3.9\n"


def test_run_without_version_env_leaves_config_untouched(tmp_path):
    m = load_machine(_make_c64(tmp_path))
    vice.run(m, env={}, runner=lambda argv: 0)
    assert (m.state_dir / "vicerc").read_text() == "# bare C64\n"
