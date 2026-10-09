"""SQLite journal for PC scans and explicit human approvals.

Never automatically uploads or touches source PKG bytes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .catalog import CatalogError, KINDS, validate_catalog
from .ingest import Probe, sha256_file


class PackageStore:
    def __init__(self, db_path: str | Path) -> None:
        self.path = str(Path(db_path).expanduser())
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS packages(
                path TEXT PRIMARY KEY, filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
                sha256 TEXT NOT NULL, guessed_kind TEXT NOT NULL,
                game_id TEXT, game_title TEXT, kind TEXT, version TEXT,
                target_firmware TEXT, required_package_ids TEXT NOT NULL DEFAULT '[]',
                rights_confirmed INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'review'
            )
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "PackageStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def put_probe(self, probe: Probe) -> None:
        with self.db:
            self.db.execute("""
                INSERT INTO packages
                    (path,filename,size_bytes,mtime_ns,sha256,guessed_kind)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    filename=excluded.filename,
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    sha256=excluded.sha256,
                    guessed_kind=excluded.guessed_kind,
                    approved=CASE WHEN packages.sha256=excluded.sha256
                        THEN packages.approved ELSE 0 END,
                    rights_confirmed=CASE WHEN packages.sha256=excluded.sha256
                        THEN packages.rights_confirmed ELSE 0 END,
                    state=CASE WHEN packages.sha256=excluded.sha256
                        THEN packages.state ELSE 'review' END
            """, (probe.path, probe.filename, probe.size_bytes,
                  probe.mtime_ns, probe.sha256, probe.guessed_kind))

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM packages ORDER BY path")]

    def approve(self, path: str, *, game_id: str, game_title: str,
                kind: str, version: str, target_firmware: str | None,
                required_package_ids: list[str], rights_confirmed: bool) -> None:
        if not rights_confirmed:
            raise CatalogError("Explicit rights confirmation is required")
        if kind not in KINDS:
            raise CatalogError("Unknown package type")
        row = self.db.execute("SELECT * FROM packages WHERE path=?", (str(Path(path).resolve()),)).fetchone()
        if row is None:
            raise CatalogError("Scan package before approving")
        package = {
            "package_id": f"sha256:{row['sha256']}", "sha256": row["sha256"],
            "filename": row["filename"], "size_bytes": row["size_bytes"],
            "kind": kind, "version": version,
            "target_firmware": target_firmware,
            "required_package_ids": required_package_ids
        }
        validate_catalog({"schema_version": 1, "published": False, "games": [
            {"game_id": game_id, "title": game_title, "packages": [dict(
                package, required_package_ids=[])]}
        ]})
        if package["package_id"] in required_package_ids:
            raise CatalogError("Package cannot depend on itself")
        # Human-approved package is still subject to the full dependency graph at export.
        with self.db:
            self.db.execute("""
                UPDATE packages SET game_id=?,game_title=?,kind=?,version=?,
                    target_firmware=?,required_package_ids=?,rights_confirmed=1,
                    approved=1,state='approved' WHERE path=?
            """, (game_id, game_title, kind, version, target_firmware,
                  json.dumps(required_package_ids), str(Path(path).resolve())))

    def recover_approved(self) -> list[tuple[str, str]]:
        """Re-hash approved sources before any future uploader resumes them."""
        results: list[tuple[str, str]] = []
        for row in self.rows():
            if not row["approved"]:
                continue
            path = Path(row["path"])
            if not path.is_file():
                status = "missing"
            else:
                try:
                    stat = path.stat()
                    status = ("approved" if stat.st_size == row["size_bytes"]
                              and sha256_file(path) == row["sha256"]
                              else "changed")
                except OSError:
                    status = "unavailable"
            with self.db:
                self.db.execute("UPDATE packages SET state=? WHERE path=?",
                                (status, row["path"]))
                if status != "approved":
                    self.db.execute(
                        "UPDATE packages SET approved=0,rights_confirmed=0 WHERE path=?",
                        (row["path"],))
            results.append((row["path"], status))
        return results

    def export_draft(self) -> dict[str, Any]:
        games: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            if not row["approved"] or not row["rights_confirmed"]:
                continue
            gid = row["game_id"]
            if gid in games and games[gid]["title"] != row["game_title"]:
                raise CatalogError("Conflicting titles for same game ID")
            game = games.setdefault(gid, {"game_id": gid, "title": row["game_title"],
                                          "packages": []})
            game["packages"].append({
                "package_id": f"sha256:{row['sha256']}",
                "sha256": row["sha256"],
                "filename": row["filename"],
                "size_bytes": row["size_bytes"],
                "kind": row["kind"],
                "version": row["version"],
                "target_firmware": row["target_firmware"],
                "required_package_ids": json.loads(row["required_package_ids"])
            })
        catalog = {"schema_version": 1, "published": False,
                   "games": list(games.values())}
        validate_catalog(catalog)
        return catalog
