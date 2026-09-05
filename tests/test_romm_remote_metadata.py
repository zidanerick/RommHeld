from romm_vita_manager.romm_remote import _publisher_name, _release_year


def test_publisher_name_uses_direct_romm_metadata():
    assert _publisher_name({"publisher": "Nintendo"}) == "Nintendo"


def test_publisher_name_reads_nested_metadata():
    assert _publisher_name({"metadata": {"publisher": "Capcom"}}) == "Capcom"


def test_publisher_name_accepts_publisher_lists():
    assert _publisher_name({"publishers": [{"name": "Sega"}]}) == "Sega"


def test_publisher_name_ignores_non_publisher_company_roles():
    assert (
        _publisher_name(
            {
                "companies": [
                    {"name": "Developer Studio", "role": "developer"},
                    {"name": "Publisher Co", "role": "publisher"},
                ]
            }
        )
        == "Publisher Co"
    )


def test_release_year_uses_direct_year():
    assert _release_year({"release_year": 2001}) == 2001


def test_release_year_reads_iso_metadata_date():
    assert _release_year({"metadata": {"first_release_date": "1998-12-01"}}) == 1998


def test_release_year_reads_unix_timestamp():
    assert _release_year({"first_release_date": 978307200}) == 2001


def test_release_year_rejects_implausible_year():
    assert _release_year({"release_year": 42}) is None
