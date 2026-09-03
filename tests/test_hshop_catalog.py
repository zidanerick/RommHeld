from romm_vita_manager.hshop_catalog import _parse_entry, _title_score


def test_parse_virtual_console_search_entry():
    release = _parse_entry(
        "/t/3458",
        "Pokemon Card GB content in virtual-console ➞ japan "
        "Virtual Console: Game Boy Color 3458 ID Pirate Legit Content Type "
        "0004000000119F00 Title ID 4.05 MiB 32 Size 0.0.0 (0) Version "
        "CTR-N-QBBJ Product Code",
    )
    assert release is not None
    assert release.title == "Pokemon Card GB"
    assert release.platform == "Game Boy Color"
    assert release.title_id == "0004000000119F00"
    assert release.product_code == "CTR-N-QBBJ"
    assert release.url.endswith("/t/3458")


def test_non_virtual_console_result_is_ignored():
    assert _parse_entry(
        "/t/2481",
        "Pokemon X content in games ➞ world 2481 ID Legit Content Type",
    ) is None


def test_title_matching_tolerates_symbols_and_accents():
    assert _title_score("PAC-MAN™", "PAC-MAN") == 100
    assert _title_score("Pokémon Red", "Pokemon Red") == 100
    assert _title_score("The Legend of Zelda Oracle of Seasons", "Legend of Zelda Oracle of Seasons") >= 85
