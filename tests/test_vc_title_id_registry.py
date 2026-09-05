import romm_vita_manager.vc_title_id_registry as registry


def _gba(slot: int) -> bytes:
    return bytes.fromhex(f"0004000000F{slot:03X}00")


def _classic(slot: int) -> bytes:
    return bytes.fromhex(f"00040000{((0x0E0000 + slot) << 8):08X}")


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
