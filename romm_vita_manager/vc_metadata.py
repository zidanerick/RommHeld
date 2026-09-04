from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VirtualConsoleMetadata:
    """Display strings written into generated 3DS VC titles.

    SMDH title fields are populated across all languages by agbcia's icon
    builder. Keeping these values non-empty and normalized also gives donor
    banner patching one canonical title string for the visible VC title badge.
    """

    short_title: str
    long_title: str
    publisher: str
    banner_title: str


def _clean(value: str | None, *, limit: int = 128) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()[:limit]


def normalize_vc_metadata(
    title_name: str,
    *,
    long_title: str | None = None,
    publisher: str | None = None,
) -> VirtualConsoleMetadata:
    """Return safe, visible metadata shared by every generated VC family."""

    short = _clean(title_name)
    if not short:
        short = "Untitled Game"
    long_value = _clean(long_title) or short
    publisher_value = _clean(publisher)
    return VirtualConsoleMetadata(
        short_title=short,
        long_title=long_value,
        publisher=publisher_value,
        banner_title=short,
    )
