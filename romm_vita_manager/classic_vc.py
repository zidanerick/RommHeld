from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .gba_vc import (
    _extract_ncch_exefs_entry,
    _primary_ncch_from_cia,
    prepare_vc_icon_artwork,
    read_asset,
)

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource

_CLASSIC_FAMILIES = {"gb", "gbc"}
_CLASSIC_ROM_EXTENSIONS = {
    "gb": (".gb",),
    "gbc": (".gbc", ".gb"),
}
_MAX_CLASSIC_ROM_SIZE = 0x800000
_NO_ENTRY = 0xFFFFFFFF
_ROOT_PARENT = 0xFFFFFFFF
_SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17)


@dataclass(frozen=True)
class ClassicVcRuntime:
    family: str
    exheader: bytes
    code: bytes
    logo: bytes
    romfs_template: bytes
    rom_path: str


def _require_classic_vc_tools():
    try:
        from agbcia.banner import assembly as banner_assembly
        from agbcia.crypto import aes_ctr, ncch_keys
        from agbcia.formats import cia as cia_format
        from agbcia.formats import exefs as exefs_format
        from agbcia.formats import ncch as ncch_format
        from agbcia.formats import ticket as ticket_format
        from agbcia.formats import tmd as tmd_format
    except ImportError as exc:
        raise RuntimeError(
            "GB/GBC Virtual Console packaging requires the 'agbcia' package and its crypto dependencies. "
            "Install project requirements first."
        ) from exc
    return (
        banner_assembly,
        aes_ctr,
        ncch_keys,
        cia_format,
        exefs_format,
        ncch_format,
        ticket_format,
        tmd_format,
    )


def classic_title_id_for_romm_id(romm_id: int, family: str) -> bytes:
    family = family.lower()
    if family not in _CLASSIC_FAMILIES:
        raise ValueError(f"Unsupported classic VC family: {family}")
    if romm_id < 0:
        raise ValueError("RomM ROM ID must be non-negative.")
    digest = hashlib.sha256(f"{family}:{romm_id}".encode("ascii")).digest()
    # Use a deterministic high application-ID range to reduce the chance of
    # colliding with Nintendo's retail IDs while staying in the standard
    # 00040000 application category.
    unique = 0xE0000000 | (int.from_bytes(digest[:4], "big") & 0x0FFFFFFF)
    return bytes.fromhex(f"00040000{unique:08X}")


def _product_code(family: str, romm_id: int) -> str:
    suffix = hashlib.sha256(f"{family}:{romm_id}".encode("ascii")).hexdigest()[:4].upper()
    prefix = "RHGB" if family == "gb" else "RHGC"
    return f"CTR-N-{prefix[:2]}{suffix[:2]}"


def _application_tag(product_code: str) -> bytes:
    tag = product_code
    for prefix in ("CTR-N-", "CTR-P-", "CTR-H-", "CTR-T-"):
        if tag.startswith(prefix):
            tag = tag[len(prefix) :]
            break
    return tag.encode("ascii", errors="ignore")[:8].ljust(8, b"\x00")


def _patch_exheader(exheader: bytes, title_id: bytes, product_code: str) -> bytes:
    if len(exheader) != 0x800:
        raise ValueError(f"VC donor exheader must be 0x800 bytes, got {len(exheader):#x}.")
    patched = bytearray(exheader)
    reversed_title_id = title_id[::-1]
    patched[0x000:0x008] = _application_tag(product_code)
    patched[0x1C8:0x1D0] = reversed_title_id
    patched[0x200:0x208] = reversed_title_id
    # Do not alter the signed Access Descriptor copy at 0x400 onward.
    return bytes(patched)


def _read_sci_save_data_size(exheader: bytes) -> int:
    return int.from_bytes(exheader[0x1C0:0x1C8], "little")


def _decrypt_region(content: bytes, info, region, boot9: bytes, section: int, *, extra: bool) -> bytes:
    raw = content[region.offset : region.offset + region.size]
    if info.no_crypto:
        return raw
    _, aes_ctr, ncch_keys, _, _, _, _, _ = _require_classic_vc_tools()
    key = (
        ncch_keys.extra_key(boot9, info.key_y, info.crypto_method)
        if extra
        else ncch_keys.main_key(boot9, info.key_y)
    )
    return aes_ctr.decrypt_region(key, info.title_id, section, raw)


