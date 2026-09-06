from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping


CONFIG_RELATIVE_PATH = Path("3ds/open_agb_firm/config.ini")
BACKUP_SUFFIX = ".rommheld.bak"

SCALERS = frozenset({"none", "bilinear", "matrix"})
COLOR_PROFILES = frozenset(
    {"none", "gba", "gb_micro", "gba_sp101", "nds", "ds_lite", "nso", "vba", "identity"}
)
AUDIO_OUTPUTS = frozenset({"auto", "speakers", "headphones"})
BOOL_VALUES = frozenset({"true", "false"})

SUPPORTED_SETTINGS: dict[tuple[str, str], str] = {
    ("general", "backlight"): "backlight",
    ("general", "backlightSteps"): "positive_int",
    ("general", "directBoot"): "bool",
    ("general", "useGbaDb"): "bool",
    ("general", "useSavesFolder"): "bool",
    ("video", "scaler"): "scaler",
    ("video", "colorProfile"): "color_profile",
    ("video", "contrast"): "float",
    ("video", "brightness"): "float",
    ("video", "saturation"): "nonnegative_float",
    ("audio", "audioOut"): "audio_out",
    ("audio", "volume"): "volume",
    ("advanced", "saveOverride"): "bool",
    ("advanced", "defaultSave"): "nonempty",
}

_SECTION_RE = re.compile(r"^\s*\[([^]]+)\]\s*(?:[;#].*)?$")
_ASSIGNMENT_RE = re.compile(r"^(\s*)([^=;#]+?)(\s*=\s*)(.*)$")


def _normalise_bool(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text not in BOOL_VALUES:
        raise ValueError("Boolean settings must be true or false.")
    return text


def _validate_value(section: str, key: str, value: object) -> str:
    validator = SUPPORTED_SETTINGS.get((section, key))
    if validator is None:
        raise KeyError(f"Unsupported open_agb_firm setting: [{section}] {key}")

    if validator == "bool":
        return _normalise_bool(value)

    text = str(value).strip()
    if validator == "nonempty":
        if not text:
            raise ValueError(f"[{section}] {key} cannot be empty.")
        return text
    if validator == "scaler":
        if text not in SCALERS:
            raise ValueError(f"scaler must be one of: {', '.join(sorted(SCALERS))}")
        return text
    if validator == "color_profile":
        if text not in COLOR_PROFILES:
            raise ValueError(
                f"colorProfile must be one of: {', '.join(sorted(COLOR_PROFILES))}"
            )
        return text
    if validator == "audio_out":
        if text not in AUDIO_OUTPUTS:
            raise ValueError(f"audioOut must be one of: {', '.join(sorted(AUDIO_OUTPUTS))}")
        return text
    if validator == "backlight":
        number = int(text)
        if not 16 <= number <= 142:
            raise ValueError("backlight must be between 16 and 142. Model-specific limits may be narrower.")
        return str(number)
    if validator == "positive_int":
        number = int(text)
        if number <= 0:
            raise ValueError(f"[{section}] {key} must be greater than zero.")
        return str(number)
    if validator == "volume":
        number = int(text)
        if not -128 <= number <= 127:
            raise ValueError("volume must be between -128 and 127.")
        return str(number)
    if validator == "float":
        return str(float(text))
    if validator == "nonnegative_float":
        number = float(text)
        if number < 0:
            raise ValueError(f"[{section}] {key} cannot be negative.")
        return str(number)
    raise RuntimeError(f"Unknown validator for [{section}] {key}: {validator}")


def parse_open_agb_values(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for line in text.splitlines():
        section_match = _SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip()
            result.setdefault(section, {})
            continue
        if section is None:
            continue
        assignment = _ASSIGNMENT_RE.match(line)
        if not assignment:
            continue
        key = assignment.group(2).strip()
        value = assignment.group(4).strip()
        result.setdefault(section, {})[key] = value
    return result


def detect_open_agb_config_format(text: str) -> str:
    values = parse_open_agb_values(text)
    if not values:
        return "unknown"

    video = values.get("video", {})
    audio = values.get("audio", {})
    advanced = values.get("advanced", {})
    scaler = video.get("scaler", "")
    color_profile = video.get("colorProfile", "")
    audio_out = audio.get("audioOut", "")
    default_save = advanced.get("defaultSave", "")

    if scaler in SCALERS and (not color_profile or color_profile in COLOR_PROFILES):
        return "current"
    if scaler.isdigit() or color_profile.isdigit() or audio_out.isdigit() or default_save.isdigit():
        return "legacy"
    return "unknown"


def update_open_agb_config_text(
    text: str,
    updates: Mapping[tuple[str, str], object],
) -> str:
    if detect_open_agb_config_format(text) != "current":
        raise RuntimeError(
            "open_agb_firm config format is not recognised as current. Launch the installed open_agb_firm version once to generate a fresh config.ini before RommHeld edits it."
        )

    validated = {
        (section, key): _validate_value(section, key, value)
        for (section, key), value in updates.items()
    }
    if not validated:
        return text

    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    for (wanted_section, wanted_key), new_value in validated.items():
        section_start: int | None = None
        section_end = len(lines)
        for index, line in enumerate(lines):
            match = _SECTION_RE.match(line)
            if not match:
                continue
            section_name = match.group(1).strip()
            if section_start is None and section_name.casefold() == wanted_section.casefold():
                section_start = index
                continue
            if section_start is not None:
                section_end = index
                break

        if section_start is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend((f"[{wanted_section}]", f"{wanted_key}={new_value}"))
            continue

        replaced = False
        for index in range(section_start + 1, section_end):
            assignment = _ASSIGNMENT_RE.match(lines[index])
            if not assignment:
                continue
            key_name = assignment.group(2).strip()
            if key_name.casefold() != wanted_key.casefold():
                continue
            old_value = assignment.group(4)
            suffix = ""
            value_without_comment = old_value
            for marker in (";", "#"):
                position = value_without_comment.find(marker)
                if position >= 0:
                    suffix = value_without_comment[position:]
                    value_without_comment = value_without_comment[:position]
                    break
            spacer = " " if suffix and not suffix.startswith(" ") else ""
            lines[index] = (
                f"{assignment.group(1)}{assignment.group(2)}{assignment.group(3)}"
                f"{new_value}{spacer}{suffix}"
            )
            replaced = True
            break

        if not replaced:
            lines.insert(section_end, f"{wanted_key}={new_value}")

    result = "\n".join(lines)
    if had_trailing_newline:
        result += "\n"
    return result


def open_agb_config_path(sd_root: Path) -> Path:
    return sd_root.expanduser() / CONFIG_RELATIVE_PATH


def write_open_agb_config(
    sd_root: Path,
    updates: Mapping[tuple[str, str], object],
) -> Path:
    path = open_agb_config_path(sd_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"open_agb_firm config not found at {path}. Launch open_agb_firm once so it creates the config before RommHeld edits it."
        )

    original = path.read_text(encoding="utf-8")
    updated = update_open_agb_config_text(original, updates)
    if updated == original:
        return path

    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    temporary = path.with_name(path.name + ".rommheld.tmp")
    try:
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
