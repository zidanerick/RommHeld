from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterable

from .config import load_config, save_config


_GBA_FAMILY = "gba"
_CLASSIC_FAMILIES = {"gb", "gbc", "nes", "gamegear", "snes"}
_GBA_CAPACITY = 0x1000
_CLASSIC_CAPACITY = 0x10000
_CLASSIC_UID_BASE = 0x0E0000
_ALLOCATION_VERSION = 1
_LOCK = threading.RLock()


def _source_key(config: dict) -> str:
    source = config.get("library_source", {})
    raw = str(source.get("romm_url", "")).strip().rstrip("/").casefold() if isinstance(source, dict) else ""
    if not raw:
        return "default"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _allocation_key(config: dict, family: str, romm_id: int) -> str:
    return f"{family.lower()}:{_source_key(config)}:{romm_id}"


def _pool(family: str) -> str:
    key = family.lower()
    if key == _GBA_FAMILY:
        return "gba"
    if key in _CLASSIC_FAMILIES:
        return "classic"
    raise ValueError(f"Unsupported Virtual Console title-ID family: {family}")


def _is_valid_for_pool(title_id: bytes, pool: str) -> bool:
    if len(title_id) != 8:
        return False
    text = title_id.hex()
    if pool == "gba":
        return text.startswith("0004000000f") and text.endswith("00")
    if not text.startswith("00040000") or not text.endswith("00"):
        return False
    unique_id = int.from_bytes(title_id[-4:], "big") >> 8
    return _CLASSIC_UID_BASE <= unique_id < _CLASSIC_UID_BASE + _CLASSIC_CAPACITY


def _slot_from_title_id(title_id: bytes, pool: str) -> int:
    if not _is_valid_for_pool(title_id, pool):
        raise ValueError("Preferred Virtual Console title ID is outside its allocation pool.")
    if pool == "gba":
        return (int.from_bytes(title_id[-3:], "big") >> 8) & 0x0FFF
    unique_id = int.from_bytes(title_id[-4:], "big") >> 8
    return unique_id - _CLASSIC_UID_BASE


def _candidate(pool: str, slot: int) -> bytes:
    if pool == "gba":
        if not 0 <= slot < _GBA_CAPACITY:
            raise ValueError("GBA title-ID allocation slot is out of range.")
        return bytes.fromhex(f"0004000000F{slot:03X}00")
    if not 0 <= slot < _CLASSIC_CAPACITY:
        raise ValueError("Classic VC title-ID allocation slot is out of range.")
    unique_id = _CLASSIC_UID_BASE + slot
    return bytes.fromhex(f"00040000{(unique_id << 8):08X}")


def _allocations(config: dict) -> dict[str, str]:
    vc = config.get("three_ds_vc", {})
    raw = vc.get("title_id_allocations", {}) if isinstance(vc, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value).lower()
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def preferred_title_id(family: str, romm_id: int) -> bytes:
    """Return the deterministic preferred ID without reading or writing config."""
    if romm_id < 0:
        raise ValueError("RomM ROM ID must be non-negative.")
    key = family.lower()
    if key == _GBA_FAMILY:
        digest = hashlib.sha256(str(romm_id).encode("ascii")).digest()
        unique = int.from_bytes(digest[:2], "big") & 0x0FFF
        return bytes.fromhex(f"0004000000F{unique:03X}00")
    if key not in _CLASSIC_FAMILIES:
        raise ValueError(f"Unsupported Virtual Console title-ID family: {family}")
    digest = hashlib.sha256(f"{key}:{romm_id}".encode("ascii")).digest()
    unique_id = _CLASSIC_UID_BASE | (int.from_bytes(digest[:2], "big") & 0x00FFFF)
    return bytes.fromhex(f"00040000{(unique_id << 8):08X}")


def configured_title_id(config: dict, family: str, romm_id: int) -> bytes | None:
    """Return a valid unique persisted assignment without mutating config."""
    key = family.lower()
    pool = _pool(key)
    allocations = _allocations(config)
    identity = _allocation_key(config, key, romm_id)
    raw = allocations.get(identity)
    if not raw:
        return None
    try:
        value = bytes.fromhex(raw)
    except ValueError:
        return None
    if not _is_valid_for_pool(value, pool):
        return None
    if any(other_key != identity and other_value == raw for other_key, other_value in allocations.items()):
        return None
    return value


def displayed_title_id(config: dict, family: str, romm_id: int) -> bytes:
    """Return the current assignment or preferred candidate without persisting it."""
    return configured_title_id(config, family, romm_id) or preferred_title_id(family, romm_id)


def allocate_registered_title_id(
    config: dict,
    family: str,
    romm_id: int,
    preferred: bytes | None = None,
    *,
    reserved_title_ids: Iterable[bytes] = (),
) -> tuple[dict, bytes]:
    """Allocate a stable RommHeld title ID inside the family pool.

    New assignments avoid other RommHeld assignments and any explicitly
    supplied reserved IDs. A valid existing assignment is intentionally kept
    stable even if it later appears in ``reserved_title_ids`` because changing
    an established title ID would break upgrade/save continuity. Callers that
    can inventory a target should therefore provide reserved IDs before the
    title's first deployment. The registry cannot by itself prove that an ID is
    absent from an arbitrary console's installed-title database.
    """
    if romm_id < 0:
        raise ValueError("RomM ROM ID must be non-negative.")
    key = family.lower()
    pool = _pool(key)
    preferred = preferred if preferred is not None else preferred_title_id(key, romm_id)
    if not _is_valid_for_pool(preferred, pool):
        raise ValueError("Preferred Virtual Console title ID is invalid for this family.")

    existing = configured_title_id(config, key, romm_id)
    if existing is not None:
        return config, existing

    allocations = _allocations(config)
    identity = _allocation_key(config, key, romm_id)
    used: set[bytes] = set()
    for other_key, raw in allocations.items():
        if other_key == identity:
            continue
        try:
            value = bytes.fromhex(raw)
        except ValueError:
            continue
        if _is_valid_for_pool(value, pool):
            used.add(value)

    for raw in reserved_title_ids:
        try:
            value = bytes(raw)
        except (TypeError, ValueError):
            continue
        if _is_valid_for_pool(value, pool):
            used.add(value)

    capacity = _GBA_CAPACITY if pool == "gba" else _CLASSIC_CAPACITY
    preferred_slot = _slot_from_title_id(preferred, pool)
    selected: bytes | None = None
    for offset in range(capacity):
        candidate = _candidate(pool, (preferred_slot + offset) % capacity)
        if candidate not in used:
            selected = candidate
            break
    if selected is None:
        raise RuntimeError(f"No free {pool} Virtual Console title IDs remain in RommHeld's allocation pool.")

    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    stored = dict(allocations)
    stored[identity] = selected.hex()
    vc["title_id_allocation_version"] = _ALLOCATION_VERSION
    vc["title_id_allocations"] = stored
    updated["three_ds_vc"] = vc
    return updated, selected


def persist_registered_title_id(
    family: str,
    romm_id: int,
    preferred: bytes | None = None,
    *,
    reserved_title_ids: Iterable[bytes] = (),
) -> tuple[dict, bytes]:
    """Atomically resolve and persist a deployment-time title-ID assignment."""
    with _LOCK:
        config = load_config()
        updated, title_id = allocate_registered_title_id(
            config,
            family,
            romm_id,
            preferred,
            reserved_title_ids=reserved_title_ids,
        )
        if updated != config:
            save_config(updated)
        return updated, title_id
