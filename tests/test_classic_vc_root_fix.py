from romm_vita_manager import classic_vc


def _path_hash(name: bytes, parent: int) -> int:
    value = (parent ^ 123456789) & 0xFFFFFFFF
    for index in range(0, len(name), 2):
        value = ((value >> 5) | (value << 27)) & 0xFFFFFFFF
        value ^= name[index] | (name[index + 1] << 8)
    return value


def test_classic_romfs_root_points_to_self_and_is_hashed() -> None:
    romfs = classic_vc.build_romfs({"/rom/TEST.000": b"ROM"})
    level3_offset = classic_vc._find_level3_offset(romfs)
    level3 = romfs[level3_offset:]

    dir_hash_offset = int.from_bytes(level3[0x04:0x08], "little")
    dir_hash_size = int.from_bytes(level3[0x08:0x0C], "little")
    dir_meta_offset = int.from_bytes(level3[0x0C:0x10], "little")
    root = dir_meta_offset

    assert int.from_bytes(level3[root : root + 4], "little") == 0
    assert int.from_bytes(level3[root + 4 : root + 8], "little") == 0xFFFFFFFF

    # Root is a real directory metadata entry and therefore participates in
    # the directory hash table.  This check does not use RommHeld's parser.
    buckets = dir_hash_size // 4
    bucket = _path_hash(b"", 0) % buckets
    head = int.from_bytes(
        level3[dir_hash_offset + bucket * 4 : dir_hash_offset + bucket * 4 + 4], "little"
    )
    seen: set[int] = set()
    while head != 0xFFFFFFFF and head != 0 and head not in seen:
        seen.add(head)
        entry = dir_meta_offset + head
        head = int.from_bytes(level3[entry + 0x10 : entry + 0x14], "little")
    assert head == 0