def _bucket_count(entries: int) -> int:
    if entries < 3:
        return 3
    if entries < 19:
        return entries | 1
    value = entries
    while any(value % prime == 0 for prime in _SMALL_PRIMES):
        value += 1
    return value


def _path_hash(name_utf16: bytes, parent_offset: int) -> int:
    value = (parent_offset ^ 123456789) & 0xFFFFFFFF
    for index in range(0, len(name_utf16), 2):
        value = ((value >> 5) | (value << 27)) & 0xFFFFFFFF
        value ^= name_utf16[index] | (name_utf16[index + 1] << 8)
    return value


def _align(value: int, boundary: int) -> int:
    remainder = value % boundary
    return value if remainder == 0 else value + boundary - remainder


def _find_level3_offset(romfs: bytes) -> int:
    # Nintendo-authored RomFS images and our own builder can place Level 3 at
    # different aligned physical offsets. Detect the filesystem header instead
    # of assuming one layout.
    for offset in range(0x1000, min(len(romfs), 0x400000), 0x1000):
        if int.from_bytes(romfs[offset : offset + 4], "little") != 0x28:
            continue
        values = [
            int.from_bytes(romfs[offset + pos : offset + pos + 4], "little")
            for pos in range(4, 40, 4)
        ]
        if len(values) != 9:
            continue
        dir_hash, _, dir_meta, _, file_hash, _, file_meta, _, file_data = values
        if (
            0x28 <= dir_hash <= dir_meta <= file_hash <= file_meta <= file_data
            and offset + file_data <= len(romfs)
        ):
            return offset
    raise ValueError("Unable to locate the RomFS Level 3 filesystem header.")


def parse_romfs_files(romfs: bytes) -> dict[str, bytes]:
    if romfs[:4] != b"IVFC":
        raise ValueError("VC donor RomFS is not an IVFC image.")
    level3_offset = _find_level3_offset(romfs)
    level3 = romfs[level3_offset:]
    fields = [int.from_bytes(level3[pos : pos + 4], "little") for pos in range(0, 40, 4)]
    _, _, _, dir_meta_offset, _, _, _, file_meta_offset, _, file_data_offset = fields

    files: dict[str, bytes] = {}
    visited_dirs: set[int] = set()

    def walk_directory(directory_offset: int, parent_path: str) -> None:
        if directory_offset == _NO_ENTRY or directory_offset in visited_dirs:
            return
        visited_dirs.add(directory_offset)
        base = dir_meta_offset + directory_offset
        child_dir = int.from_bytes(level3[base + 8 : base + 12], "little")
        first_file = int.from_bytes(level3[base + 12 : base + 16], "little")
        name_length = int.from_bytes(level3[base + 20 : base + 24], "little")
        name = (
            level3[base + 24 : base + 24 + name_length].decode("utf-16-le")
            if name_length
            else ""
        )
        current = parent_path
        if name:
            current = f"{parent_path.rstrip('/')}/{name}" if parent_path != "/" else f"/{name}"

        file_offset = first_file
        seen_files: set[int] = set()
        while file_offset != _NO_ENTRY and file_offset not in seen_files:
            seen_files.add(file_offset)
            file_base = file_meta_offset + file_offset
            sibling = int.from_bytes(level3[file_base + 4 : file_base + 8], "little")
            data_offset = int.from_bytes(level3[file_base + 8 : file_base + 16], "little")
            data_size = int.from_bytes(level3[file_base + 16 : file_base + 24], "little")
            file_name_length = int.from_bytes(level3[file_base + 28 : file_base + 32], "little")
            file_name = level3[
                file_base + 32 : file_base + 32 + file_name_length
            ].decode("utf-16-le")
            path = f"{current.rstrip('/')}/{file_name}" if current != "/" else f"/{file_name}"
            start = file_data_offset + data_offset
            files[path] = bytes(level3[start : start + data_size])
            file_offset = sibling

        directory = child_dir
        seen_siblings: set[int] = set()
        while directory != _NO_ENTRY and directory not in seen_siblings:
            seen_siblings.add(directory)
            child_base = dir_meta_offset + directory
            sibling = int.from_bytes(level3[child_base + 4 : child_base + 8], "little")
            walk_directory(directory, current)
            directory = sibling

    walk_directory(0, "/")
    return files


