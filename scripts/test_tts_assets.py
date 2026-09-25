import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('tts_assets', Path(__file__).with_name('install-tts-assets.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NAME = 'tts/audio/v3-benchmark-2026-09-25/eleven_v3/hua/p01.mp3'


class AudioArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'audio.zip'
        self.destination = self.root / 'dist'

    def fixture(self, names=None, symlink=False):
        payload = b'authored test audio bytes'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name in names or [NAME]:
                info = zipfile.ZipInfo(name)
                if symlink:
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, payload)
        return {'version': 1, 'archiveBytes': self.archive.stat().st_size, 'archiveSha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(), 'files': [{'path': NAME, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]}

    def rejected(self, manifest):
        with self.assertRaises(ValueError):
            module.install(self.archive, self.destination, manifest)
        self.assertFalse(self.destination.exists())

    def test_installs_exact_bytes(self):
        manifest = self.fixture()
        self.assertEqual(module.install(self.archive, self.destination, manifest), 1)
        self.assertEqual((self.destination / NAME).read_bytes(), b'authored test audio bytes')

    def test_english_and_mandarin_coexist(self):
        module.install(self.archive, self.destination, self.fixture())
        for variant in ['en', 'en-us']:
            english = f'tts/audio/v3-benchmark-{variant}-2026-09-25/eleven_v3/hua/en01.mp3'
            manifest = self.fixture([english])
            manifest['files'][0]['path'] = english
            self.assertEqual(module.install(self.archive, self.destination, manifest), 1)
            self.assertEqual((self.destination / english).read_bytes(), (self.destination / NAME).read_bytes())

    def test_rejects_changed_archive(self):
        manifest = self.fixture()
        manifest['archiveSha256'] = '0' * 64
        self.rejected(manifest)

    def test_rejects_changed_audio(self):
        manifest = self.fixture()
        manifest['files'][0]['sha256'] = '0' * 64
        self.rejected(manifest)

    def test_rejects_missing_or_extra_audio(self):
        self.rejected(self.fixture([NAME, NAME.replace('p01', 'p02')]))

    def test_rejects_duplicate_members(self):
        self.rejected(self.fixture([NAME, NAME]))

    def test_rejects_traversal(self):
        manifest = self.fixture()
        manifest['files'][0]['path'] = '../outside.mp3'
        self.rejected(manifest)

    def test_rejects_symlink(self):
        self.rejected(self.fixture(symlink=True))


if __name__ == '__main__':
    unittest.main()
