from pathlib import Path

from romm_vita_manager.three_ds_setup import COMPONENTS, component_presence


def _component(key: str):
    return next(component for component in COMPONENTS if component.key == key)


def test_setup_twilight_quick_check_preserves_assets_without_claiming_launcher(tmp_path: Path):
    twilight = _component("twilight")
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)

    detected, marker = component_presence(tmp_path, twilight)
    assert not detected
    assert marker is None

    (tmp_path / "_nds" / "nds-bootstrap").mkdir()
    detected, marker = component_presence(tmp_path, twilight)
    assert not detected
    assert marker is not None
    assert "_nds/TWiLightMenu" in marker
    assert "_nds/nds-bootstrap" in marker


def test_setup_fbi_quick_check_ignores_theme_only_leftovers(tmp_path: Path):
    fbi = _component("fbi")
    (tmp_path / "fbi" / "theme").mkdir(parents=True)

    detected, marker = component_presence(tmp_path, fbi)
    assert not detected
    assert marker is None

    executable = tmp_path / "3ds" / "FBI" / "FBI.3dsx"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"3dsx")

    detected, marker = component_presence(tmp_path, fbi)
    assert detected
    assert marker is not None
    matched = marker.split("; ")
    assert "3ds/FBI/FBI.3dsx" in matched
    assert "fbi/theme" not in matched


def test_setup_fbi_quick_check_detects_sd_installed_cia_title(tmp_path: Path):
    fbi = _component("fbi")
    title_id = "000400000F800100"
    title_path = (
        tmp_path
        / "Nintendo 3DS"
        / ("1" * 32)
        / ("2" * 32)
        / "title"
        / title_id[:8]
        / title_id[8:]
    )
    title_path.mkdir(parents=True)

    detected, marker = component_presence(tmp_path, fbi)

    assert detected
    assert marker == "Nintendo 3DS/<ID0>/<ID1>/title/00040000/0F800100"


def test_setup_open_agb_firm_quick_check_requires_firm_payload(tmp_path: Path):
    open_agb = _component("open-agb-firm")
    (tmp_path / "3ds" / "open_agb_firm").mkdir(parents=True)
    (tmp_path / "3ds" / "open_agb_firm" / "gba_db.bin").write_bytes(b"db")

    detected, marker = component_presence(tmp_path, open_agb)
    assert not detected
    assert marker is None

    payload = tmp_path / "luma" / "payloads" / "open_agb_firm.firm"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"firm")

    detected, marker = component_presence(tmp_path, open_agb)
    assert detected
    assert marker == "luma/payloads/open_agb_firm.firm"