def _build_level3(files: dict[str, bytes]) -> bytes:
    normalized: dict[str, bytes] = {}
    for raw_path, data in files.items():
        path = "/" + raw_path.strip("/")
        if path == "/":
            raise ValueError("RomFS file path cannot be the root directory.")
        normalized[path] = bytes(data)

    dir_paths = {"/"}
    for path in normalized:
        parts = path.strip("/").split("/")[:-1]
        current = ""
        for part in parts:
            current += "/" + part
            dir_paths.add(current)

    ordered_dirs = ["/"] + sorted((p for p in dir_paths if p != "/"), key=lambda p: (p.count("/"), p.casefold()))
    dir_name_bytes = {
        path: (b"" if path == "/" else path.rsplit("/", 1)[-1].encode("utf-16-le"))
        for path in ordered_dirs
    }
    dir_entry_sizes = {path: 0x18 + _align(len(dir_name_bytes[path]), 4) for path in ordered_dirs}
    dir_offsets: dict[str, int] = {}
    running = 0
    for path in ordered_dirs:
        dir_offsets[path] = running
        running += dir_entry_sizes[path]

    ordered_files = sorted(normalized, key=lambda p: (p.rsplit("/", 1)[0].casefold(), p.casefold()))
    file_name_bytes = {path: path.rsplit("/", 1)[-1].encode("utf-16-le") for path in ordered_files}
    file_entry_sizes = {path: 0x20 + _align(len(file_name_bytes[path]), 4) for path in ordered_files}
    file_offsets: dict[str, int] = {}
    running = 0
    for path in ordered_files:
        file_offsets[path] = running
        running += file_entry_sizes[path]

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
    for values in child_dirs.values():
        values.sort(key=str.casefold)
    for values in child_files.values():
        values.sort(key=str.casefold)

    directory_bucket_count = _bucket_count(max(0, len(ordered_dirs) - 1))
    directory_buckets = [_NO_ENTRY] * directory_bucket_count
    directory_hash_next = {path: _NO_ENTRY for path in ordered_dirs}
    for path in ordered_dirs:
        if path == "/":
            continue
        parent = path.rsplit("/", 1)[0] or "/"
        bucket = _path_hash(dir_name_bytes[path], dir_offsets[parent]) % directory_bucket_count
        directory_hash_next[path] = directory_buckets[bucket]
        directory_buckets[bucket] = dir_offsets[path]

    file_bucket_count = _bucket_count(len(ordered_files))
    file_buckets = [_NO_ENTRY] * file_bucket_count
    file_hash_next = {path: _NO_ENTRY for path in ordered_files}
    for path in ordered_files:
        parent = path.rsplit("/", 1)[0] or "/"
        bucket = _path_hash(file_name_bytes[path], dir_offsets[parent]) % file_bucket_count
        file_hash_next[path] = file_buckets[bucket]
        file_buckets[bucket] = file_offsets[path]

    directory_metadata = bytearray()
    for path in ordered_dirs:
        parent = _ROOT_PARENT if path == "/" else dir_offsets[path.rsplit("/", 1)[0] or "/"]
        siblings = [] if path == "/" else child_dirs[path.rsplit("/", 1)[0] or "/"]
        sibling = _NO_ENTRY
        if path != "/":
            index = siblings.index(path)
            if index + 1 < len(siblings):
                sibling = dir_offsets[siblings[index + 1]]
        children = child_dirs[path]
        files_here = child_files[path]
        first_child = dir_offsets[children[0]] if children else _NO_ENTRY
        first_file = file_offsets[files_here[0]] if files_here else _NO_ENTRY
        encoded = dir_name_bytes[path]
        directory_metadata += (
            parent.to_bytes(4, "little")
            + sibling.to_bytes(4, "little")
            + first_child.to_bytes(4, "little")
            + first_file.to_bytes(4, "little")
            + directory_hash_next[path].to_bytes(4, "little")
            + len(encoded).to_bytes(4, "little")
            + encoded.ljust(_align(len(encoded), 4), b"\x00")
        )

    data_offsets: dict[str, int] = {}
    file_data = bytearray()
    for path in ordered_files:
        aligned = _align(len(file_data), 0x10)
        if aligned > len(file_data):
            file_data += bytes(aligned - len(file_data))
        data_offsets[path] = len(file_data)
        file_data += normalized[path]

    file_metadata = bytearray()
    for path in ordered_files:
        parent_path = path.rsplit("/", 1)[0] or "/"
        siblings = child_files[parent_path]
        index = siblings.index(path)
        sibling = file_offsets[siblings[index + 1]] if index + 1 < len(siblings) else _NO_ENTRY
        encoded = file_name_bytes[path]
        file_metadata += (
            dir_offsets[parent_path].to_bytes(4, "little")
            + sibling.to_bytes(4, "little")
            + data_offsets[path].to_bytes(8, "little")
            + len(normalized[path]).to_bytes(8, "little")
            + file_hash_next[path].to_bytes(4, "little")
            + len(encoded).to_bytes(4, "little")
            + encoded.ljust(_align(len(encoded), 4), b"\x00")
        )

    directory_hash_table = b"".join(value.to_bytes(4, "little") for value in directory_buckets)
    file_hash_table = b"".join(value.to_bytes(4, "little") for value in file_buckets)
    header_size = 0x28
    dir_hash_offset = header_size
    dir_meta_offset = dir_hash_offset + len(directory_hash_table)
    file_hash_offset = dir_meta_offset + len(directory_metadata)
    file_meta_offset = file_hash_offset + len(file_hash_table)
    file_data_offset = _align(file_meta_offset + len(file_metadata), 0x10)
    padding = bytes(file_data_offset - (file_meta_offset + len(file_metadata)))

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
        + padding
        + bytes(file_data)
    )


