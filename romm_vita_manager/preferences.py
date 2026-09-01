from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


PREFERENCE_OPTIONS = (
    ("native", "Prefer native runtime"),
    ("retroachievements", "Prefer RetroAchievements"),
    ("compatibility", "Prefer compatibility"),
)


@dataclass(frozen=True)
class RuntimePreference:
    key: str
    label: str


def preference_options() -> tuple[RuntimePreference, ...]:
    return tuple(RuntimePreference(key, label) for key, label in PREFERENCE_OPTIONS)


def get_device_preference(config: Mapping[str, object], device_key: str) -> str:
    preferences = config.get("runtime_preferences", {})
    if isinstance(preferences, Mapping):
        value = preferences.get(device_key)
        if value in {key for key, _ in PREFERENCE_OPTIONS}:
            return str(value)
    return "compatibility"


def set_device_preference(config: dict, device_key: str, preference: str) -> dict:
    if preference not in {key for key, _ in PREFERENCE_OPTIONS}:
        raise ValueError(f"Unknown runtime preference: {preference}")
    updated = dict(config)
    preferences = dict(updated.get("runtime_preferences", {}))
    preferences[device_key] = preference
    updated["runtime_preferences"] = preferences
    return updated
