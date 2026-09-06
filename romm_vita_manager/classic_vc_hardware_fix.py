from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .gba_vc import prepare_vc_title_badge
from .vc_metadata import normalize_vc_metadata

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


_INSTALLED = False
_NO_ENTRY = 0xFFFFFFFF


def _align(value: int, boundary: int) -> int:
    remainder = value % boundary
    return value if remainder == 0 else value + boundary - remainder


def _hash_blocks_padded(data: bytes, block_size: int) -> bytes:
    """Hash complete IVFC blocks, zero-padding the final short block."""
    if not data:
        return b""
    return b"".join(
        hashlib.sha256(data[offset : offset + block_size].ljust(block_size, b"\x00")).digest()
        for offset in range(0, len(data), block_size)
    )


def _build_level3_retail(vc, files: dict[str, bytes]) -> bytes:
    """Build nested Level-3 RomFS metadata using Nintendo/3dstools conventions.

    The initial classic-VC implementation made its own parser and writer agree
    with each other, which hid two on-disk differences from retail RomFS:
    the root directory was omitted from the directory hash table and the root
    parent used the no-entry sentinel.  A real reader hashes *all* directory
    metadata entries, including root, and root's parent points to itself.
    """
    normalized: dict[str, bytes] = {}
    for raw_path, data in files.items():
        path = "/" + raw_path.strip("/")
        if path == "/":
            raise ValueError("RomFS file path cannot be the root directory.")
        normalized[path] = bytes(data)

    dir_paths = {"/"}
    for path in normalized:
        current = ""
        for part in path.strip("/").split("/")[:-1]:
            current += "/" + part
            dir_paths.add(current)

    # 3DS RomFS metadata is breadth-first by directory level.  Sorting within
    # a level makes RommHeld output deterministic without changing semantics.
    ordered_dirs = ["/"] + sorted(
        (path for path in dir_paths if path != "/"),
        key=lambda path: (path.count("/"), path.casefold()),
    )
    dir_names = {
        path: (b"" if path == "/" else path.rsplit("/", 1)[-1].encode("utf-16-le"))
        for path in ordered_dirs
    }
    dir_sizes = {path: 0x18 + _align(len(dir_names[path]), 4) for path in ordered_dirs}
    dir_offsets: dict[str, int] = {}
    cursor = 0
    for path in ordered_dirs:
        dir_offsets[path] = cursor
        cursor += dir_sizes[path]

    ordered_files = sorted(
        normalized,
        key=lambda path: (path.rsplit("/", 1)[0].casefold(), path.casefold()),
    )
    file_names = {
        path: path.rsplit("/", 1)[-1].encode("utf-16-le") for path in ordered_files
    }
    file_sizes = {path: 0x20 + _align(len(file_names[path]), 4) for path in ordered_files}
    file_offsets: dict[str, int] = {}
    cursor = 0
    for path in ordered_files:
        file_offsets[path] = cursor
        cursor += file_sizes[path]

    child_dirs: dict[str, list[str]] = {path: [] for path in ordered_dirs}
    child_files: dict[str, list[str]] = {path: [] for path in ordered_dirs}
    for path in ordered_dirs:
        if path == "/":
            continue
        parent = path.rsplit("/", 1)[0] or "/"
        child_dirs[parent].append(path)
    for path in ordered_files:
        parent = path.rsplit("/", 1)[0] or "/"
        child_files[parent].append(path)
    for children in child_dirs.values():
        children.sort(key=str.casefold)
    for children in child_files.values():
        children.sort(key=str.casefold)

    # The hash-table entry count is the metadata-entry count, which includes
    # root.  devkitPro 3dstools does the same and retail Oracle of Seasons has
    # six directory entries and seven buckets (rather than five buckets when
    # root is incorrectly excluded).
    dir_bucket_count = vc._bucket_count(len(ordered_dirs))
    dir_buckets = [_NO_ENTRY] * dir_bucket_count
    dir_hash_next: dict[str, int] = {}
    for path in ordered_dirs:
        parent_offset = 0 if path == "/" else dir_offsets[path.rsplit("/", 1)[0] or "/"]
        bucket = vc._path_hash(dir_names[path], parent_offset) % dir_bucket_count
        dir_hash_next[path] = dir_buckets[bucket]
        dir_buckets[bucket] = dir_offsets[path]

    file_bucket_count = vc._bucket_count(len(ordered_files))
    file_buckets = [_NO_ENTRY] * file_bucket_count
    file_hash_next: dict[str, int] = {}
    for path in ordered_files:
        parent = path.rsplit("/", 1)[0] or "/"
        bucket = vc._path_hash(file_names[path], dir_offsets[parent]) % file_bucket_count
        file_hash_next[path] = file_buckets[bucket]
        file_buckets[bucket] = file_offsets[path]

    directory_metadata = bytearray()
    for path in ordered_dirs:
        if path == "/":
            parent = 0  # root points to itself
            sibling = _NO_ENTRY
        else:
            parent_path = path.rsplit("/", 1)[0] or "/"
            parent = dir_offsets[parent_path]
            siblings = child_dirs[parent_path]
            index = siblings.index(path)
            sibling = dir_offsets[siblings[index + 1]] if index + 1 < len(siblings) else _NO_ENTRY

        children = child_dirs[path]
        files_here = child_files[path]
        first_child = dir_offsets[children[0]] if children else _NO_ENTRY
        first_file = file_offsets[files_here[0]] if files_here else _NO_ENTRY
        encoded = dir_names[path]
        directory_metadata += (
            parent.to_bytes(4, "little")
            + sibling.to_bytes(4, "little")
            + first_child.to_bytes(4, "little")
            + first_file.to_bytes(4, "little")
            + dir_hash_next[path].to_bytes(4, "little")
            + len(encoded).to_bytes(4, "little")
            + encoded.ljust(_align(len(encoded), 4), b"\x00")
        )

    # File data in retail RomFS is 16-byte aligned.  Preserve that even though
    # some generic 3DS builders only guarantee four-byte alignment.
    data_offsets: dict[str, int] = {}
    file_data = bytearray()
    for path in ordered_files:
        aligned = _align(len(file_data), 0x10)
        if aligned != len(file_data):
            file_data += bytes(aligned - len(file_data))
        data_offsets[path] = len(file_data)
        file_data += normalized[path]

    file_metadata = bytearray()
    for path in ordered_files:
        parent_path = path.rsplit("/", 1)[0] or "/"
        siblings = child_files[parent_path]
        index = siblings.index(path)
        sibling = file_offsets[siblings[index + 1]] if index + 1 < len(siblings) else _NO_ENTRY
        encoded = file_names[path]
        file_metadata += (
            dir_offsets[parent_path].to_bytes(4, "little")
            + sibling.to_bytes(4, "little")
            + data_offsets[path].to_bytes(8, "little")
            + len(normalized[path]).to_bytes(8, "little")
            + file_hash_next[path].to_bytes(4, "little")
            + len(encoded).to_bytes(4, "little")
            + encoded.ljust(_align(len(encoded), 4), b"\x00")
        )

    directory_hash_table = b"".join(value.to_bytes(4, "little") for value in dir_buckets)
    file_hash_table = b"".join(value.to_bytes(4, "little") for value in file_buckets)

    header_size = 0x28
    dir_hash_offset = header_size
    dir_meta_offset = dir_hash_offset + len(directory_hash_table)
    file_hash_offset = dir_meta_offset + len(directory_metadata)
    file_meta_offset = file_hash_offset + len(file_hash_table)
    file_data_offset = _align(file_meta_offset + len(file_metadata), 0x10)
    metadata_padding = bytes(file_data_offset - (file_meta_offset + len(file_metadata)))

    header = (
        header_size.to_bytes(4, "little")
        + dir_hash_offset.to_bytes(4, "little")
        + len(directory_hash_table).to_bytes(4, "little")
        + dir_meta_offset.to_bytes(4, "little")
        + len(directory_metadata).to_bytes(4, "little")
        + file_hash_offset.to_bytes(4, "little")
        + len(file_hash_table).to_bytes(4, "little")
        + file_meta_offset.to_bytes(4, "little")
        + len(file_metadata).to_bytes(4, "little")
        + file_data_offset.to_bytes(4, "little")
    )
    return (
        header
        + directory_hash_table
        + bytes(directory_metadata)
        + file_hash_table
        + bytes(file_metadata)
        + metadata_padding
        + bytes(file_data)
    )