def _hash_blocks(data: bytes, block_size: int) -> bytes:
    return b"".join(
        hashlib.sha256(data[offset : offset + block_size]).digest()
        for offset in range(0, len(data), block_size)
    )


def build_romfs(files: dict[str, bytes], *, block_size_log2: int = 12) -> bytes:
    level3 = _build_level3(files)
    block_size = 1 << block_size_log2
    level2 = _hash_blocks(level3, block_size)
    level1 = _hash_blocks(level2, block_size)
    master = _hash_blocks(level1, block_size)

    def padded(data: bytes) -> bytes:
        return data.ljust(_align(len(data), block_size), b"\x00")

    master_padded = padded(master)
    level1_padded = padded(level1)
    level2_padded = padded(level2)
    header_region_size = 0x60
    master_offset = header_region_size
    level1_offset = master_offset + len(master_padded)
    level2_offset = level1_offset + len(level1_padded)
    level3_offset = level2_offset + len(level2_padded)

    header = (
        b"IVFC"
        + (0x10000).to_bytes(4, "little")
        + len(master).to_bytes(4, "little")
        + level1_offset.to_bytes(8, "little")
        + len(level1).to_bytes(8, "little")
        + block_size_log2.to_bytes(4, "little")
        + bytes(4)
        + level2_offset.to_bytes(8, "little")
        + len(level2).to_bytes(8, "little")
        + block_size_log2.to_bytes(4, "little")
        + bytes(4)
        + level3_offset.to_bytes(8, "little")
        + len(level3).to_bytes(8, "little")
        + block_size_log2.to_bytes(4, "little")
        + bytes(4)
        + bytes(4)
        + (0).to_bytes(4, "little")
    ).ljust(header_region_size, b"\x00")
    return header + master_padded + level1_padded + level2_padded + level3


