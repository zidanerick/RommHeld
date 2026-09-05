from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from romm_vita_manager.vc_banner_patch import (
    _encode_texture_mips,
    _rebuild_cbmd_preserving_slots,
)


def test_rgb565_mip_chain_matches_donor_buffer_size() -> None:
    image = Image.new("RGB", (128, 128), (240, 80, 30))
    texture = SimpleNamespace(
        name="COMMON1",
        width=128,
        height=128,
        hw_format=3,
        mipmap_count=3,
    )
    encoded = _encode_texture_mips(image, texture)

    assert len(encoded) == (128 * 128 + 64 * 64 + 32 * 32) * 2
    assert encoded != bytes(len(encoded))


def test_rgba8_mip_chain_matches_snes_donor_shape() -> None:
    image = Image.new("RGBA", (128, 128), (30, 120, 220, 255))
    texture = SimpleNamespace(
        name="COMMON1",
        width=128,
        height=128,
        hw_format=0,
        mipmap_count=3,
    )
    encoded = _encode_texture_mips(image, texture)

    assert len(encoded) == (128 * 128 + 64 * 64 + 32 * 32) * 4


def test_gamegear_single_level_rgb565_shape() -> None:
    image = Image.new("RGB", (128, 128), (20, 40, 80))
    texture = SimpleNamespace(
        name="COMMON2",
        width=128,
        height=128,
        hw_format=3,
        mipmap_count=1,
    )
    encoded = _encode_texture_mips(image, texture)

    assert len(encoded) == 128 * 128 * 2


def test_cbmd_rebuild_preserves_common_localized_slots_and_cwav() -> None:
    from agbcia.formats import lz11

    common = b"CGFX-common-scene" * 40
    english = b"CGFX-english-title-plate" * 30
    donor_header = bytearray(0x88)
    donor_header[:4] = b"CBMD"
    common_encoded = lz11.compress(common)
    english_encoded = lz11.compress(english)
    donor_header[0x08:0x0C] = (0x88).to_bytes(4, "little")
    english_offset = 0x88 + len(common_encoded)
    donor_header[0x0C:0x10] = english_offset.to_bytes(4, "little")
    cwav_offset = english_offset + len(english_encoded)
    donor_header[0x84:0x88] = cwav_offset.to_bytes(4, "little")
    cwav = b"CWAV-synthetic-audio"
    donor = bytes(donor_header) + common_encoded + english_encoded + cwav

    rebuilt = _rebuild_cbmd_preserving_slots(
        donor,
        [(0, common + b"-patched"), (1, english + b"-patched")],
    )
    common_offset = int.from_bytes(rebuilt[0x08:0x0C], "little")
    localized_offset = int.from_bytes(rebuilt[0x0C:0x10], "little")
    rebuilt_cwav_offset = int.from_bytes(rebuilt[0x84:0x88], "little")

    assert common_offset == 0x88
    assert localized_offset > common_offset
    assert rebuilt_cwav_offset > localized_offset
    assert rebuilt[rebuilt_cwav_offset:] == cwav
    assert lz11.decompress(rebuilt[common_offset:]) == common + b"-patched"
    assert lz11.decompress(rebuilt[localized_offset:]) == english + b"-patched"
