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


def test_link_roms_repairs_wrong_target(tmp_path):
    """A symlink pointing at the wrong path is replaced."""
    vm = tmp_path / "state"
    vm.mkdir()
    old_roms = tmp_path / "old-roms"
    old_roms.mkdir()
    new_roms = tmp_path / "new-roms"
    new_roms.mkdir()
    # Create link pointing at old path
    (vm / "roms").symlink_to(old_roms)
    emu86box.link_roms(vm, new_roms)
    link = vm / "roms"
    assert link.is_symlink()
    assert link.resolve() == new_roms.resolve()


def test_link_roms_repairs_broken_dangling_symlink(tmp_path):
    """A dangling symlink (target deleted) is replaced."""
    vm = tmp_path / "state"
    vm.mkdir()
    gone_roms = tmp_path / "gone-roms"
    gone_roms.mkdir()
    (vm / "roms").symlink_to(gone_roms)
    gone_roms.rmdir()  # make the symlink dangle
    assert (vm / "roms").is_symlink()
    assert not (vm / "roms").exists()  # confirms it's dangling

    new_roms = tmp_path / "new-roms"
    new_roms.mkdir()
    emu86box.link_roms(vm, new_roms)
    link = vm / "roms"
    assert link.is_symlink()
    assert link.resolve() == new_roms.resolve()


def test_link_roms_raises_on_real_directory(tmp_path):
    """A real (non-symlink) directory at vmdir/roms raises RuntimeError."""
    vm = tmp_path / "state"
    vm.mkdir()
    real_dir = vm / "roms"
    real_dir.mkdir()
    roms = tmp_path / "roms-store"
    roms.mkdir()
    with pytest.raises(RuntimeError, match="non-symlink"):
        emu86box.link_roms(vm, roms)


def test_apply_media_warns_on_missing_file(tmp_path, capsys):
    """apply_media still writes the cfg key but emits a stderr warning when the
    media file does not exist on disk."""
    d = tmp_path / "missing-media-machine"
    (d / "state").mkdir(parents=True)
    (d / "machine.toml").write_text(
        'name = "Test"\nemulator = "86box"\nconfig = "86box.cfg"\n'
        '[[media]]\nslot = "floppy_a"\nfile = "media/missing.img"\n'
    )
    (d / "86box.cfg").write_text("[General]\nvid = 1\n")
    (d / "state" / "86box.cfg").write_text("[General]\nvid = 1\n")
    machine = load_machine(d)
    # The media file deliberately does NOT exist.
    emu86box.apply_media(machine)
    section, key = emu86box.SLOT_KEYS["floppy_a"]
    text = (machine.state_dir / "86box.cfg").read_text()
    # Key must still be written.
    assert key in text
    # Warning must name the missing file.
    captured = capsys.readouterr()
    assert "missing.img" in captured.err


def test_build_argv():
    assert emu86box.build_argv("/nix/store/x/bin/86Box", Path("/vm")) == [
        "/nix/store/x/bin/86Box", "-P", "/vm",
    ]
