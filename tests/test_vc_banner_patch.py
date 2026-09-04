from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from romm_vita_manager.vc_banner_patch import _encode_texture_mips


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
