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
