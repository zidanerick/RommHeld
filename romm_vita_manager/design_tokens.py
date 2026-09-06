from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str
    sidebar: str
    surface: str
    surface_raised: str
    surface_hover: str
    separator: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    success: str
    warning: str
    error: str


@dataclass(frozen=True)
class PlatformBrand:
    key: str
    name: str
    accent: str
    accent_hover: str
    accent_soft: str


# Neutral dark surfaces intentionally resemble modern desktop system UI rather
# than any specific proprietary interface.
DARK = Palette(
    background="#0B0B0D",
    sidebar="#141416",
    surface="#1C1C1E",
    surface_raised="#242426",
    surface_hover="#2C2C2E",
    separator="#38383A",
    text_primary="#F5F5F7",
    text_secondary="#A1A1A6",
    text_tertiary="#727277",
    success="#30D158",
    warning="#FF9F0A",
    error="#FF453A",
)


# Manufacturer-family accents. These are orientation accents only: the app
# stays neutral and uses the brand colour sparingly for selection and primary
# actions.
BRANDS: dict[str, PlatformBrand] = {
    "nintendo": PlatformBrand("nintendo", "Nintendo", "#E60012", "#FF1A2B", "#351014"),
    "sony": PlatformBrand("sony", "Sony / PlayStation", "#0070D1", "#1687E5", "#0C2740"),
    "xbox": PlatformBrand("xbox", "Xbox", "#107C10", "#159615", "#153415"),
    "sega": PlatformBrand("sega", "Sega", "#0089CF", "#10A0E8", "#0C2D3D"),
    "neutral": PlatformBrand("neutral", "Neutral", "#6E6E73", "#85858B", "#2A2A2D"),
}


PLATFORM_FAMILIES: dict[str, str] = {
    "vita": "sony",
    "psvita": "sony",
    "psp": "sony",
    "playstation_portable": "sony",
    "3ds": "nintendo",
    "nintendo_3ds": "nintendo",
    "ds": "nintendo",
    "nintendo_ds": "nintendo",
    "gba": "nintendo",
    "game_boy_advance": "nintendo",
    "gb": "nintendo",
    "gbc": "nintendo",
    "switch": "nintendo",
    "xbox": "xbox",
    "xbox360": "xbox",
    "xbox_one": "xbox",
    "dreamcast": "sega",
    "saturn": "sega",
    "genesis": "sega",
    "megadrive": "sega",
}


# Shared geometry. Keeping these values here prevents every widget from
# inventing its own margins and corner radii.
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

RADIUS_SMALL = 8
RADIUS_MEDIUM = 12
RADIUS_LARGE = 16

SIDEBAR_WIDTH = 238
CONTENT_MAX_WIDTH = 1440


_STATUS_ERROR_TERMS = (
    "failed",
    "failure",
    "error",
    "invalid",
    "missing",
)
_STATUS_MUTED_TERMS = (
    "not configured",
    "not mounted",
    "not detected",
    "not selected",
    "not checked",
    "unavailable",
)
_STATUS_WARNING_TERMS = (
    "needs ",
    "required",
    "waiting",
    "checking",
    "cancelling",
    "transferring",
    "preparing",
    "confirm",
    "action required",
    "overwrite needed",
    "endpoint required",
)
_STATUS_SUCCESS_TERMS = (
    "ready",
    "connected",
    "mounted",
    "detected",
    "configured",
    "complete",
    "completed",
    "copied",
    "validated",
)


# Health services expose explicit state keys. Keep their presentation separate
# from status_tone(), which exists for older free-form workflow strings. This
# prevents the UI from inferring device/runtime health from wording such as a
# path, marker, or troubleshooting sentence.
_HEALTH_STATE_ALIASES = {
    "assets-only": "assets_only",
    "data-only": "data_only",
    "manual-only": "manual_only",
    "system-sensitive": "system_sensitive",
    "not-verified": "not_verified",
    "present-unverified": "present_unverified",
    "needs-attention": "needs_attention",
    "not-applicable": "not_applicable",
    "unknown/manual-only": "unknown_manual_only",
}

