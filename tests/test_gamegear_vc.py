from __future__ import annotations

import hashlib

from romm_vita_manager import classic_vc
from romm_vita_manager.classic_vc_title_fix import hardware_safe_classic_title_id
from romm_vita_manager.gamegear_vc import (
    _marchive_key,
    pack_gamegear_mdf,
    unpack_gamegear_mdf,
)


_DONOR_BASENAME = "GGSonic2_JUE_2012_09_12.GG.m"


def test_marchive_key_matches_independent_marchivebatchtool_vector() -> None:
    # Expected key generated independently from MArchiveBatchTool's published
    # MD5 + MT19937 init_by_array algorithm, not by decoding a donor fixture.
    assert _marchive_key(_DONOR_BASENAME).hex() == (
        "b02308c5ca75ec92296e6c003ebcc51b"
        "c54cafcd1c90244521d07faa623b0fd1"
        "dcd1feb11536c088c4b9c3e14146fcd2"
        "675cbedeb7a4e160d33f3143e775f1c9"
    )


def test_gamegear_mdf_pack_matches_known_synthetic_vector() -> None:
    raw = b"RommHeld Game Gear test vector\n" * 100
    packed = pack_gamegear_mdf(raw, _DONOR_BASENAME)

    assert packed[:8] == b"mdf\x00" + len(raw).to_bytes(4, "little")
    assert len(packed) == 69
    assert hashlib.sha256(packed).hexdigest() == (
        "02cfb95447a0178630a179bbf4e755cacc943a68b025b0e1c27baf83f2a95c52"
    )
    assert unpack_gamegear_mdf(packed, _DONOR_BASENAME) == raw


def test_gamegear_filename_is_part_of_archive_cipher() -> None:
    raw = bytes(range(256)) * 4
    packed = pack_gamegear_mdf(raw, _DONOR_BASENAME)

    try:
        unpack_gamegear_mdf(packed, "DifferentGame.GG.m")
    except ValueError as exc:
        assert "decompress" in str(exc).lower()
    else:
        raise AssertionError("MArchive unexpectedly decoded with the wrong donor filename")


def test_gamegear_family_is_installed_in_validated_classic_backend() -> None:
    assert "gamegear" in classic_vc._CLASSIC_FAMILIES
    assert classic_vc._CLASSIC_ROM_EXTENSIONS["gamegear"] == (".gg",)
    assert callable(classic_vc.prepare_runtime_payload)
    title_id = hardware_safe_classic_title_id(222, "gamegear")
    assert title_id[:4] == bytes.fromhex("00040000")
    assert title_id[7] == 0
