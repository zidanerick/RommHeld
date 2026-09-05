from __future__ import annotations

from romm_vita_manager.hshop_catalog import (
    _parse_entry,
    _platform_matches,
    _title_score,
    find_official_vc_release,
    find_vc_seed_by_title_id,
)


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


def test_parse_new3ds_snes_product_code():
    release = _parse_entry(
        "/t/8509",
        "Mario's Super Picross content in virtual-console ➞ europe "
        "Virtual Console: Super Nintendo Compatible only with New 3DS systems 8509 ID "
        "Pirate Legit Content Type 000400000F706600 Title ID 4.82 MiB 38 Size "
        "0.0.0 (0) Version KTR-N-UBGP Product Code",
    )
    assert release is not None
    assert release.title_id == "000400000F706600"
    assert release.product_code == "KTR-N-UBGP"


def test_non_virtual_console_result_is_ignored():
    assert _parse_entry(
        "/t/2481",
        "Pokemon X content in games ➞ world 2481 ID Legit Content Type",
    ) is None


def test_title_matching_tolerates_symbols_and_accents():
    assert _title_score("PAC-MAN™", "PAC-MAN") == 100
    assert _title_score("Pokémon Red", "Pokemon Red") == 100
    assert _title_score("The Legend of Zelda Oracle of Seasons", "Legend of Zelda Oracle of Seasons") >= 85


def test_platform_matching_keeps_game_boy_families_distinct():
    assert _platform_matches("game boy", "Game Boy")
    assert not _platform_matches("game boy", "Game Boy Color")
    assert not _platform_matches("game boy", "Game Boy Advance")
    assert _platform_matches("game boy color", "Game Boy Color")
    assert _platform_matches(
        "super nintendo",
        "Super Nintendo Compatible only with New 3DS systems",
    )


class _Response:
    def __init__(self, data: str):
        self.data = data.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit: int) -> bytes:
        return self.data


class _Opener:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.urls: list[str] = []

    def open(self, req, timeout: float):
        self.urls.append(req.full_url)
        return _Response(self.responses.pop(0))


def test_gb_official_lookup_does_not_return_gbc_release_with_same_title():
    search = """
    <html><body>
    <a href="/t/1001">
    Example Game content in virtual-console ➞ usa
    Virtual Console: Game Boy Color 1001 ID Pirate Legit Content Type
    0004000000111100 Title ID 4.00 MiB 32 Size 0.0.0 (0) Version CTR-N-ABCE Product Code
    </a>
    <a href="/t/1002">
    Example Game content in virtual-console ➞ usa
    Virtual Console: Game Boy 1002 ID Pirate Legit Content Type
    0004000000222200 Title ID 4.00 MiB 32 Size 0.0.0 (0) Version CTR-N-ABCD Product Code
    </a>
    </body></html>
    """
    release = find_official_vc_release("Example Game", "gb", opener=_Opener([search]))
    assert release is not None
    assert release.platform == "Game Boy"
    assert release.title_id == "0004000000222200"


def test_snes_seed_lookup_uses_catalogue_metadata_only():
    search = """
    <html><body><a href="/t/8509">
    Mario's Super Picross content in virtual-console ➞ europe
    Virtual Console: Super Nintendo Compatible only with New 3DS systems 8509 ID
    Pirate Legit Content Type 000400000F706600 Title ID 4.82 MiB 38 Size
    0.0.0 (0) Version KTR-N-UBGP Product Code
    </a></body></html>
    """
    detail = """
    <html><body><p>Title ID: 000400000F706600</p>
    <p><b>Seed:</b> <code>5e8b9a1f0754c12559c5ceccbe2c3652</code></p></body></html>
    """
    opener = _Opener([search, detail])
    seed = find_vc_seed_by_title_id("000400000F706600", opener=opener)

    assert seed == bytes.fromhex("5e8b9a1f0754c12559c5ceccbe2c3652")
    assert len(opener.urls) == 2
    assert "t%3A000400000F706600" in opener.urls[0]
    assert opener.urls[1].endswith("/t/8509")