def validate_retail_romfs(romfs: bytes) -> None:
    """Independently validate the invariants a generated classic VC RomFS needs.

    This deliberately does not call RommHeld's normal RomFS parser.  The first
    implementation only round-tripped through its own parser, allowing writer
    and reader bugs to cancel each other out.  Generated payloads now fail the
    build on the PC if their IVFC tree or Level-3 metadata is inconsistent.
    """
    if len(romfs) < 0x1000 or romfs[:4] != b"IVFC":
        raise ValueError("Generated VC RomFS is missing a valid IVFC header.")
    if int.from_bytes(romfs[4:8], "little") != 0x10000:
        raise ValueError("Generated VC RomFS has the wrong IVFC magic number.")

    master_size = int.from_bytes(romfs[0x08:0x0C], "little")
    l1_logical = int.from_bytes(romfs[0x0C:0x14], "little")
    l1_size = int.from_bytes(romfs[0x14:0x1C], "little")
    l1_log2 = int.from_bytes(romfs[0x1C:0x20], "little")
    l2_logical = int.from_bytes(romfs[0x24:0x2C], "little")
    l2_size = int.from_bytes(romfs[0x2C:0x34], "little")
    l2_log2 = int.from_bytes(romfs[0x34:0x38], "little")
    l3_logical = int.from_bytes(romfs[0x3C:0x44], "little")
    l3_size = int.from_bytes(romfs[0x44:0x4C], "little")
    l3_log2 = int.from_bytes(romfs[0x4C:0x50], "little")

    if not master_size or not l1_size or not l2_size or not l3_size:
        raise ValueError("Generated VC RomFS contains an empty IVFC hash level.")
    if len({l1_log2, l2_log2, l3_log2}) != 1:
        raise ValueError("Generated VC RomFS uses inconsistent IVFC block sizes.")
    block_size = 1 << l3_log2
    if block_size != 0x1000:
        raise ValueError("Generated VC RomFS must use 0x1000-byte IVFC blocks.")

    expected_l2_logical = _align(l1_size, block_size)
    expected_l3_logical = expected_l2_logical + _align(l2_size, block_size)
    if l1_logical != 0 or l2_logical != expected_l2_logical or l3_logical != expected_l3_logical:
        raise ValueError("Generated VC RomFS has inconsistent IVFC logical offsets.")

    # Retail GB/GBC donors use a 0x5C-byte IVFC header and store 0x5C in
    # the second reserved word at 0x54.  Reproduce the donor convention rather
    # than depending on tolerant readers for a field Nintendo populates.
    if int.from_bytes(romfs[0x54:0x58], "little") != 0x5C:
        raise ValueError("Generated VC RomFS is missing the retail 0x5C IVFC header marker.")
    if int.from_bytes(romfs[0x58:0x5C], "little") != 0:
        raise ValueError("Generated VC RomFS has unexpected IVFC optional-info data.")

    l3_physical = 0x1000
    l1_physical = l3_physical + _align(l3_size, block_size)
    l2_physical = l1_physical + _align(l1_size, block_size)
    end = l2_physical + _align(l2_size, block_size)
    if end > len(romfs):
        raise ValueError("Generated VC RomFS IVFC levels extend past the image.")

    level3 = romfs[l3_physical : l3_physical + l3_size]
    level1 = romfs[l1_physical : l1_physical + l1_size]
    level2 = romfs[l2_physical : l2_physical + l2_size]
    master = romfs[0x60 : 0x60 + master_size]
    if _hash_blocks_padded(level3, block_size) != level2:
        raise ValueError("Generated VC RomFS Level-3 hash tree is invalid.")
    if _hash_blocks_padded(level2, block_size) != level1:
        raise ValueError("Generated VC RomFS Level-2 hash tree is invalid.")
    if _hash_blocks_padded(level1, block_size) != master:
        raise ValueError("Generated VC RomFS master hash is invalid.")

    if len(level3) < 0x28 or int.from_bytes(level3[0:4], "little") != 0x28:
        raise ValueError("Generated VC RomFS Level-3 header is invalid.")
    dir_hash_offset = int.from_bytes(level3[0x04:0x08], "little")
    dir_hash_size = int.from_bytes(level3[0x08:0x0C], "little")
    dir_meta_offset = int.from_bytes(level3[0x0C:0x10], "little")
    dir_meta_size = int.from_bytes(level3[0x10:0x14], "little")
    file_hash_offset = int.from_bytes(level3[0x14:0x18], "little")
    file_hash_size = int.from_bytes(level3[0x18:0x1C], "little")
    file_meta_offset = int.from_bytes(level3[0x1C:0x20], "little")
    file_meta_size = int.from_bytes(level3[0x20:0x24], "little")
    file_data_offset = int.from_bytes(level3[0x24:0x28], "little")

    if dir_hash_offset != 0x28:
        raise ValueError("Generated VC RomFS directory hash table is misplaced.")
    if not (
        dir_hash_offset + dir_hash_size == dir_meta_offset
        and dir_meta_offset + dir_meta_size == file_hash_offset
        and file_hash_offset + file_hash_size == file_meta_offset
        and file_meta_offset + file_meta_size <= file_data_offset
        and file_data_offset % 0x10 == 0
        and file_data_offset <= len(level3)
    ):
        raise ValueError("Generated VC RomFS Level-3 tables are not internally consistent.")
    if dir_hash_size % 4 or file_hash_size % 4:
        raise ValueError("Generated VC RomFS hash-table size is invalid.")

    # Parse every directory entry directly from metadata, then verify that the
    # independent hash-table chains can actually find it.
    directory_entries: dict[int, tuple[int, bytes, int]] = {}
    cursor = 0
    while cursor < dir_meta_size:
        base = dir_meta_offset + cursor
        if base + 0x18 > file_hash_offset:
            raise ValueError("Generated VC RomFS directory metadata is truncated.")
        parent = int.from_bytes(level3[base : base + 4], "little")
        next_hash = int.from_bytes(level3[base + 0x10 : base + 0x14], "little")
        name_size = int.from_bytes(level3[base + 0x14 : base + 0x18], "little")
        entry_size = 0x18 + _align(name_size, 4)
        if cursor + entry_size > dir_meta_size:
            raise ValueError("Generated VC RomFS directory name extends past metadata.")
        name = bytes(level3[base + 0x18 : base + 0x18 + name_size])
        directory_entries[cursor] = (parent, name, next_hash)
        cursor += entry_size
    if cursor != dir_meta_size or 0 not in directory_entries:
        raise ValueError("Generated VC RomFS directory metadata size is inconsistent.")
    if directory_entries[0][0] != 0:
        raise ValueError("Generated VC RomFS root directory does not point to itself.")

    dir_bucket_count = dir_hash_size // 4
    if dir_bucket_count < 3:
        raise ValueError("Generated VC RomFS directory hash table is too small.")
    for offset, (parent, name, _) in directory_entries.items():
        if parent not in directory_entries:
            raise ValueError("Generated VC RomFS directory points to an invalid parent.")
        bucket = 0
        value = (parent ^ 123456789) & 0xFFFFFFFF
        for index in range(0, len(name), 2):
            value = ((value >> 5) | (value << 27)) & 0xFFFFFFFF
            value ^= name[index] | (name[index + 1] << 8)
        bucket = value % dir_bucket_count
        chain = int.from_bytes(
            level3[dir_hash_offset + bucket * 4 : dir_hash_offset + bucket * 4 + 4], "little"
        )
        seen: set[int] = set()
        while chain != _NO_ENTRY and chain not in seen and chain != offset:
            seen.add(chain)
            entry = directory_entries.get(chain)
            if entry is None:
                raise ValueError("Generated VC RomFS directory hash chain points outside metadata.")
            chain = entry[2]
        if chain != offset:
            raise ValueError("Generated VC RomFS directory is unreachable from its hash table.")

    file_entries: dict[int, tuple[int, bytes, int, int, int]] = {}
    cursor = 0
    while cursor < file_meta_size:
        base = file_meta_offset + cursor
        if base + 0x20 > file_data_offset:
            raise ValueError("Generated VC RomFS file metadata is truncated.")
        parent = int.from_bytes(level3[base : base + 4], "little")
        data_offset = int.from_bytes(level3[base + 0x08 : base + 0x10], "little")
        data_size = int.from_bytes(level3[base + 0x10 : base + 0x18], "little")
        next_hash = int.from_bytes(level3[base + 0x18 : base + 0x1C], "little")
        name_size = int.from_bytes(level3[base + 0x1C : base + 0x20], "little")
        entry_size = 0x20 + _align(name_size, 4)
        if cursor + entry_size > file_meta_size:
            raise ValueError("Generated VC RomFS file name extends past metadata.")
        if parent not in directory_entries:
            raise ValueError("Generated VC RomFS file points to an invalid directory.")
        if data_offset % 0x10:
            raise ValueError("Generated VC RomFS file data is not 16-byte aligned.")
        if file_data_offset + data_offset + data_size > len(level3):
            raise ValueError("Generated VC RomFS file data extends past Level 3.")
        name = bytes(level3[base + 0x20 : base + 0x20 + name_size])
        file_entries[cursor] = (parent, name, next_hash, data_offset, data_size)
        cursor += entry_size
    if cursor != file_meta_size:
        raise ValueError("Generated VC RomFS file metadata size is inconsistent.")

    file_bucket_count = file_hash_size // 4
    for offset, (parent, name, _, _, _) in file_entries.items():
        value = (parent ^ 123456789) & 0xFFFFFFFF
        for index in range(0, len(name), 2):
            value = ((value >> 5) | (value << 27)) & 0xFFFFFFFF
            value ^= name[index] | (name[index + 1] << 8)
        bucket = value % file_bucket_count
        chain = int.from_bytes(
            level3[file_hash_offset + bucket * 4 : file_hash_offset + bucket * 4 + 4], "little"
        )
        seen: set[int] = set()
        while chain != _NO_ENTRY and chain not in seen and chain != offset:
            seen.add(chain)
            entry = file_entries.get(chain)
            if entry is None:
                raise ValueError("Generated VC RomFS file hash chain points outside metadata.")
            chain = entry[2]
        if chain != offset:
            raise ValueError("Generated VC RomFS file is unreachable from its hash table.")


