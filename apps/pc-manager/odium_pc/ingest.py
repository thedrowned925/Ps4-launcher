"""Read-only package probing. Header detection is not complete PKG validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .pkg_metadata import read_package_hints

PS4_PKG_MAGIC = b"\x7fCNT"
BUFFER_SIZE = 4 * 1024 * 1024


@dataclass(frozen=True)
class Probe:
    path: str
    filename: str
    size_bytes: int
    mtime_ns: int
    sha256: str
    guessed_kind: str
    needs_manual_review: bool = True
    content_id: str | None = None
    title_id: str | None = None
    title: str | None = None
    app_version: str | None = None
    metadata_note: str = ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(part)
    return digest.hexdigest()


def guess_kind(filename: str) -> str:
    name = filename.casefold()
    if "backport" in name or "bp_" in name:
        return "backport"
    if "dlc" in name or "addon" in name or "add-on" in name:
        return "dlc"
    if "update" in name or "patch" in name:
        return "update"
    return "base"


def inspect_pkg(path: str | Path) -> Probe:
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.casefold() != ".pkg":
        raise ValueError("Expected a regular .pkg file")
    before = source.stat()
    with source.open("rb") as stream:
        if stream.read(4) != PS4_PKG_MAGIC:
            raise ValueError("Unrecognized PS4 PKG header (0x7F434E54 expected)")
    # Hints are untrusted (possibly absent/encrypted); no automatic approval.
    hints = read_package_hints(source)
    digest = sha256_file(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source changed while hashing; retry after stabilizing")
    return Probe(str(source), source.name, after.st_size, after.st_mtime_ns,
                 digest, guess_kind(source.name),
                 content_id=hints.content_id, title_id=hints.title_id,
                 title=hints.title, app_version=hints.app_version,
                 metadata_note=hints.note)