def extract_classic_vc_runtime(donor_cia: Path, boot9: Path, family: str) -> ClassicVcRuntime:
    family = family.lower()
    if family not in _CLASSIC_FAMILIES:
        raise ValueError(f"Unsupported classic VC family: {family}")
    donor = read_asset(donor_cia)
    keys = read_asset(boot9)
    ncch = _primary_ncch_from_cia(donor)
    _, _, _, _, _, ncch_format, _, _ = _require_classic_vc_tools()
    info = ncch_format.parse(ncch)
    if info.exheader is None or info.romfs is None:
        raise ValueError("Classic VC donor is missing its exheader or RomFS runtime.")

    exheader = _decrypt_region(
        ncch,
        info,
        info.exheader,
        keys,
        ncch_format.SECTION_EXTENDED_HEADER,
        extra=False,
    )
    romfs = _decrypt_region(
        ncch,
        info,
        info.romfs,
        keys,
        ncch_format.SECTION_ROMFS,
        extra=True,
    )
    files = parse_romfs_files(romfs)
    rom_candidates = sorted(path for path in files if path.casefold().startswith("/rom/"))
    if len(rom_candidates) != 1:
        raise ValueError(
            f"Expected one ROM payload in the {family.upper()} donor, found {len(rom_candidates)}."
        )
    rom_path = rom_candidates[0]
    files[rom_path] = b""
    for path in list(files):
        if path.count("/") == 1 and path.casefold().endswith(".patch"):
            del files[path]

    code = _extract_ncch_exefs_entry(ncch, keys, ".code")
    try:
        logo = _extract_ncch_exefs_entry(ncch, keys, "logo")
    except ValueError:
        logo = b""
    return ClassicVcRuntime(
        family=family,
        exheader=exheader,
        code=code,
        logo=logo,
        romfs_template=build_romfs(files),
        rom_path=rom_path,
    )


def prepare_classic_rom(data: bytes, family: str) -> bytes:
    family = family.lower()
    if family not in _CLASSIC_FAMILIES:
        raise ValueError(f"Unsupported classic VC family: {family}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (OSError, zipfile.BadZipFile):
        if len(data) > _MAX_CLASSIC_ROM_SIZE:
            raise ValueError("GB/GBC ROM is larger than the supported 8 MiB limit.")
        return data

    with archive:
        suffixes = _CLASSIC_ROM_EXTENSIONS[family]
        candidates = [
            item
            for item in archive.infolist()
            if not item.is_dir() and item.filename.casefold().endswith(suffixes)
        ]
        if not candidates:
            raise ValueError(f"ZIP archive does not contain a {family.upper()} ROM.")
        candidates.sort(key=lambda item: (item.filename.count("/"), item.filename.casefold()))
        selected = candidates[0]
        if selected.file_size > _MAX_CLASSIC_ROM_SIZE:
            raise ValueError("GB/GBC ROM inside the ZIP is larger than the supported 8 MiB limit.")
        return archive.read(selected)


def build_classic_vc_cia(
    rom: bytes,
    artwork: "ImageSource",
    runtime: ClassicVcRuntime,
    *,
    romm_id: int,
    title_name: str,
    long_title: str | None = None,
    publisher: str = "",
    title_version: int = 0,
) -> bytes:
    family = runtime.family.lower()
    if family not in _CLASSIC_FAMILIES:
        raise ValueError(f"Unsupported classic VC family: {family}")
    rom = prepare_classic_rom(rom, family)
    title_id = classic_title_id_for_romm_id(romm_id, family)
    product_code = _product_code(family, romm_id)
    exheader = _patch_exheader(runtime.exheader, title_id, product_code)

    files = parse_romfs_files(runtime.romfs_template)
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
    ) = _require_classic_vc_tools()

    icon_source = prepare_vc_icon_artwork(artwork) if isinstance(artwork, bytes) else artwork
    icon = banner_assembly.build_icon(
        icon_source,
        title_name[:128],
        (long_title or title_name)[:128],
        publisher[:128],
        save_data=_read_sci_save_data_size(exheader) > 0,
    )
    banner = banner_assembly.build_banner(artwork)
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
            save_data_size=_read_sci_save_data_size(exheader),
            title_version=title_version,
        )
    )
    meta = cia_format.MetaRegion(icon=icon)
    return cia_format.build(ticket=ticket, tmd=tmd, content=ncch_bytes, meta=meta)
