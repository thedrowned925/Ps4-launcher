"""Regression: scanning alone must produce useful report without publication approval."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from odium_pc.ingest import inspect_pkg
from odium_pc.store import PackageStore
from test_pkg_metadata import make_pkg


class ReviewReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pkg = self.root / "example.pkg"
        self.pkg.write_bytes(make_pkg(with_sfo=True))

    def test_unapproved_scans_appear_without_catalog_rights(self):
        before = self.pkg.read_bytes()
        with PackageStore(self.root / "review.sqlite3") as store:
            store.put_probe(inspect_pkg(self.pkg))
            snapshot = store.export_review_snapshot()
            self.assertEqual(snapshot["review_snapshot_version"], 1)
            self.assertFalse(snapshot["published"])
            self.assertEqual(len(snapshot["packages"]), 1)
            scanned = snapshot["packages"][0]
            self.assertEqual(scanned["suggested_game_id"], "CUSA12345")
            self.assertEqual(scanned["content_id"],
                             "UP0000-CUSA12345_00-TESTGAME00000000")
            self.assertEqual(scanned["suggested_title"], "Independent Test Game")
            self.assertEqual(scanned["suggested_version"], "01.40")
            self.assertFalse(scanned["approved_for_staging"])
            self.assertEqual(store.export_draft()["games"], [])
        self.assertEqual(before, self.pkg.read_bytes())

    def test_preview_remains_unpublishable_after_local_approval(self):
        with PackageStore(self.root / "review.sqlite3") as store:
            store.put_probe(inspect_pkg(self.pkg))
            store.approve(str(self.pkg), game_id="CUSA12345",
                          game_title="Independent Test Game", kind="base",
                          version="01.40", target_firmware=None,
                          required_package_ids=[], rights_confirmed=True)
            report = store.export_review_snapshot()
            self.assertFalse(report["published"])
            self.assertTrue(report["packages"][0]["approved_for_staging"])
            self.assertTrue(store.export_draft()["games"])

    def test_migrate_old_database_preserving_review_records(self):
        db = self.root / "review.sqlite3"
        with sqlite3.connect(db) as con:
            con.execute("""CREATE TABLE packages(
                path TEXT PRIMARY KEY, filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
                sha256 TEXT NOT NULL, guessed_kind TEXT NOT NULL,
                game_id TEXT, game_title TEXT, kind TEXT, version TEXT,
                target_firmware TEXT, required_package_ids TEXT NOT NULL DEFAULT '[]',
                rights_confirmed INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'review'
            )""")
            con.execute("""INSERT INTO packages
                (path,filename,size_bytes,mtime_ns,sha256,guessed_kind)
                VALUES(?,?,?,?,?,?)""", (str(self.pkg), self.pkg.name, 10, 0,
                                          "a" * 64, "base"))
        with PackageStore(db) as store:
            report = store.export_review_snapshot()
            self.assertEqual(len(report["packages"]), 1)
            self.assertIsNone(report["packages"][0]["suggested_title"])
            store.put_probe(inspect_pkg(self.pkg))
            self.assertEqual(store.rows()[0]["title_id"], "CUSA12345")


if __name__ == "__main__":
    unittest.main()