def validate_classic_package_identity(
    *,
    ncch: bytes,
    exheader: bytes,
    donor_exheader: bytes,
    title_id: bytes,
    ticket: bytes,
    tmd: bytes,
) -> None:
    """Verify title identity is consistent across every generated package layer."""
    if len(title_id) != 8 or ncch[0x100:0x104] != b"NCCH":
        raise ValueError("Generated classic VC NCCH is invalid.")
    expected_disk_id = title_id[::-1]
    if ncch[0x108:0x110] != expected_disk_id or ncch[0x118:0x120] != expected_disk_id:
        raise ValueError("Generated classic VC NCCH title IDs do not match.")
    if not (ncch[0x18F] & 0x04):
        raise ValueError("Generated classic VC NCCH is not marked NoCrypto.")
    if exheader[0x1C8:0x1D0] != expected_disk_id or exheader[0x200:0x208] != expected_disk_id:
        raise ValueError("Generated classic VC exheader title IDs do not match the NCCH.")
    if exheader[0x400:] != donor_exheader[0x400:]:
        raise ValueError("Generated classic VC modified the donor's signed Access Descriptor.")
    if hashlib.sha256(exheader[:0x400]).digest() != ncch[0x160:0x180]:
        raise ValueError("Generated classic VC exheader hash is invalid.")
    if ticket[0x1DC:0x1E4] != title_id:
        raise ValueError("Generated classic VC ticket title ID does not match the NCCH.")
    if tmd[0x18C:0x194] != title_id:
        raise ValueError("Generated classic VC TMD title ID does not match the NCCH.")
    if int.from_bytes(tmd[0x1DE:0x1E0], "big") != 1:
        raise ValueError("Generated classic VC TMD does not describe exactly one content.")
    content_record = 0xB04
    content_size = int.from_bytes(tmd[content_record + 0x08 : content_record + 0x10], "big")
    content_hash = tmd[content_record + 0x10 : content_record + 0x30]
    if content_size != len(ncch) or content_hash != hashlib.sha256(ncch).digest():
        raise ValueError("Generated classic VC TMD content record does not match its NCCH.")


