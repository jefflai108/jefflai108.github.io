"""Integration checks use synthetic clips in a temporary DB, never production labels."""
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import wave
import server

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'audio').mkdir()
        for n in range(2):
            with wave.open(str(self.root / 'audio' / f'taigi-{n:08d}.wav'), 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\0\0' * 1600)
        self.manifest = self.root / 'manifest.jsonl'
        self.manifest.write_text('\n'.join(json.dumps({'id':f'taigi-{n:08d}','audio':f'audio/taigi-{n:08d}.wav','text':'原始台語'},ensure_ascii=False) for n in range(2)))
        self.db = self.root / 'review.sqlite3'
        server.initialize(self.db, self.manifest, expected_count=2)
        self.http = server.make_server('127.0.0.1', 0, self.db, 'test-only-key', {'https://jefflai108.github.io'})
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'
    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(); self.tmp.cleanup()
    def call(self, path, body=None, headers=None, method=None, auth=True):
        h = {'Authorization':'Bearer test-only-key'} if auth else {}
        h.update(headers or {})
        req = Request(self.base+quote(path,safe='/?=&'), data=json.dumps(body).encode() if body is not None else None, headers=h, method=method or ('PUT' if body is not None else 'GET'))
        try: response = urlopen(req)
        except HTTPError as e: response = e
        try:
            data = response.read()
            return response.status, dict(response.headers), json.loads(data) if response.headers.get_content_type() == 'application/json' else data
        finally:
            response.close()
    def payload(self, text, revision=0, editor='Alice', status='unreviewed'):
        return {'annotation':text,'revision':revision,'editor':editor,'status':status}
    def test_private_routes_and_ranges(self):
        for path in ['/api/meta','/api/clips','/api/export','/api/clips/taigi-00000000/audio']:
            self.assertEqual(self.call(path,auth=False)[0],401)
        status,h,data=self.call('/api/clips/taigi-00000000/audio',headers={'Range':'bytes=0-43','Origin':'https://jefflai108.github.io'})
        self.assertEqual(status,206); self.assertEqual(len(data),44); self.assertEqual(data[:4],b'RIFF')
        self.assertEqual(h['Access-Control-Allow-Origin'],'https://jefflai108.github.io')
        self.assertEqual(self.call('/api/clips/taigi-00000000/audio',headers={'Range':'bytes=999999-'})[0],416)
        self.assertEqual(self.call('/api/clips/../../etc/passwd')[0],404)
        self.assertEqual(self.call('/api/meta',headers={'Origin':'https://evil.example'},method='OPTIONS')[0],403)
        self.assertEqual(self.call('/api/meta',headers={'Origin':'https://jefflai108.github.io'},method='OPTIONS')[0],204)
    def test_initial_copy_persistence_export_and_immutable_original(self):
        rows=self.call('/api/clips')[2]['clips']; self.assertEqual(len(rows),2)
        self.assertTrue(all(r['original']==r['annotation'] and r['revision']==0 for r in rows))
        self.assertFalse(any('audio_path' in r for r in rows))
        status,_,result=self.call('/api/clips/taigi-00000000',self.payload('正確台語'))
        self.assertEqual(status,200); self.assertEqual(result['clip']['revision'],1)
        server.initialize(self.db,self.manifest,expected_count=2)
        row=self.call('/api/clips/taigi-00000000')[2]['clip']
        self.assertEqual(row['annotation'],'正確台語'); self.assertEqual(row['original'],'原始台語')
        history=self.call('/api/clips/taigi-00000000/history')[2]['history']; self.assertEqual(len(history),1)
        self.assertEqual(self.call('/api/export')[2]['clips'][0]['annotation'],'正確台語')
        self.assertEqual(self.call('/api/clips?q=正確')[2]['total'],1)
        malicious=self.payload('changed'); malicious['original']='overwrite'
        self.assertEqual(self.call('/api/clips/taigi-00000000',malicious)[0],400)
    def test_two_editors_conflict_and_idempotent_retry(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(lambda name:self.call('/api/clips/taigi-00000000',self.payload(name,editor=name)),['Alice','Bob']))
        self.assertEqual(sorted(r[0] for r in replies),[200,409])
        winner=next(r[2]['clip'] for r in replies if r[0]==200)
        self.assertEqual(self.call('/api/clips/taigi-00000000',self.payload(winner['annotation']))[0],200)
        self.assertEqual(len(self.call('/api/clips/taigi-00000000/history')[2]['history']),1)
        self.assertEqual(self.call('/api/clips/taigi-00000000',self.payload('merged',1,'Carol'))[0],200)
        self.assertEqual(self.call('/api/changes?since=0')[2]['clips'][0]['annotation'],'merged')
    def test_blank_annotation_valid_and_validation_rejects_other_splits(self):
        self.assertEqual(self.call('/api/clips/taigi-00000000',self.payload('',status='reviewed'))[0],200)
        self.assertEqual(self.call('/api/clips?status=reviewed')[2]['total'],1)
        self.assertEqual(self.call('/api/clips/taigi-99999999',self.payload('train'))[0],404)
        self.assertEqual(self.call('/api/clips/taigi-00000000',self.payload('x',editor=''))[0],400)
        with self.assertRaises(ValueError): server.initialize(self.db,self.manifest)
        self.manifest.write_text(self.manifest.read_text().replace('原始','別的'))
        with self.assertRaises(ValueError): server.initialize(self.db,self.manifest,expected_count=2)

    def add_dev2(self):
        # Deliberately overlap IDs: even a colliding ID must stay in its own set.
        manifest = self.root / 'dev2.jsonl'
        manifest.write_text(self.manifest.read_text().replace('原始台語', '第二組台語'))
        path = self.root / 'dev2.sqlite3'
        server.initialize(path, manifest, 2, source=server.DEV2_SOURCE,
                          fingerprint=hashlib.sha256(manifest.read_bytes()).hexdigest())
        self.http.dev2_db_path = str(path)
        return path, manifest

    def test_dev2_import_preserves_existing_edits_and_exports_each_source(self):
        self.call('/api/clips/taigi-00000000', self.payload('Dev correction', editor='Stella', status='reviewed'))
        with server.connect(self.db) as db:
            before = {table: [tuple(r) for r in db.execute('SELECT * FROM ' + table)]
                      for table in ['clips', 'history', 'metadata']}
        self.add_dev2()
        with server.connect(self.db) as db:
            after = {table: [tuple(r) for r in db.execute('SELECT * FROM ' + table)] for table in before}
        self.assertEqual(before, after)
        self.assertEqual(self.call('/api/meta')[2]['stats']['reviewed'], 1)
        self.assertEqual(self.call('/api/dev2/meta')[2]['stats']['reviewed'], 0)
        self.assertEqual(self.call('/api/dev2/export')[2]['source'], server.DEV2_SOURCE)
        self.assertEqual(self.call('/api/export')[2]['source'], server.SOURCE)
        self.assertEqual(self.call('/api/dev2/clips')[2]['clips'][0]['annotation'], '第二組台語')
        self.assertEqual(self.call('/api/dev2/recordings')[0], 404)

    def test_dev2_conflicts_changes_history_and_audio_are_isolated(self):
        self.add_dev2()
        path = '/api/dev2/clips/taigi-00000000'
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda name: self.call(path, self.payload(name, editor=name, status='reviewed')), ['Stella', 'Colette']))
        self.assertEqual(sorted(r[0] for r in replies), [200, 409])
        winner = next(r[2]['clip'] for r in replies if r[0] == 200)
        self.assertEqual(self.call(path, self.payload(winner['annotation'], status='reviewed'))[0], 200)
        self.assertEqual(len(self.call(path + '/history')[2]['history']), 1)
        self.assertEqual(len(self.call('/api/dev2/changes?since=0')[2]['clips']), 1)
        self.assertEqual(self.call('/api/changes?since=0')[2]['clips'], [])
        self.assertEqual(self.call('/api/clips/taigi-00000000')[2]['clip']['revision'], 0)
        self.assertEqual(self.call('/api/dev2/clips?status=reviewed')[2]['total'], 1)
        status, headers, data = self.call(path + '/audio', headers={'Range': 'bytes=0-43', 'Origin': 'https://jefflai108.github.io'})
        self.assertEqual(status, 206); self.assertEqual(data[:4], b'RIFF')
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://jefflai108.github.io')

    def test_dev2_access_and_source_guards(self):
        self.assertEqual(self.call('/api/dev2/meta')[0], 503)
        path, manifest = self.add_dev2()
        for route in ['/api/dev2/meta', '/api/dev2/export', '/api/dev2/changes', '/api/dev2/clips', '/api/dev2/clips/taigi-00000000/audio']:
            self.assertEqual(self.call(route, auth=False)[0], 401)
        self.assertEqual(self.call('/api/dev2/clips/taigi-00000000', self.payload('x'), auth=False)[0], 401)
        self.assertEqual(self.call('/api/dev2/clips/taigi-00000000', self.payload('x'), headers={'Origin': 'https://evil.example'})[0], 403)
        with self.assertRaises(ValueError):
            server.initialize(path, manifest, 2, source=server.DEV2_SOURCE, fingerprint='wrong')
        with self.assertRaises(ValueError):
            server.initialize(path, manifest, 2)

if __name__=='__main__': unittest.main()
