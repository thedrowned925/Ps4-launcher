"""Immutable catalog validation and dependency ordering; no implicit installs."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

KINDS = frozenset({"base", "update", "dlc", "backport"})
SHA256 = re.compile(r"^[a-f0-9]{64}$")
FW = re.compile(r"^[0-9]{1,2}\.[0-9]{2}$")


class CatalogError(ValueError):
    pass


def immutable_remote_path(game_id: str, kind: str, digest: str) -> str:
    """Return a stable distinct path independent of human-edited filenames."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", game_id):
        raise CatalogError("Unsafe game ID")
    if kind not in KINDS or not SHA256.fullmatch(digest):
        raise CatalogError("Invalid package kind or sha256")
    return f"packages/{game_id}/{kind}/{digest}.pkg"


def _valid_source(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    if not all(isinstance(source.get(k), str) and source[k] for k in
               ("repo_id", "revision", "path")):
        return False
    path = source["path"]
    if path.startswith("/") or "\\" in path or ".." in PurePosixPath(path).parts:
        return False
    # Never point in-flight downloads at mutable branch aliases.
    if not re.fullmatch(r"[a-f0-9]{40}", source["revision"]):
        return False
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", source["repo_id"]):
        return False
    return True


def order_packages(packages: list[dict[str, Any]], selected: list[str],
                   installed: set[str] | None = None) -> list[str]:
    """Topologically sort selected packages + dependencies (installed are skipped).

    Uses immutable package_id references scoped to a single game.
    """
    mapping = {p["package_id"]: p for p in packages}
    if len(mapping) != len(packages):
        raise CatalogError("Duplicate package ID")
    installed = installed or set()
    visiting: set[str] = set()
    visited: set[str] = set()
    output: list[str] = []

    def visit(pid: str) -> None:
        if pid in visiting:
            raise CatalogError("Cyclic package dependencies")
        if pid in visited:
            return
        if pid not in mapping:
            raise CatalogError(f"Unknown dependency: {pid}")
        visiting.add(pid)
        for dependency in mapping[pid].get("required_package_ids", []):
            visit(dependency)
        visiting.remove(pid)
        visited.add(pid)
        if pid not in installed:
            output.append(pid)

    for package_id in selected:
        visit(package_id)
    return output


def validate_catalog(catalog: dict[str, Any]) -> None:
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
        raise CatalogError("Unsupported catalog schema")
    if not isinstance(catalog.get("published"), bool):
        raise CatalogError("Missing published flag")
    games = catalog.get("games")
    if not isinstance(games, list):
        raise CatalogError("games must be a list")

    used_games: set[str] = set()
    used_packages: set[str] = set()
    for game in games:
        if not isinstance(game, dict):
            raise CatalogError("Invalid game")
        gid, title = game.get("game_id"), game.get("title")
        if not isinstance(gid, str) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", gid):
            raise CatalogError("Invalid game ID")
        if gid in used_games or not isinstance(title, str) or not title.strip():
            raise CatalogError("Duplicate game ID or missing title")
        used_games.add(gid)
        packages = game.get("packages")
        if not isinstance(packages, list):
            raise CatalogError("packages must be a list")
        for pkg in packages:
            if not isinstance(pkg, dict):
                raise CatalogError("Invalid package")
            digest = pkg.get("sha256")
            pid = pkg.get("package_id")
            if (not isinstance(digest, str) or not SHA256.fullmatch(digest)
                    or pid != f"sha256:{digest}" or pid in used_packages):
                raise CatalogError("Invalid/duplicate immutable package ID")
            used_packages.add(pid)
            if pkg.get("kind") not in KINDS:
                raise CatalogError("Invalid package kind")
            if not isinstance(pkg.get("size_bytes"), int) or (
                    isinstance(pkg["size_bytes"], bool) or pkg["size_bytes"] < 4):
                raise CatalogError("Invalid package size")
            if not isinstance(pkg.get("filename"), str) or not pkg["filename"].lower().endswith(".pkg"):
                raise CatalogError("Invalid PKG filename")
            if not isinstance(pkg.get("version"), str) or not pkg["version"].strip():
                raise CatalogError("Missing version")
            firmware = pkg.get("target_firmware")
            if firmware is not None and (
                    not isinstance(firmware, str) or not FW.fullmatch(firmware)):
                raise CatalogError("Invalid firmware version")
            depends = pkg.get("required_package_ids")
            if not isinstance(depends, list) or not all(isinstance(d, str) for d in depends):
                raise CatalogError("Invalid dependencies")
            if len(depends) != len(set(depends)):
                raise CatalogError("Duplicate dependencies")
            if catalog["published"] and not _valid_source(pkg.get("source")):
                raise CatalogError("Published package requires pinned remote source")
        order_packages(packages, [p["package_id"] for p in packages])
