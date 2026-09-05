import romm_vita_manager.vc_title_id_registry as registry


def _gba(slot: int) -> bytes:
    return bytes.fromhex(f"0004000000F{slot:03X}00")


def _classic(slot: int) -> bytes:
    return bytes.fromhex(f"00040000{((0x0E0000 + slot) << 8):08X}")


def test_preferred_title_ids_are_pure_family_specific_candidates():
    gba = registry.preferred_title_id("gba", 42)
    gb = registry.preferred_title_id("gb", 42)
    gbc = registry.preferred_title_id("gbc", 42)

    assert gba.hex().startswith("0004000000f")
    assert gba.endswith(b"\x00")
    assert gb.hex().startswith("00040000")
    assert gb.endswith(b"\x00")
    assert gb != gbc
    assert registry.preferred_title_id("gba", 42) == gba


def test_displayed_title_id_does_not_persist_unallocated_candidate():
    config = {"library_source": {"romm_url": "https://romm.example"}}
    before = dict(config)
    displayed = registry.displayed_title_id(config, "gba", 42)

    assert displayed == registry.preferred_title_id("gba", 42)
    assert config == before
    assert "three_ds_vc" not in config


def test_gba_allocation_preserves_preferred_slot_when_free():
    updated, title_id = registry.allocate_registered_title_id({}, "gba", 42, _gba(0x123))
    assert title_id == _gba(0x123)
    assert list(updated["three_ds_vc"]["title_id_allocations"].values()) == [title_id.hex()]


def test_gba_allocation_probes_on_collision_and_stays_stable():
    config, first = registry.allocate_registered_title_id({}, "gba", 1, _gba(0x222))
    config, second = registry.allocate_registered_title_id(config, "gba", 2, _gba(0x222))
    assert first == _gba(0x222)
    assert second == _gba(0x223)

    same_config, repeated = registry.allocate_registered_title_id(config, "gba", 2, _gba(0x222))
    assert repeated == second
    assert same_config == config


def test_allocation_skips_explicit_reserved_target_title_id():
    updated, title_id = registry.allocate_registered_title_id(
        {},
        "gba",
        2,
        _gba(0x222),
        reserved_title_ids=(_gba(0x222),),
    )
    assert title_id == _gba(0x223)
    assert updated["three_ds_vc"]["title_id_allocations"]["gba:default:2"] == _gba(0x223).hex()


def test_existing_assignment_stays_stable_if_later_listed_as_reserved():
    config, first = registry.allocate_registered_title_id({}, "gba", 2, _gba(0x222))
    same_config, repeated = registry.allocate_registered_title_id(
        config,
        "gba",
        2,
        _gba(0x222),
        reserved_title_ids=(first,),
    )
    assert repeated == first
    assert same_config == config


def test_classic_families_share_one_collision_pool():
    config, gb = registry.allocate_registered_title_id({}, "gb", 11, _classic(0x3456))
    config, nes = registry.allocate_registered_title_id(config, "nes", 12, _classic(0x3456))
    assert gb == _classic(0x3456)
    assert nes == _classic(0x3457)


def test_same_romm_id_on_different_servers_gets_independent_identity():
    first_config = {"library_source": {"romm_url": "https://one.example"}}
    first_config, first = registry.allocate_registered_title_id(first_config, "gba", 7, _gba(0x100))

    second_config = dict(first_config)
    second_config["library_source"] = {"romm_url": "https://two.example"}
    second_config, second = registry.allocate_registered_title_id(second_config, "gba", 7, _gba(0x100))

    assert first == _gba(0x100)
    assert second == _gba(0x101)
    allocations = second_config["three_ds_vc"]["title_id_allocations"]
    assert len(allocations) == 2


def test_invalid_persisted_duplicate_is_reallocated():
    base = {
        "three_ds_vc": {
            "title_id_allocations": {
                "gba:default:1": _gba(0x300).hex(),
                "gba:default:2": _gba(0x300).hex(),
            }
        }
    }
    updated, title_id = registry.allocate_registered_title_id(base, "gba", 2, _gba(0x300))
    assert title_id == _gba(0x301)
    assert updated["three_ds_vc"]["title_id_allocations"]["gba:default:2"] == _gba(0x301).hex()


def test_persist_registered_title_id_is_the_explicit_write_boundary(monkeypatch):
    saved = []
    config = {"library_source": {"romm_url": "https://romm.example"}}
    monkeypatch.setattr(registry, "load_config", lambda: config)
    monkeypatch.setattr(registry, "save_config", lambda value: saved.append(value))

    displayed = registry.displayed_title_id(config, "gba", 99)
    assert saved == []

    updated, persisted = registry.persist_registered_title_id("gba", 99)
    assert persisted == displayed
    assert saved == [updated]
    assert registry.configured_title_id(updated, "gba", 99) == persisted
