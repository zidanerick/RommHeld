from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VirtualConsoleProfile:
    key: str
    label: str
    source_extensions: tuple[str, ...]
    output_extension: str
    runtime: str
    requires_boot_logo: bool = False
    requires_boot9: bool = False
    title_id_pattern: str | None = None


GBA_NATIVE_PROFILE = VirtualConsoleProfile(
    key="gba-native",
    label="GBA Virtual Console-style (AGB_FIRM)",
    source_extensions=(".gba", ".agb"),
    output_extension=".cia",
    runtime="nintendo-agb-firm",
    requires_boot_logo=True,
    requires_boot9=True,
    title_id_pattern="0004000000F???00",
)


PROFILES = (GBA_NATIVE_PROFILE,)


def profile_for_rom(path: str | Path) -> VirtualConsoleProfile | None:
    suffix = Path(path).suffix.lower()
    return next((profile for profile in PROFILES if suffix in profile.source_extensions), None)


def validate_native_gba_title_id(title_id: str) -> str:
    value = title_id.strip().lower()
    if len(value) != 16:
        raise ValueError("GBA native Virtual Console title IDs must contain 16 hexadecimal digits.")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("GBA native Virtual Console title IDs must contain only hexadecimal digits.") from exc
    if not (value.startswith("0004000000f") and value.endswith("00")):
        raise ValueError("GBA native Virtual Console title IDs must match 0004000000F???00.")
    return value


def validate_gba_native_assets(*, boot_logo: str | Path | None, boot9: str | Path | None) -> None:
    for label, value in (("AGB_FIRM boot logo", boot_logo), ("boot9 dump", boot9)):
        if value is None or not Path(value).expanduser().is_file():
            raise FileNotFoundError(f"A valid {label} file is required for native GBA packaging.")
