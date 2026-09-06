from romm_vita_manager.ftp_file_safety import destructive_path_risk


def test_3ds_console_managed_title_tree_is_critical():
    risk = destructive_path_risk("3ds", "Nintendo 3DS/0123/title")

    assert risk.level == "critical"
    assert "title/save-data tree" in risk.message


def test_3ds_homebrew_tree_is_caution_not_critical():
    risk = destructive_path_risk("Nintendo 3DS", "3ds/ftpd/ftpd.3dsx")

    assert risk.level == "caution"
    assert "Homebrew Launcher" in risk.message


def test_vita_app_and_license_trees_are_critical():
    for path in ("app/ABCD12345", "license/app/ABCD12345"):
        risk = destructive_path_risk("Vita", path)
        assert risk.level == "critical"


def test_vita_data_and_pspemu_are_caution():
    assert destructive_path_risk("PlayStation TV", "data/tool/config.ini").level == "caution"
    assert destructive_path_risk("Vita", "pspemu/ISO/game.iso").level == "caution"


def test_normal_rom_path_uses_plain_destructive_warning():
    risk = destructive_path_risk("3ds", "roms/gba/game.gba")

    assert risk.level == "normal"
    assert risk.title == "Delete remote item"
