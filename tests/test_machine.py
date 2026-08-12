from pathlib import Path
from vintage.machine import Machine, Media, load_machine, discover_machines


def test_shipped_c64_machine_loads():
    repo_machines = Path(__file__).resolve().parents[1] / "machines"
    m = load_machine(repo_machines / "c64")
    assert m.emulator == "vice"
    assert m.config == "vicerc"
    assert m.media == ()  # boots to READY. with no user media
    assert (repo_machines / "c64" / "vicerc").is_file()


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
