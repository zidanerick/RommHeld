from romm_vita_manager.emulators import EMULATORS


def test_dsvita_setup_copy_surfaces_runtime_prerequisites() -> None:
    definition = next(item for item in EMULATORS if item.key == "dsvita")

    assert "libshacccg.suprx" in definition.achievement_role
    assert "kubridge >= 0.3.1" in definition.achievement_role
    assert "*KERNEL" in definition.achievement_role
    assert "taiHEN *KERNEL" in definition.install_note
