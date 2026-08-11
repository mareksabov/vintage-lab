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
