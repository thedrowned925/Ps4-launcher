"""Bounded, read-only PKG header and optional unencrypted PARAM.SFO metadata parser.

Untrusted package metadata is a *suggestion*, not compatibility, signature, or
redistribution validation. No decryption, file extraction, or source mutation.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

MAX_ENTRIES = 8192
MAX_SFO = 1024 * 1024
MAX_ITEMS = 1024
CONTENT_ID = re.compile(r"^[A-Z0-9]{2}[0-9]{4}-([A-Z]{4}[0-9]{5})_[0-9]{2}-[A-Z0-9]{16}$")


@dataclass(frozen=True)
class PackageHints:
    content_id: str | None = None
    title_id: str | None = None
    title: str | None = None
    app_version: str | None = None
    note: str = "PKG header only; metadata needs human review"


def _sfo_fields(raw: bytes) -> dict[str, str]:
    """Parse bounded plaintext PSF fields without trusting offsets/counts."""
    if len(raw) < 20 or raw[:4] != b"\x00PSF":
        return {}
    _, _, key_offset, data_offset, count = struct.unpack_from("<4sIIII", raw)
    if count > MAX_ITEMS or 20 + count * 16 > len(raw):
        return {}
    if key_offset >= len(raw) or data_offset >= len(raw):
        return {}
    values: dict[str, str] = {}
    for i in range(count):
        entry = 20 + i * 16
        key_rel, fmt, length, max_length, data_rel = struct.unpack_from("<HHIII", raw, entry)
        kstart = key_offset + key_rel
        vstart = data_offset + data_rel
        if (kstart >= len(raw) or vstart > len(raw) or
                length > max_length or length > len(raw) - vstart):
            continue
        key_end = raw.find(b"\x00", kstart, min(len(raw), kstart + 80))
        if key_end < 0:
            continue
        try:
            key = raw[kstart:key_end].decode("ascii")
        except UnicodeDecodeError:
            continue
        if key not in ("TITLE", "TITLE_ID", "CONTENT_ID", "APP_VER"):
            continue
        if fmt not in (0x0204, 0x0004):  # UTF-8 string formats.
            continue
        text = raw[vstart:vstart + length].split(b"\x00", 1)[0].decode(
            "utf-8", errors="replace").strip()
        if text:
            values[key] = text[:200]
    return values


def read_package_hints(source: str | Path | BinaryIO) -> PackageHints:
    """Inspect only a few KB of PKG header and at most 1 MiB of plaintext SFO."""
    owns = isinstance(source, (str, Path))
    stream = Path(source).open("rb") if owns else source
    try:
        stream.seek(0)
        header = stream.read(0x80)
        if len(header) < 4 or header[:4] != b"\x7fCNT":
            raise ValueError("Not a PS4 PKG")
        if len(header) < 0x64:
            return PackageHints(note="Truncated PKG header; no identity hint")
        candidate = header[0x40:0x64].rstrip(b"\x00")
        try:
            cid = candidate.decode("ascii")
        except UnicodeDecodeError:
            cid = ""
        parsed = CONTENT_ID.fullmatch(cid)
        content_id = cid if parsed else None
        title_id = parsed.group(1) if parsed else None
        sfo: dict[str, str] = {}
        count = int.from_bytes(header[0x10:0x14], "big")
        table = int.from_bytes(header[0x18:0x1c], "big")
        stream.seek(0, 2)
        size = stream.tell()
        if (0 < count <= MAX_ENTRIES and table >= 0x80
                and table <= size and count * 32 <= size - table):
            # Stream entries one-by-one; do not allocate attacker-supplied tables.
            stream.seek(table)
            for i in range(count):
                stream.seek(table + i * 32)
                entry = stream.read(32)
                if len(entry) != 32:
                    break
                fid, _, flags1, flags2, offset, length = struct.unpack_from(">IIIIII", entry)
                if fid != 0x1000:
                    continue
                if not (20 <= length <= MAX_SFO and offset <= size
                        and length <= size - offset):
                    break
                stream.seek(offset)
                raw_sfo = stream.read(length)
                sfo = _sfo_fields(raw_sfo)
                break
        sfo_cid = sfo.get("CONTENT_ID")
        sfo_title = sfo.get("TITLE_ID")
        notes = []
        if sfo_cid and content_id and sfo_cid != content_id:
            notes.append("Header/SFO Content ID mismatch; verify manually")
        if sfo_title and title_id and sfo_title != title_id:
            notes.append("Header/SFO Title ID mismatch; verify manually")
        if not sfo:
            notes.append("No readable plaintext PARAM.SFO; header hints only")
        else:
            notes.append("Plaintext PARAM.SFO read; fields are untrusted hints")
        return PackageHints(
            content_id=content_id or (sfo_cid if sfo_cid and CONTENT_ID.fullmatch(sfo_cid) else None),
            title_id=title_id or (sfo_title if sfo_title and re.fullmatch(r"[A-Z]{4}[0-9]{5}", sfo_title) else None),
            title=sfo.get("TITLE"), app_version=sfo.get("APP_VER"),
            note="; ".join(notes))
    finally:
        if owns:
            stream.close()
