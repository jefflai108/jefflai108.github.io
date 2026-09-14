"""Authored, offline fixtures for public snapshot installation and privacy bounds."""

import copy
import hashlib
import importlib.util
import json
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import warnings
import zipfile
from urllib.parse import urlsplit
from urllib.request import Request


SPEC = importlib.util.spec_from_file_location("corpus_assets", Path(__file__).with_name("install-taiwan-corpus-assets.py"))
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class PublicSnapshotTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.archive = self.root / "snapshot.zip"
        self.manifest_path = self.root / "manifest.json"
        self.source_path = self.root / "source.json"
        self.source_path.write_text(json.dumps(INSTALLER.SOURCE))
        self.tree = {
            "schema": "taiwan-corpus-discovery/v1", "mode": "public-index",
            "generated_at": "2026-09-14T12:00:00Z", "taxonomy_version": "authored-test/v1",
            "total_posts": 1, "total_replies": 2,
            "source_counts": {"ptt": {"posts": 1, "replies": 2}, "dcard": {"posts": 0, "replies": 0},
                              "threads": {"posts": 0, "replies": 0}},
            "topics": [{"id": "education", "label": "學習", "label_en": "Learning", "description": "Authored topic",
                        "children": [{"id": "education.general", "label": "一般", "description": "Authored branch",
                                      "coverage_target": True}]}],
            "leaves": [{"id": "a" * 64, "source": "ptt", "community": "SENIORHIGH", "title": "人工撰寫的測試標題",
                        "url": "https://www.ptt.cc/bbs/SENIORHIGH/M.1234567890.A.ABC.html",
                        "published_at": None, "collected_at": "2026-09-14T12:00:00Z",
                        "topic_id": "education", "branch_id": "education.general", "reply_count": 2,
                        "assignment": {"method": "community"},
                        "engagement": {"likes": None, "comments": 2, "pushes": 1, "boos": 0}}],
        }

    def prepare(self, members=None):
        content = {"index.html": b'<!doctype html><html data-mode="public-index"><title>Authored fixture</title></html>',
                   "app.js": b"document.body.textContent = 'Authored fixture';", "style.css": b"body { color: black; }",
                   "favicon.svg": b'<svg xmlns="http://www.w3.org/2000/svg"/>',
                   "data/tree.json": json.dumps(self.tree, ensure_ascii=False).encode()}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in members if members is not None else content.items():
                    archive.writestr(name, data)
        archive = self.archive.read_bytes()
        digest = hashlib.sha256(archive).hexdigest()
        self.manifest = {"schema": "taiwan-corpus-public-export/v1", "destination": "taiwan-corpus",
                         "archive_name": "taiwan-corpus-public-20260914T120000Z-" + digest[:12] + ".zip",
                         "asset_name": "taiwan-corpus-public-20260914T120000Z-" + digest[:12] + ".zip",
                         "archive_bytes": len(archive), "archive_sha256": digest, "content_mode": "public-index",
                         "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                                   for name, data in content.items()},
                         **{key: self.tree[key] for key in ("generated_at", "taxonomy_version", "total_posts",
                                                           "total_replies", "source_counts")}}
        self.save_manifest()
        return archive

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def install(self):
        return INSTALLER.install(self.archive, self.dist, self.manifest_path)

    def rejected(self):
        before = {str(path): path.read_bytes() for path in self.dist.rglob("*") if path.is_file()}
        with self.assertRaises((ValueError, TypeError, KeyError)):
            self.install()
        after = {str(path): path.read_bytes() for path in self.dist.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_install_and_repeat_replace_exact_snapshot(self):
        self.prepare()
        for _ in range(2):
            self.assertEqual(self.install(), 6)
        target = self.dist / "taiwan-corpus"
        self.assertEqual({str(path.relative_to(target)) for path in target.rglob("*") if path.is_file()},
                         INSTALLER.MEMBERS | {'snapshot.json'})
        self.assertEqual(json.loads((target / "data/tree.json").read_bytes()), self.tree)
        self.assertEqual(stat.S_IMODE((target / "data/tree.json").stat().st_mode), 0o644)
        self.assertEqual(json.loads((target / 'snapshot.json').read_bytes()), {
            'schema': 'taiwan-corpus-public-snapshot/v1', 'archive_sha256': self.manifest['archive_sha256'],
            'asset_name': self.manifest['asset_name'], 'generated_at': self.manifest['generated_at'], 'total_posts': 1})

    def test_archive_and_member_digest_mismatches(self):
        self.prepare()
        self.archive.write_bytes(self.archive.read_bytes() + b"changed")
        self.rejected()
        self.prepare()
        self.manifest["files"]["app.js"]["sha256"] = "0" * 64
        self.save_manifest()
        self.rejected()

    def test_missing_duplicate_traversal_and_special_zip_members(self):
        for members in ([('index.html', b'x')], [('index.html', b'x')] * 5,
                        [('../escape', b'x')], [('data/../escape', b'x')], [('/absolute', b'x')]):
            with self.subTest(members=members):
                self.prepare(members)
                self.rejected()
        self.prepare()
        with zipfile.ZipFile(self.archive) as archive:
            members = [(member.filename, archive.read(member)) for member in archive.infolist()]
        link = zipfile.ZipInfo("app.js")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.prepare([(link if name == 'app.js' else name, data) for name, data in members])
        self.rejected()

    def test_noncanonical_names_and_private_extra_files(self):
        for name in ('app.js\0private', 'private/catalog.sqlite', 'data/replies.json'):
            self.prepare([(name, b'authored extra file')])
            self.rejected()

    def test_destination_traversal_and_symlink(self):
        self.prepare()
        self.manifest["destination"] = "../escape"
        self.save_manifest()
        self.rejected()
        self.prepare()
        outside = self.root / "outside"
        outside.mkdir()
        (self.dist / "taiwan-corpus").symlink_to(outside, target_is_directory=True)
        self.rejected()
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_snapshot_is_untouched_on_bad_input_or_mixed_inventory(self):
        self.prepare()
        self.install()
        self.manifest["archive_sha256"] = "0" * 64
        self.save_manifest()
        self.rejected()
        self.prepare()
        (self.dist / "taiwan-corpus/extra.txt").write_text("Unrelated file")
        self.rejected()

    def test_public_index_refuses_content_and_author_fields(self):
        original = copy.deepcopy(self.tree)
        for field in ("text", "preview", "replies", "author", "username", "metadata"):
            with self.subTest(field=field):
                self.tree = copy.deepcopy(original)
                self.tree["leaves"][0][field] = "Authored disallowed payload"
                self.prepare()
                self.rejected()
        self.tree = copy.deepcopy(original)
        self.tree["leaves"][0]["assignment"]["matched_terms"] = ["Authored term"]
        self.prepare()
        self.rejected()

    def test_count_mismatch_duplicate_or_unassigned_roots(self):
        original = copy.deepcopy(self.tree)
        for mutate in (lambda tree: tree.update(total_posts=2),
                       lambda tree: tree['leaves'].append(copy.deepcopy(tree['leaves'][0])),
                       lambda tree: tree['leaves'][0].update(branch_id='missing'),
                       lambda tree: tree['source_counts']['ptt'].update(posts=True)):
            self.tree = copy.deepcopy(original)
            mutate(self.tree)
            self.prepare()
            self.rejected()

    def test_source_link_validation(self):
        for url in ('javascript:alert(1)', 'https://user:secret@www.ptt.cc/bbs/Food/M.1234567890.A.ABC.html',
                    'https://www.ptt.cc.evil.test/bbs/Food/M.1234567890.A.ABC.html',
                    'https://www.ptt.cc/bbs/Food/M.1234567890.A.ABC.html?token=private'):
            self.tree['leaves'][0]['url'] = url
            self.prepare()
            self.rejected()

    def test_namespace_sizes_and_versioned_name_are_strict(self):
        self.prepare()
        original = copy.deepcopy(self.manifest)
        for changes in ({'release_tag': 'elsewhere'}, {'repository': 'other/repo'}, {'url': 'https://evil.test/payload.zip'},
                        {'archive_name': 'taiwan-corpus-public.zip'}, {'content_mode': 'full-corpus'},
                        {'archive_bytes': INSTALLER.MAX_ARCHIVE + 1}, {'archive_bytes': True}):
            self.manifest = {**original, **changes}
            self.save_manifest()
            self.rejected()
        with self.assertRaises(ValueError):
            INSTALLER.validate_manifest(b' ' * (INSTALLER.MAX_MANIFEST + 1))

    def test_release_install_pins_namespace_and_rechecks_manifest(self):
        archive = self.prepare()
        raw = self.manifest_path.read_bytes()
        with patch.object(INSTALLER, 'download', side_effect=[raw, archive, raw]) as download:
            self.assertEqual(INSTALLER.install_release(self.dist, self.source_path), 6)
            self.assertEqual([call.args[0] for call in download.call_args_list],
                             ['taiwan-corpus-manifest.json', self.manifest['archive_name'], 'taiwan-corpus-manifest.json'])
        before = (self.dist / 'taiwan-corpus/data/tree.json').read_bytes()
        with patch.object(INSTALLER, 'download', side_effect=[raw, archive, raw + b'\n']):
            with self.assertRaisesRegex(ValueError, 'changed'):
                INSTALLER.install_release(self.dist, self.source_path)
        self.assertEqual((self.dist / 'taiwan-corpus/data/tree.json').read_bytes(), before)

    def test_release_source_cannot_redirect_downloads(self):
        self.source_path.write_text(json.dumps({**INSTALLER.SOURCE, 'repository': 'other/repo'}))
        with patch.object(INSTALLER, 'download') as download:
            with self.assertRaises(ValueError):
                INSTALLER.install_release(self.dist, self.source_path)
            download.assert_not_called()

    def test_both_pointer_reads_bypass_cache_without_changing_asset_namespace(self):
        archive = self.prepare()
        raw = self.manifest_path.read_bytes()
        responses = []
        for data in (raw, archive, raw):
            response = MagicMock()
            response.headers = {'Content-Length': str(len(data))}
            response.read.side_effect = io.BytesIO(data).read
            response.__enter__.return_value = response
            responses.append(response)
        with patch.object(INSTALLER, 'build_opener') as opener:
            opener.return_value.open.side_effect = responses
            self.assertEqual(INSTALLER.install_release(self.dist, self.source_path), 6)
            requests = [call.args[0] for call in opener.return_value.open.call_args_list]
        expected = urlsplit(INSTALLER.asset_url(INSTALLER.SOURCE['manifest_asset']))
        for request in (requests[0], requests[2]):
            actual = urlsplit(request.full_url)
            self.assertEqual((actual.scheme, actual.netloc, actual.path),
                             (expected.scheme, expected.netloc, expected.path))
            self.assertRegex(actual.query, r'^check=[a-f0-9]{32}$')
            self.assertEqual(request.get_header('Cache-control'), 'no-cache')
        self.assertNotEqual(requests[0].full_url, requests[2].full_url)
        self.assertEqual(requests[1].full_url, INSTALLER.asset_url(self.manifest['archive_name']))
        self.assertIsNone(requests[1].get_header('Cache-control'))

    def test_download_size_bounds(self):
        class Response:
            def __init__(self, body, headers):
                self.body, self.headers = body, headers
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return self.body[:limit]
        for response in (Response(b'', {'Content-Length': '100'}), Response(b'x' * 11, {})):
            with patch.object(INSTALLER, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaisesRegex(ValueError, 'size bound'):
                    INSTALLER.download('taiwan-corpus-manifest.json', 10)

    def test_redirect_refuses_other_namespace_or_host(self):
        request = Request(INSTALLER.asset_url('taiwan-corpus-manifest.json'))
        for url in ('http://github.com/insecure', 'https://evil.test/archive',
                    'https://github.com/other/repo/releases/download/taiwan-corpus-public/taiwan-corpus-manifest.json'):
            with self.assertRaises(ValueError):
                INSTALLER.ReleaseRedirect().redirect_request(request, None, 302, 'Found', {}, url)


if __name__ == '__main__':
    unittest.main()