_HEALTH_STATE_TONES = {
    "healthy": "success",
    "ready": "success",
    "verified": "success",
    "present": "neutral",
    "not_verified": "neutral",
    "present_unverified": "neutral",
    "partial": "warning",
    "assets_only": "warning",
    "data_only": "warning",
    "repairable": "warning",
    "needs_attention": "warning",
    "incomplete": "warning",
    "outdated": "warning",
    "manual_only": "warning",
    "system_sensitive": "warning",
    "unknown_manual_only": "warning",
    "busy": "warning",
    "checking": "warning",
    "misconfigured": "error",
    "failed": "error",
    "error": "error",
    "missing": "muted",
    "unknown": "muted",
    "not_applicable": "muted",
}

_HEALTH_STATE_LABELS = {
    "healthy": "Healthy",
    "ready": "Ready",
    "verified": "Verified",
    "present": "Present",
    "not_verified": "Present · Not verified",
    "present_unverified": "Present · Launch not verified",
    "partial": "Partial",
    "assets_only": "Assets only",
    "data_only": "Data/assets only",
    "repairable": "Repairable",
    "needs_attention": "Needs attention",
    "incomplete": "Incomplete",
    "outdated": "Outdated",
    "manual_only": "Manual only",
    "system_sensitive": "System-sensitive · Manual only",
    "unknown_manual_only": "Unknown · Manual confirmation required",
    "busy": "In progress",
    "checking": "Checking",
    "misconfigured": "Misconfigured",
    "failed": "Failed",
    "error": "Error",
    "missing": "Missing",
    "unknown": "Unknown",
    "not_applicable": "Not applicable",
}


def brand_for_platform(platform_key: str | None) -> PlatformBrand:
    key = (platform_key or "").strip().lower()
    family = PLATFORM_FAMILIES.get(key, "neutral")
    return BRANDS[family]


def status_tone(value: str) -> str:
    """Classify common workflow text without importing Qt.

    Absence states such as ``Not mounted`` remain muted rather than being
    presented as failures. Explicit failure language wins over all other
    matches, and warning/busy states are kept distinct from successful states.
    """

    text = value.strip().casefold()
    if not text:
        return "neutral"
    if any(term in text for term in _STATUS_ERROR_TERMS):
        return "error"
    if any(term in text for term in _STATUS_MUTED_TERMS):
        return "muted"
    if any(term in text for term in _STATUS_WARNING_TERMS):
        return "warning"
    if any(term in text for term in _STATUS_SUCCESS_TERMS):
        return "success"
    return "neutral"


def normalize_health_state(state: str | None) -> str:
    """Normalize a service-supplied health state for presentation only.

    Unknown future states are preserved rather than rejected so a newer device
    service can still render safely before the UI gains a tailored label/tone.
    """

    raw = str(state or "").strip().casefold()
    if not raw:
        return "unknown"
    if raw in _HEALTH_STATE_ALIASES:
        return _HEALTH_STATE_ALIASES[raw]
    return raw.replace("-", "_").replace(" ", "_").replace("/", "_")


def health_state_tone(state: str | None) -> str:
    """Return the semantic UI tone for an explicit service health state."""

    return _HEALTH_STATE_TONES.get(normalize_health_state(state), "neutral")


def health_state_label(state: str | None, fallback: str | None = None) -> str:
    """Return a compact label without deriving or changing the health state."""

    normalized = normalize_health_state(state)
    if fallback:
        return fallback
    label = _HEALTH_STATE_LABELS.get(normalized)
    if label:
        return label
    return normalized.replace("_", " ").strip().title() or "Unknown"


__all__ = [
    "BRANDS",
    "CONTENT_MAX_WIDTH",
    "DARK",
    "PLATFORM_FAMILIES",
    "Palette",
    "PlatformBrand",
    "RADIUS_LARGE",
    "RADIUS_MEDIUM",
    "RADIUS_SMALL",
    "SIDEBAR_WIDTH",
    "SPACE_1",
    "SPACE_2",
    "SPACE_3",
    "SPACE_4",
    "SPACE_5",
    "SPACE_6",
    "SPACE_8",
    "brand_for_platform",
    "health_state_label",
    "health_state_tone",
    "normalize_health_state",
    "status_tone",
]
