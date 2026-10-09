import tempfile
import unittest
from pathlib import Path
from odium_pc.catalog import CatalogError
from odium_pc.ingest import PS4_PKG_MAGIC, inspect_pkg
from odium_pc.store import PackageStore
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.pkg = self.dir / "demo.pkg"
        self.pkg.write_bytes(PS4_PKG_MAGIC + b"authorized-demo" * 100)
    def test_probe_is_read_only(self):
        content = self.pkg.read_bytes()
        probe = inspect_pkg(self.pkg)
        self.assertEqual(probe.size_bytes, len(content))
        self.assertEqual(probe.guessed_kind, "base")
        self.assertEqual(self.pkg.read_bytes(), content)
    def test_reject_unrecognized_pkg(self):
        self.pkg.write_bytes(b"NOT_A_PS4_PKG")
        with self.assertRaises(ValueError): inspect_pkg(self.pkg)
    def test_approval_and_draft_export(self):
        probe = inspect_pkg(self.pkg)
        with PackageStore(self.dir / "review.sqlite3") as store:
            store.put_probe(probe)
            with self.assertRaises(CatalogError):
                store.approve(str(self.pkg), game_id="demo", game_title="Demo",
                              kind="base", version="1.00",
                              target_firmware=None, required_package_ids=[],
                              rights_confirmed=False)
            store.approve(str(self.pkg), game_id="demo", game_title="Demo",
                          kind="base", version="1.00", target_firmware=None,
                          required_package_ids=[], rights_confirmed=True)
            catalog = store.export_draft()
            self.assertFalse(catalog["published"])
            self.assertEqual(catalog["games"][0]["packages"][0]["sha256"], probe.sha256)
        with PackageStore(self.dir / "review.sqlite3") as reopened:
            self.assertEqual(len(reopened.export_draft()["games"]), 1)
    def test_modified_file_pauses_approved_job(self):
        with PackageStore(self.dir / "review.sqlite3") as store:
            store.put_probe(inspect_pkg(self.pkg))
            store.approve(str(self.pkg), game_id="demo", game_title="Demo",
                          kind="base", version="1.00", target_firmware=None,
                          required_package_ids=[], rights_confirmed=True)
            self.pkg.write_bytes(PS4_PKG_MAGIC + b"different")
            self.assertEqual(store.recover_approved()[0][1], "changed")
            self.assertEqual(store.export_draft()["games"], [])
            self.assertEqual(store.rows()[0]["rights_confirmed"], 0)
    def test_dependency_validation_on_export(self):
        with PackageStore(self.dir / "review.sqlite3") as store:
            store.put_probe(inspect_pkg(self.pkg))
            store.approve(str(self.pkg), game_id="demo", game_title="Demo",
                          kind="update", version="1.10",
                          target_firmware="9.00",
                          required_package_ids=["sha256:" + "b" * 64],
                          rights_confirmed=True)
            with self.assertRaises(CatalogError): store.export_draft()
if __name__ == "__main__": unittest.main()
