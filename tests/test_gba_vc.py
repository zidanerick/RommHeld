import io
import zipfile
from types import SimpleNamespace

from PIL import Image

import romm_vita_manager.gba_vc as gba_vc
from romm_vita_manager.gba_vc import (
    build_native_gba_cia,
    native_title_id_for_romm_id,
    prepare_gba_rom,
    prepare_vc_icon_artwork,
    prepare_vc_title_badge,
)


def test_native_title_id_is_valid_gba_vc_shape():
    title_id = native_title_id_for_romm_id(42)
    assert len(title_id) == 8
    assert title_id.hex().startswith("0004000000f")
    assert title_id.hex().endswith("00")


def test_native_title_id_is_stable():
    assert native_title_id_for_romm_id(42) == native_title_id_for_romm_id(42)
    assert native_title_id_for_romm_id(42) != native_title_id_for_romm_id(43)


def test_native_builder_rejects_blank_boot_logo_before_packaging():
    try:
        build_native_gba_cia(
            b"GBA TEST ROM",
            b"image",
            boot_logo=b"",
            title_id=native_title_id_for_romm_id(42),
            title_name="Test Game",
        )
    except ValueError as exc:
        assert "boot logo" in str(exc).lower()
    else:
        raise AssertionError("Expected blank AGB_FIRM boot logo to be rejected")


def test_native_builder_does_not_stamp_homebrew_publisher(monkeypatch):
    captured = {}

    class Request:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        gba_vc,
        "_require_agbcia",
        lambda: (Request, lambda request: SimpleNamespace(cia=b"cia")),
    )
    monkeypatch.setattr(gba_vc, "prepare_vc_icon_artwork", lambda artwork: b"icon")

    result = build_native_gba_cia(
        b"GBA TEST ROM",
        b"image",
        boot_logo=b"real-logo",
        title_id=native_title_id_for_romm_id(42),
        title_name="Test Game",
    )
    assert result == b"cia"
    assert captured["publisher"] == ""
    assert captured["icon_image"] == b"icon"
    assert captured["banner_image"] == b"image"
    assert captured["bottom_badge_image"] is None


def test_native_builder_uses_real_publisher_when_supplied(monkeypatch):
    captured = {}

    class Request:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        gba_vc,
        "_require_agbcia",
        lambda: (Request, lambda request: SimpleNamespace(cia=b"cia")),
    )
    monkeypatch.setattr(gba_vc, "prepare_vc_icon_artwork", lambda artwork: b"icon")

    build_native_gba_cia(
        b"GBA TEST ROM",
        b"image",
        boot_logo=b"real-logo",
        title_id=native_title_id_for_romm_id(42),
        title_name="Test Game",
        publisher="Nintendo",
    )
    assert captured["publisher"] == "Nintendo"


def test_native_builder_requires_donor_icon_with_official_banner():
    try:
        build_native_gba_cia(
            b"GBA TEST ROM",
            b"image",
            boot_logo=b"real-logo",
            donor_banner=b"donor-banner",
            title_id=native_title_id_for_romm_id(42),
            title_name="Metroid Fusion",
        )
    except ValueError as exc:
        message = str(exc).lower()
        assert "presentation cache" in message
        assert "re-prepare" in message
    else:
        raise AssertionError("Expected official-style GBA build without donor icon to be rejected")


def test_native_builder_uses_donor_derived_official_presentation(monkeypatch):
    captured = {}
    calls = {}

    class Request:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        gba_vc,
        "_require_agbcia",
        lambda: (Request, lambda request: SimpleNamespace(cia=b"cia")),
    )
    monkeypatch.setattr(
        gba_vc,
        "prepare_official_vc_icon_artwork",
        lambda donor_icon, artwork: calls.setdefault("icon", (donor_icon, artwork)) and b"retail-icon",
    )
    monkeypatch.setattr(
        gba_vc,
        "prepare_official_vc_front_artwork",
        lambda donor_banner, artwork, family: calls.setdefault(
            "front", (donor_banner, artwork, family)
        )
        and b"retail-front",
    )

    def badge(donor_banner, title, family, *, release_year=None):
        calls["badge"] = (donor_banner, title, family, release_year)
        return b"retail-badge"

    monkeypatch.setattr(gba_vc, "prepare_official_vc_badge", badge)

    result = build_native_gba_cia(
        b"GBA TEST ROM",
        b"image",
        boot_logo=b"real-logo",
        donor_banner=b"donor-banner",
        donor_icon=b"donor-smdh",
        release_year=2004,
        title_id=native_title_id_for_romm_id(42),
        title_name="Metroid Fusion",
        publisher="Nintendo",
    )

    assert result == b"cia"
    assert calls["icon"] == (b"donor-smdh", b"image")
    assert calls["front"] == (b"donor-banner", b"image", "gba")
    assert calls["badge"] == (b"donor-banner", "Metroid Fusion", "gba", 2004)
    assert captured["icon_image"] == b"retail-icon"
    assert captured["banner_image"] == b"retail-front"
    assert captured["donor_banner"] == b"donor-banner"
    assert captured["bottom_badge_image"] == b"retail-badge"
    assert captured["publisher"] == "Nintendo"


def test_prepare_vc_icon_artwork_preserves_portrait_cover_inside_square():
    source = Image.new("RGB", (120, 180), (20, 40, 60))
    source.paste((220, 100, 40), (20, 20, 100, 160))
    source_bytes = io.BytesIO()
    source.save(source_bytes, format="PNG")

    result = prepare_vc_icon_artwork(source_bytes.getvalue(), canvas_size=256)
    image = Image.open(io.BytesIO(result))
    assert image.size == (256, 256)
    assert image.format == "PNG"
    assert image.getpixel((0, 128)) == image.getpixel((255, 128))
    assert image.getpixel((128, 128)) != image.getpixel((0, 128))


def test_prepare_vc_title_badge_renders_visible_transparent_png():
    result = prepare_vc_title_badge("The Legend of Zelda: The Minish Cap", width=512, height=128)
    image = Image.open(io.BytesIO(result)).convert("RGBA")
    assert image.size == (512, 128)
    assert image.getchannel("A").getbbox() is not None
    assert image.getpixel((0, 0))[3] == 0


def test_prepare_gba_rom_extracts_gba_from_zip():
    raw_rom = b"GBA TEST ROM\x00" * 32
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Advance Wars (USA).gba", raw_rom)
        archive.writestr("README.txt", "metadata")

    assert prepare_gba_rom(buffer.getvalue()) == raw_rom


def test_prepare_gba_rom_rejects_zip_without_gba():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "metadata")

    try:
        prepare_gba_rom(buffer.getvalue())
    except ValueError as exc:
        assert "does not contain a .gba ROM" in str(exc)
    else:
        raise AssertionError("Expected ZIP without a GBA ROM to be rejected")
