"""Zero-network tests: fake Hugging Face responses, including corruption/error paths."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from odium_pc.catalog import CatalogError
from odium_pc.hf_stage import prepare_tasks, stage_approved, create_ready_catalog
from odium_pc.ingest import PS4_PKG_MAGIC, inspect_pkg
from odium_pc.store import PackageStore


class FakeHub:
    def __init__(self, *, is_public=True, upload_changes=True):
        self.sha = "a" * 40
        self.is_public = is_public
        self.files = {}
        self.uploads = 0
        self.upload_changes = upload_changes

    def repo_info(self, **kwargs):
        return SimpleNamespace(sha=self.sha, private=not self.is_public)

    def get_paths_info(self, *, paths, **kwargs):
        return [SimpleNamespace(path=p) for p in paths if p in self.files]

    def upload_file(self, *, path_in_repo, path_or_fileobj, parent_commit, **kwargs):
        assert parent_commit == self.sha
        source = Path(path_or_fileobj)
        data = source.read_bytes()
        import hashlib
        self.files[path_in_repo] = (len(data), hashlib.sha256(data).hexdigest())
        self.uploads += 1
        if self.upload_changes:
            self.sha = f"{self.uploads:040x}"
        return SimpleNamespace(oid=self.sha)

    def metadata(self, url):
        # fake://dataset/path?revision=...
        path, revision = url.rsplit("?", 1)
        key = path.partition("fake://")[2]
        size, digest = self.files[key]
        return SimpleNamespace(size=size, etag=digest, commit_hash=revision)


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.pkg = self.directory / "authorized.pkg"
        self.pkg.write_bytes(PS4_PKG_MAGIC + b"developer-own-homebrew" * 50)
        self.store = PackageStore(self.directory / "db.sqlite3")
        self.addCleanup(self.store.close)
        self.store.put_probe(inspect_pkg(self.pkg))
        self.store.approve(str(self.pkg), game_id="demo", game_title="Demo",
                           kind="base", version="1.00", target_firmware=None,
                           required_package_ids=[], rights_confirmed=True)

    @staticmethod
    def url_builder(*, filename, revision, **kwargs):
        return "fake://" + filename + "?" + revision

    def stage(self, hub, metadata=None):
        return stage_approved(self.store, "demo/authorized-homebrew",
                              api=hub, metadata=metadata or hub.metadata,
                              url_builder=self.url_builder)

    def test_plan_has_stable_content_addressed_path(self):
        task, = prepare_tasks(self.store, "demo/authorized-homebrew")
        self.assertIn(task.sha256, task.remote_path)
        self.assertTrue(task.local_path.endswith(".pkg"))

    def test_stage_and_reuse_without_reupload(self):
        hub = FakeHub()
        self.stage(hub)
        self.assertEqual(hub.uploads, 1)
        ready = create_ready_catalog(self.store, "demo/authorized-homebrew")
        self.assertTrue(ready["published"])
        self.assertEqual(ready["games"][0]["packages"][0]["source"]["revision"], hub.sha)
        self.stage(hub)
        self.assertEqual(hub.uploads, 1)

    def test_private_repo_refused(self):
        hub = FakeHub(is_public=False)
        with self.assertRaises(CatalogError):
            self.stage(hub)
        self.assertEqual(hub.uploads, 0)

    def test_remote_hash_mismatch_refused(self):
        hub = FakeHub()
        def wrong(url):
            meta = hub.metadata(url)
            meta.etag = "0" * 64
            return meta
        with self.assertRaises(CatalogError):
            self.stage(hub, metadata=wrong)
        with self.assertRaises(CatalogError):
            create_ready_catalog(self.store, "demo/authorized-homebrew")

    def test_source_changed_refused(self):
        self.pkg.write_bytes(PS4_PKG_MAGIC + b"not-original")
        hub = FakeHub()
        with self.assertRaises(CatalogError):
            self.stage(hub)
        self.assertEqual(hub.uploads, 0)

    def test_no_approval_no_upload(self):
        self.store.db.execute("UPDATE packages SET approved=0")
        self.store.db.commit()
        with self.assertRaises(CatalogError):
            self.stage(FakeHub())


if __name__ == "__main__":
    unittest.main()
