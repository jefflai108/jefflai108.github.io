"""Offline checks for release archive validation and safe installation."""

import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "gallery_assets", Path(__file__).with_name("install-image-comparison-assets.py")
)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class AssetInstallationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.archive = self.root / "images.zip"
        self.manifest_path = self.root / "manifest.json"
        self.name = "original/gemini/01.jpg"
        self.content = b"image bytes used only by the offline archive test"
        self.manifest = {
            "destination": "gpt-vs-gemini/images",
            "files": {self.name: {
                "bytes": len(self.content),
                "sha256": hashlib.sha256(self.content).hexdigest(),
            }},
        }

    def prepare(self, members=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w") as archive:
                for name, content in members or [(self.name, self.content)]:
                    archive.writestr(name, content)
        data = self.archive.read_bytes()
        self.manifest.update(archive_bytes=len(data), archive_sha256=hashlib.sha256(data).hexdigest())
        self.save_manifest()

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def install(self):
        return INSTALLER.install(self.archive, self.dist, self.manifest_path)

    def assert_rejected_without_writes(self):
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(list(self.dist.iterdir()), [])

    def test_valid_archive_and_repeat_install(self):
        self.prepare()
        for _ in range(2):
            self.assertEqual(self.install(), 1)
        target = self.dist / "gpt-vs-gemini/images" / self.name
        self.assertEqual(target.read_bytes(), self.content)
        self.assertEqual([p for p in self.dist.rglob("*") if p.is_file()], [target])

    def test_archive_hash_mismatch(self):
        self.prepare()
        self.manifest["archive_sha256"] = "0" * 64
        self.save_manifest()
        self.assert_rejected_without_writes()

    def test_image_hash_mismatch(self):
        self.prepare()
        self.manifest["files"][self.name]["sha256"] = "0" * 64
        self.save_manifest()
        self.assert_rejected_without_writes()

    def test_unexpected_member(self):
        self.prepare([(self.name, self.content), ("extra.jpg", b"unexpected")])
        self.assert_rejected_without_writes()

    def test_duplicate_member(self):
        self.prepare([(self.name, self.content), (self.name, self.content)])
        self.assert_rejected_without_writes()

    def test_traversal_member(self):
        self.prepare([(self.name, self.content), ("../escape.jpg", b"escape")])
        self.assert_rejected_without_writes()
        self.assertFalse((self.root / "escape.jpg").exists())

    def test_symlink_member(self):
        member = zipfile.ZipInfo(self.name)
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.prepare([(member, self.content)])
        self.assert_rejected_without_writes()

    def test_destination_traversal(self):
        self.prepare()
        self.manifest["destination"] = "../escape"
        self.save_manifest()
        self.assert_rejected_without_writes()

    def test_existing_destination_symlink(self):
        self.prepare()
        outside = self.root / "outside"
        outside.mkdir()
        (self.dist / "gpt-vs-gemini").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
