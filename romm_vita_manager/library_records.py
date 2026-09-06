from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from .mappings import normalize_platform_slug, platform_label
from .models import Game
from .romm_remote import RomMRemoteGame


ProviderIdentifier: TypeAlias = int | str
ProviderCursor: TypeAlias = int | str


@dataclass(frozen=True)
class LibraryPlatform:
    """Provider identity plus RommHeld's normalized platform interpretation."""

    provider_platform_id: ProviderIdentifier | None
    source_key: str
    canonical_key: str
    display_name: str


@dataclass(frozen=True)
class LocalContentRef:
    path: Path


@dataclass(frozen=True)
class RomMContentRef:
    rom_id: int
    filename: str


ContentRef: TypeAlias = LocalContentRef | RomMContentRef


@dataclass(frozen=True)
class LibraryItem:
    """Provider-neutral library metadata before target/deployment decisions."""

    provider: str
    provider_item_id: ProviderIdentifier
    platform: LibraryPlatform
    name: str
    filename: str
    size_bytes: int | None
    content_ref: ContentRef
    artwork_ref: str | None = None
    publisher: str | None = None
    release_year: int | None = None


@dataclass(frozen=True)
class LibraryQuery:
    search: str = ""
    canonical_platforms: frozenset[str] = frozenset()
    source_platform_id: ProviderIdentifier | None = None
    cursor: ProviderCursor | None = None
    page_size: int = 24
    scope_key: str = ""


@dataclass(frozen=True)
class LibraryPage:
    items: tuple[LibraryItem, ...]
    platforms: tuple[LibraryPlatform, ...] = ()
    next_cursor: ProviderCursor | None = None


def library_item_from_romm(game: RomMRemoteGame) -> LibraryItem:
    source_key = game.source_platform_slug or game.platform_slug
    canonical_key = str(game.platform_slug or source_key).strip().lower()
    return LibraryItem(
        provider="romm",
        provider_item_id=game.rom_id,
        platform=LibraryPlatform(
            provider_platform_id=game.source_platform_id,
            source_key=source_key,
            canonical_key=canonical_key,
            display_name=game.platform or platform_label(canonical_key),
        ),
        name=game.name,
        filename=game.filename,
        size_bytes=game.size,
        content_ref=RomMContentRef(game.rom_id, game.filename),
        artwork_ref=game.cover_url,
        publisher=game.publisher or None,
        release_year=game.release_year,
    )


def library_item_from_local(game: Game) -> LibraryItem:
    source_key = str(game.source_platform)
    canonical_key = normalize_platform_slug(source_key)
    return LibraryItem(
        provider="local",
        provider_item_id=str(game.path),
        platform=LibraryPlatform(
            provider_platform_id=None,
            source_key=source_key,
            canonical_key=canonical_key,
            display_name=platform_label(canonical_key),
        ),
        name=game.name,
        filename=game.path.name,
        size_bytes=game.size,
        content_ref=LocalContentRef(game.path),
    )
