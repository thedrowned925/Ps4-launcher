import copy
import unittest
from odium_pc.catalog import CatalogError, immutable_remote_path, order_packages, validate_catalog
A = "a" * 64
B = "b" * 64
C = "c" * 64
def package(digest, kind="base", depends=None):
    return {"package_id": f"sha256:{digest}", "sha256": digest,
            "filename": f"{digest[:8]}.pkg", "size_bytes": 10,
            "kind": kind, "version": "1.00", "target_firmware": None,
            "required_package_ids": depends or []}
class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"schema_version": 1, "published": False,
          "games": [{"game_id": "demo", "title": "Demo",
                     "packages": [package(A), package(B, "update", [f"sha256:{A}"]),
                                  package(C, "backport", [f"sha256:{B}"])]}]}
    def test_dependency_order(self):
        self.assertEqual(order_packages(self.catalog["games"][0]["packages"],
                         [f"sha256:{C}"]), [f"sha256:{A}", f"sha256:{B}", f"sha256:{C}"])
        self.assertEqual(order_packages(self.catalog["games"][0]["packages"],
                         [f"sha256:{C}"], {f"sha256:{A}"}), [f"sha256:{B}", f"sha256:{C}"])
    def test_validate_draft(self):
        validate_catalog(self.catalog)
    def test_reject_cycle(self):
        c = copy.deepcopy(self.catalog)
        c["games"][0]["packages"][0]["required_package_ids"] = [f"sha256:{C}"]
        with self.assertRaises(CatalogError): validate_catalog(c)
    def test_reject_missing_dependency(self):
        c = copy.deepcopy(self.catalog)
        c["games"][0]["packages"][2]["required_package_ids"] = [f"sha256:{'d'*64}"]
        with self.assertRaises(CatalogError): validate_catalog(c)
    def test_reject_duplicate(self):
        c = copy.deepcopy(self.catalog)
        c["games"][0]["packages"].append(package(A))
        with self.assertRaises(CatalogError): validate_catalog(c)
    def test_published_requires_pinned_source(self):
        c = copy.deepcopy(self.catalog)
        c["published"] = True
        with self.assertRaises(CatalogError): validate_catalog(c)
        for p in c["games"][0]["packages"]:
            p["source"] = {"repo_id": "owner/demo", "revision": "1" * 40,
                           "path": immutable_remote_path("demo", p["kind"], p["sha256"])}
        validate_catalog(c)
        c["games"][0]["packages"][0]["source"]["revision"] = "main"
        with self.assertRaises(CatalogError): validate_catalog(c)
    def test_reject_path_traversal(self):
        c = copy.deepcopy(self.catalog)
        c["published"] = True
        for p in c["games"][0]["packages"]:
            p["source"] = {"repo_id": "owner/demo", "revision": "1" * 40,
                           "path": "packages/test.pkg"}
        c["games"][0]["packages"][1]["source"]["path"] = "../secret.pkg"
        with self.assertRaises(CatalogError): validate_catalog(c)
    def test_reject_invalid_firmware(self):
        c = copy.deepcopy(self.catalog)
        c["games"][0]["packages"][2]["target_firmware"] = "9"
        with self.assertRaises(CatalogError): validate_catalog(c)
if __name__ == "__main__": unittest.main()
