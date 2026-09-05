from __future__ import annotations

from PIL import Image

from romm_vita_manager.vc_banner_patch import _encode_l4_tiled
from romm_vita_manager.vc_presentation import _decode_l4


def test_l4_decoder_expands_low_and_high_nibbles_in_pica_order() -> None:
    raw = bytearray(32)
    raw[0] = 0xE1

    image = _decode_l4(bytes(raw), 8, 8)

    assert image.mode == "L"
    assert image.getpixel((0, 0)) == 0x11
    assert image.getpixel((1, 0)) == 0xEE


def test_l4_encoder_decoder_round_trip_on_representable_values() -> None:
    image = Image.new("L", (8, 8), 0)
    for y in range(8):
        for x in range(8):
            image.putpixel((x, y), ((x + y) & 0x0F) * 0x11)

    encoded = _encode_l4_tiled(image, 8, 8)
    decoded = _decode_l4(encoded, 8, 8)

    assert decoded.tobytes() == image.tobytes()
