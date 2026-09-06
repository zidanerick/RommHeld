import romm_vita_manager.vc_title_id_registry as registry


def _gba(slot: int) -> bytes:
    return bytes.fromhex(f"0004000000F{slot:03X}00")


def _gba_slot(title_id: bytes) -> int:
    return (int.from_bytes(title_id[-3:], "big") >> 8) & 0x0FFF


def test_display_preview_avoids_mounted_sd_collisions_without_persisting(monkeypatch):
    config = {"library_source": {"romm_url": "https://romm.example"}}
    before = dict(config)
    preferred = registry.preferred_title_id("gba", 42)
    slot = _gba_slot(preferred)
    blocked_next = _gba((slot + 1) % 0x1000)
    monkeypatch.setattr(
        registry,
        "configured_mounted_sd_title_ids",
        lambda value: frozenset({preferred, blocked_next}),
    )

    displayed = registry.displayed_title_id(config, "gba", 42)

    assert displayed == _gba((slot + 2) % 0x1000)
    assert config == before
    assert "three_ds_vc" not in config


def test_display_preview_returns_existing_assignment_without_inventory_scan(monkeypatch):
    config, assigned = registry.allocate_registered_title_id({}, "gba", 7, _gba(0x222))
    monkeypatch.setattr(
        registry,
        "configured_mounted_sd_title_ids",
        lambda value: (_ for _ in ()).throw(AssertionError("unexpected inventory scan")),
    )

    assert registry.displayed_title_id(config, "gba", 7) == assigned
