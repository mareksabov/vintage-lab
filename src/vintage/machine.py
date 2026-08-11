"""Machine model, loading, and discovery."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Media:
    slot: str
    file: str


@dataclass(frozen=True)
class Machine:
    id: str
    path: Path
    name: str
    emulator: str
    config: str
    media: tuple[Media, ...] = ()

    @property
    def state_dir(self) -> Path:
        return self.path / "state"

    @property
    def media_dir(self) -> Path:
        return self.path / "media"


def load_machine(path: Path) -> Machine:
    data = tomllib.loads((path / "machine.toml").read_text())
    media = tuple(
        Media(slot=entry["slot"], file=entry["file"])
        for entry in data.get("media", [])
    )
    return Machine(
        id=path.name,
        path=path,
        name=data["name"],
        emulator=data["emulator"],
        config=data["config"],
        media=media,
    )


def discover_machines(root: Path) -> list[Machine]:
    machines = [
        load_machine(child)
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "machine.toml").is_file()
    ]
    return machines
