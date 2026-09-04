from romm_vita_manager.romm_remote import _publisher_name


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