def install() -> None:
    """Install the hardware-validated GB/GBC VC implementation.

    The package keeps this compatibility install centralized because older
    modules imported classic_vc directly.  The implementation below is checked
    against 3dbrew, devkitPro 3dstools and the structure of user-supplied retail
    GB/GBC donors, and it validates every generated RomFS and package identity
    before returning a CIA.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    @dataclass(frozen=True)
    class HardwareClassicVcRuntime:
        family: str
        exheader: bytes
        code: bytes
        logo: bytes
        romfs_template: bytes
        rom_path: str
        donor_banner: bytes = b""

    original_extract_runtime = vc.extract_classic_vc_runtime

    def find_level3_offset(romfs: bytes) -> int:
        if romfs[:4] != b"IVFC":
            raise ValueError("VC donor RomFS is not an IVFC image.")
        if vc._looks_like_level3(romfs, 0x1000):
            return 0x1000
        limit = min(len(romfs), 0x400000)
        for offset in range(0x20, limit, 0x10):
            if vc._looks_like_level3(romfs, offset):
                return offset
        raise ValueError("Unable to locate the RomFS Level 3 filesystem header.")

    def build_romfs(files: dict[str, bytes], *, block_size_log2: int = 12) -> bytes:
        level3 = _build_level3_retail(vc, files)
        block_size = 1 << block_size_log2
        if block_size != 0x1000:
            raise ValueError("Classic VC RomFS must use 0x1000-byte IVFC blocks.")

        level2 = _hash_blocks_padded(level3, block_size)
        level1 = _hash_blocks_padded(level2, block_size)
        master = _hash_blocks_padded(level1, block_size)

        level3_padded = level3.ljust(_align(len(level3), block_size), b"\x00")
        level1_padded = level1.ljust(_align(len(level1), block_size), b"\x00")
        level2_padded = level2.ljust(_align(len(level2), block_size), b"\x00")

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
            + (0x5C).to_bytes(4, "little")
            + (0).to_bytes(4, "little")
        )
        if len(header) != 0x5C:
            raise AssertionError(f"Unexpected IVFC header size: {len(header):#x}")
        first_block = (header.ljust(0x60, b"\x00") + master).ljust(block_size, b"\x00")
        romfs = first_block + level3_padded + level1_padded + level2_padded
        validate_retail_romfs(romfs)
        return romfs

    def extract_runtime(donor_cia: Path, boot9: Path, family: str):
        base = original_extract_runtime(donor_cia, boot9, family)
        donor = vc.read_asset(donor_cia)
        keys = vc.read_asset(boot9)
        ncch = vc._primary_ncch_from_cia(donor)
        donor_banner = vc._extract_ncch_exefs_entry(ncch, keys, "banner")
        # base.romfs_template is rebuilt through the live vc.build_romfs global
        # after install(), then checked again when it is loaded for an inject.
        validate_retail_romfs(base.romfs_template)
        return HardwareClassicVcRuntime(
            family=base.family,
            exheader=base.exheader,
            code=base.code,
            logo=base.logo,
            romfs_template=base.romfs_template,
            rom_path=base.rom_path,
            donor_banner=donor_banner,
        )

    def build_cia(
        rom: bytes,
        artwork: "ImageSource",
        runtime: HardwareClassicVcRuntime,
        *,
        romm_id: int,
        title_name: str,
        long_title: str | None = None,
        publisher: str = "",
        title_version: int = 0,
    ) -> bytes:
        family = runtime.family.lower()
        if family not in vc._CLASSIC_FAMILIES:
            raise ValueError(f"Unsupported classic VC family: {family}")

        metadata = normalize_vc_metadata(title_name, long_title=long_title, publisher=publisher)
        rom = vc.prepare_classic_rom(rom, family)
        title_id = vc.classic_title_id_for_romm_id(romm_id, family)
        product_code = vc._product_code(family, romm_id)
        exheader = vc._patch_exheader(runtime.exheader, title_id, product_code)

        validate_retail_romfs(runtime.romfs_template)
        files = vc.parse_romfs_files(runtime.romfs_template)
        if runtime.rom_path not in files:
            raise ValueError("Cached classic VC runtime is missing its ROM placeholder.")
        files[runtime.rom_path] = rom
        romfs = build_romfs(files)

        (
            banner_assembly,
            _,
            _,
            cia_format,
            exefs_format,
            ncch_format,
            ticket_format,
            tmd_format,
        ) = vc._require_classic_vc_tools()

        icon_source = vc.prepare_vc_icon_artwork(artwork) if isinstance(artwork, bytes) else artwork
        icon = banner_assembly.build_icon(
            icon_source,
            metadata.short_title,
            metadata.long_title,
            metadata.publisher,
            save_data=vc._read_sci_save_data_size(exheader) > 0,
        )

        if not runtime.donor_banner:
            raise ValueError("Cached classic VC runtime is missing its animated donor banner.")
        try:
            from agbcia.banner.donor import patch_donor_banner
        except ImportError as exc:
            raise RuntimeError("Animated GB/GBC VC banners require agbcia banner donor support.") from exc
        banner = patch_donor_banner(
            runtime.donor_banner,
            artwork,
            bottom_badge_image=prepare_vc_title_badge(metadata.banner_title),
        )

        entries = [
            exefs_format.ExeFSFile(name=".code", data=runtime.code),
            exefs_format.ExeFSFile(name="banner", data=banner),
            exefs_format.ExeFSFile(name="icon", data=icon),
        ]
        if runtime.logo:
            entries.append(exefs_format.ExeFSFile(name="logo", data=runtime.logo))
        exefs = exefs_format.build(entries)

        ncch = ncch_format.Ncch(
            title_id=title_id,
            product_code=product_code,
            exheader=exheader,
            exefs=exefs,
            romfs=romfs,
        )
        ncch_bytes = ncch_format.build(ncch)
        ticket = ticket_format.build(ticket_format.Ticket(title_id=title_id))
        content = tmd_format.content_chunk_from_data(content_id=0, content_index=0, data=ncch_bytes)
        tmd = tmd_format.build(
            tmd_format.Tmd(
                title_id=title_id,
                contents=(content,),
                save_data_size=vc._read_sci_save_data_size(exheader),
                title_version=title_version,
            )
        )
        validate_classic_package_identity(
            ncch=ncch_bytes,
            exheader=exheader,
            donor_exheader=runtime.exheader,
            title_id=title_id,
            ticket=ticket,
            tmd=tmd,
        )
        meta = cia_format.MetaRegion(icon=icon)
        return cia_format.build(ticket=ticket, tmd=tmd, content=ncch_bytes, meta=meta)

    vc.ClassicVcRuntime = HardwareClassicVcRuntime
    vc._ROOT_PARENT = 0
    vc._build_level3 = lambda files: _build_level3_retail(vc, files)
    vc._find_level3_offset = find_level3_offset
    vc._hash_blocks = _hash_blocks_padded
    vc.build_romfs = build_romfs
    vc.extract_classic_vc_runtime = extract_runtime
    vc.build_classic_vc_cia = build_cia
    _INSTALLED = True
