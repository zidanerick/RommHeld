from __future__ import annotations

from unittest.mock import patch

import pytest

from romm_vita_manager.romm_api import (
    RomMApiError,
    normalize_romm_url,
    test_connection as check_connection,
)


def test_normalize_romm_instance_url():
    assert normalize_romm_url("https://romm.example.test/") == "https://romm.example.test"


def test_normalize_romm_api_url():
    assert normalize_romm_url("https://romm.example.test/api") == "https://romm.example.test"
    assert normalize_romm_url("https://romm.example.test/api/") == "https://romm.example.test"


def test_rejects_malformed_url():
    with pytest.raises(ValueError):
        normalize_romm_url("romm.example.test")


def test_client_token_prefix_is_checked():
    with pytest.raises(ValueError, match="beginning with rmm_"):
        check_connection("https://romm.example.test", "not-a-client-token")


def test_403_is_reported_as_scope_error():
    with patch(
        "romm_vita_manager.romm_api.request.urlopen",
        side_effect=__import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            "https://romm.example.test/api/platforms", 403, "Forbidden", {}, None
        ),
    ):
        with pytest.raises(RomMApiError, match="platforms.read"):
            check_connection("https://romm.example.test", "rmm_" + "a" * 64)
