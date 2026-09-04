from __future__ import annotations

import hashlib


def _align(value: int, boundary: int) -> int:
    remainder = value % boundary
    return value if remainder == 0 else value + boundary - remainder


def _hash_blocks_padded(data: bytes, block_size: int) -> bytes:
    """Hash complete IVFC blocks, zero-padding the final short block.

    Real 3DS RomFS images hash every 0x1000-byte block, including the final
    partially-used block after zero padding. Hashing only the short tail gives
    a self-consistent image to our own parser but fails hardware IVFC
    verification.
    """
    if not data:
        return b""
    return b"".join(
        hashlib.sha256(data[offset : offset + block_size].ljust(block_size, b"\x00")).digest()
        for offset in range(0, len(data), block_size)
    )


def install() -> None:
    """Install the hardware-correct RomFS implementation into classic_vc.

    This is kept separate while the GB/GBC injector is undergoing real-device
    validation. It replaces only the RomFS layout/hash helpers; the donor
    runtime, metadata and CIA assembly paths remain unchanged.
    """
    from . import classic_vc as vc

    def find_level3_offset(romfs: bytes) -> int:
        if romfs[:4] != b"IVFC":
            raise ValueError("VC donor RomFS is not an IVFC image.")

        # Retail 3DS RomFS stores Level 3 physically at 0x1000. The IVFC
        # descriptor's Level-3 offset is a *logical* hash-tree offset, not a
        # physical file offset. Treating it as a file position was the original
        # GB/GBC hardware bug.
        if vc._looks_like_level3(romfs, 0x1000):
            return 0x1000

        # Keep a conservative fallback for unusual/synthetic fixtures.
        limit = min(len(romfs), 0x400000)
        for offset in range(0x20, limit, 0x10):
            if vc._looks_like_level3(romfs, offset):
                return offset
        raise ValueError("Unable to locate the RomFS Level 3 filesystem header.")

    def build_romfs(files: dict[str, bytes], *, block_size_log2: int = 12) -> bytes:
        level3 = vc._build_level3(files)
        block_size = 1 << block_size_log2

        # Hardware layout used by Nintendo-authored RomFS:
        #   header/master hash -> Level 3 -> Level 1 -> Level 2
        # The IVFC header offsets are logical hash-tree offsets, not these
        # physical locations.
        level2 = _hash_blocks_padded(level3, block_size)
        level1 = _hash_blocks_padded(level2, block_size)
        master = _hash_blocks_padded(level1, block_size)

        def padded(data: bytes) -> bytes:
            return data.ljust(_align(len(data), block_size), b"\x00")

        level3_padded = padded(level3)
        level1_padded = padded(level1)
        level2_padded = padded(level2)

        # Logical offsets match retail images: L1 starts at 0, L2 follows the
        # padded L1 logical range, and L3 follows padded L2.
        level1_logical = 0
        level2_logical = len(level1_padded)
        level3_logical = level2_logical + len(level2_padded)

        header = (
            b"IVFC"
            + (0x10000).to_bytes(4, "little")
            + len(master).to_bytes(4, "little")
            + level1_logical.to_bytes(8, "little")
            + len(level1).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + level2_logical.to_bytes(8, "little")
            + len(level2).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + level3_logical.to_bytes(8, "little")
            + len(level3).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + bytes(4)
            + (0).to_bytes(4, "little")
        ).ljust(0x60, b"\x00")

        # The master-hash region occupies the remainder of the first block;
        # Level 3 begins at physical offset 0x1000 exactly.
        first_block = (header + master).ljust(block_size, b"\x00")
        return first_block + level3_padded + level1_padded + level2_padded

    vc._find_level3_offset = find_level3_offset
    vc._hash_blocks = _hash_blocks_padded
    vc.build_romfs = build_romfs
