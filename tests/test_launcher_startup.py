from __future__ import annotations

from launcher import _workspace_is_configured


def _config(
    workspace: str,
    *,
    mode: str = "local",
    local_root: str = "/media/library",
    romm_url: str = "",
    api_token: str = "",
    setup_complete: bool = True,
) -> dict:
    return {
        "setup_complete": setup_complete,
        "active_console": workspace,
        "library_source": {
            "mode": mode,
            "local_root": local_root,
            "romm_url": romm_url,
            "api_token": api_token,
        },
    }


def test_first_run_requires_selector() -> None:
    assert not _workspace_is_configured(_config("vita", setup_complete=False))


def test_invalid_saved_workspace_requires_selector() -> None:
    assert not _workspace_is_configured(_config("unknown"))


def test_returning_local_workspace_does_not_require_live_path() -> None:
    # Startup deliberately checks saved configuration, not current mount state.
    # An offline removable/library path should open the workspace and surface an
    # actionable runtime state instead of replaying onboarding.
    assert _workspace_is_configured(
        _config("vita", local_root="/definitely/not/mounted/right/now")
    )
    assert _workspace_is_configured(
        _config("3ds", local_root="/definitely/not/mounted/right/now")
    )
    assert _workspace_is_configured(
        _config("ds", local_root="/definitely/not/mounted/right/now")
    )


def test_local_workspace_requires_a_saved_root() -> None:
    assert not _workspace_is_configured(_config("vita", local_root=""))


def test_romm_source_is_only_valid_for_supported_workspace() -> None:
    credentials = {
        "mode": "romm_api",
        "local_root": "",
        "romm_url": "https://romm.example.com",
        "api_token": "token",
    }
    assert _workspace_is_configured(_config("3ds", **credentials))
    assert not _workspace_is_configured(_config("vita", **credentials))
    assert not _workspace_is_configured(_config("ds", **credentials))


def test_romm_workspace_requires_saved_url_and_token() -> None:
    assert not _workspace_is_configured(
        _config("3ds", mode="romm_api", local_root="", romm_url="", api_token="token")
    )
    assert not _workspace_is_configured(
        _config(
            "3ds",
            mode="romm_api",
            local_root="",
            romm_url="https://romm.example.com",
            api_token="",
        )
    )
