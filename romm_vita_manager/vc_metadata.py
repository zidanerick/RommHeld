from __future__ import annotations

import unicodedata
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


_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�")


def _mojibake_score(value: str) -> int:
    return sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)


def _repair_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Latin-1/CP1252 metadata corruption.

    RomM metadata normally arrives as proper Unicode, but imported metadata can
    already contain strings such as ``PokÃ©mon``. Only accept a round-trip when
    it strictly reduces tell-tale mojibake markers, so legitimate non-ASCII
    names are left alone.
    """
    best = value
    best_score = _mojibake_score(value)
    if best_score == 0:
        return value
    for encoding in ("latin-1", "cp1252"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        score = _mojibake_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return best


def _clean(value: str | None, *, limit: int = 128) -> str:
    text = str(value or "").replace("\x00", " ")
    text = unicodedata.normalize("NFC", _repair_mojibake(text))
    return " ".join(text.split()).strip()[:limit]


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
