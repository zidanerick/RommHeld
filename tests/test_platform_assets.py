from pathlib import Path

from romm_vita_manager.platform_assets import get_platform_assets


def test_supported_platforms_have_valid_asset_paths() -> None:
    for key in ("vita", "3ds", "ds"):
        assets = get_platform_assets(key)
        assert assets is not None
        assert assets.logo_role in {"icon", "wordmark"}
        assert assets.path("device_large").is_file()
        assert assets.path("device_small").is_file()
        assert assets.path("logo").is_file()
        assert assets.path("logo_dark").is_file()


def test_3ds_uses_icon_identity_role() -> None:
    assets = get_platform_assets("3ds")
    assert assets is not None
    assert assets.logo_role == "icon"
    assert assets.path("logo_simpleicons").is_file()
    assert assets.path("logo_simpleicons_dark").is_file()


def test_vita_and_ds_use_wordmark_identity_role() -> None:
    for key in ("vita", "ds"):
        assets = get_platform_assets(key)
        assert assets is not None
        assert assets.logo_role == "wordmark"
