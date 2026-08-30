from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Game:
    path: Path
    name: str
    source_platform: str
    size: int
    relative: Path


@dataclass(frozen=True)
class Destination:
    label: str
    path: Path
    mode: str


@dataclass(frozen=True)
class VitaStatus:
    state: str
    detail: str
