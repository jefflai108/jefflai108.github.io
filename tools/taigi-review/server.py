#!/usr/bin/env python3
"""One shared, authenticated Taigi dev review store; audio stays on this Mac."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
import wave
import recordings

EXPECTED_COUNT = 5424
EXPECTED_FINGERPRINT = '9f676034bdaa564a554d93443dbf1836fc2782270cb1eb36b75679b27838c78d'
SOURCE = {"repo": "jefflai108/streaming-taigi-asr", "config": "default", "split": "validation", "revision": "6722261aee9c4d729b4c5bdd629ec3ebf2060179"}
DEV2_SOURCE = {"repo": "jefflai108/streaming-taigi-asr", "config": "default", "split": "validation2", "revision": "7889df22aa03f5dd1805737d24c5d39729a60a54"}
DEV2_COUNT = 5133
DEV2_FINGERPRINT = '0848a6246cb5d25a2ef7c8415416c87686cbd2df258d543e03794db4953daee0'
STATUSES = {"unreviewed", "reviewed", "flagged"}


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(db_path, manifest, expected_count=EXPECTED_COUNT, *, source=SOURCE, fingerprint=EXPECTED_FINGERPRINT):
    manifest = Path(manifest).resolve()
    rows = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    actual_fingerprint = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if (expected_count == EXPECTED_COUNT or source != SOURCE) and actual_fingerprint != fingerprint:
        raise ValueError('Manifest does not match the verified HF dev snapshot')
    if len(rows) != expected_count or len({r['id'] for r in rows}) != expected_count:
        raise ValueError("Refusing to import: unexpected dev split size or duplicate IDs")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript('''
        CREATE TABLE IF NOT EXISTS clips (
          id TEXT PRIMARY KEY, position INTEGER UNIQUE NOT NULL,
          original TEXT NOT NULL, annotation TEXT NOT NULL, audio_path TEXT NOT NULL,
          duration REAL NOT NULL, status TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK(status IN ('unreviewed','reviewed','flagged')),
          revision INTEGER NOT NULL DEFAULT 0, updated_at TEXT, updated_by TEXT);
        CREATE TABLE IF NOT EXISTS history (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, clip_id TEXT NOT NULL REFERENCES clips(id),
          revision INTEGER NOT NULL, annotation TEXT NOT NULL, status TEXT NOT NULL,
          editor TEXT NOT NULL, saved_at TEXT NOT NULL, UNIQUE(clip_id, revision));
        CREATE INDEX IF NOT EXISTS idx_clips_status_position ON clips(status, position);
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        existing = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
        if existing and existing[0] != actual_fingerprint:
            raise ValueError("Dev manifest changed; refusing to modify existing annotations")
        existing_source = db.execute("SELECT value FROM metadata WHERE key='source'").fetchone()
        if existing_source and json.loads(existing_source[0]) != source:
            raise ValueError("Review source changed; refusing to modify existing annotations")
        count = db.execute("SELECT count(*) FROM clips").fetchone()[0]
        if count and count != expected_count:
            raise ValueError("Existing database row count does not match dev split")
        if not count:
            for pos, row in enumerate(rows):
                audio = (manifest.parent / row['audio']).resolve()
                if not audio.is_relative_to(manifest.parent / 'audio') or not audio.is_file():
                    raise ValueError("Invalid or missing dev audio")
                with wave.open(str(audio), 'rb') as wav:
                    duration = wav.getnframes() / wav.getframerate()
                db.execute("INSERT INTO clips(id,position,original,annotation,audio_path,duration) VALUES(?,?,?,?,?,?)",
                           (row['id'], pos, row['text'], row['text'], str(audio), duration))
            db.execute("INSERT INTO metadata VALUES('manifest_sha256',?)", (actual_fingerprint,))
            db.execute("INSERT INTO metadata VALUES('source',?)", (json.dumps(source),))
        db.execute("PRAGMA optimize")
    recordings.initialize(db_path)


def public_row(row):
    return {k: row[k] for k in row.keys() if k != 'audio_path'}


def save(db_path, clip_id, payload):
    if not isinstance(payload, dict) or set(payload) != {'annotation', 'status', 'revision', 'editor'}:
        return 400, {"error": "Invalid annotation fields"}
    text, status, revision, editor = (payload[k] for k in ('annotation', 'status', 'revision', 'editor'))
    if not isinstance(text, str) or len(text) > 10000 or type(revision) is not int or revision < 0:
        return 400, {"error": "Invalid transcript or revision"}
    if not isinstance(status, str) or status not in STATUSES:
        return 400, {"error": "Choose a valid review status"}
    if not isinstance(editor, str) or not 1 <= len(editor.strip()) <= 80:
        return 400, {"error": "Enter your name (1–80 characters) before saving"}
    with connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        if row is None:
            return 404, {"error": "Clip not found in dev set"}
        # Idempotent retry after a lost response, including changed revisions.
        if row['annotation'] == text and row['status'] == status and row['revision'] != revision:
            return 200, {"clip": public_row(row)}
        if row['revision'] != revision:
            return 409, {"error": "Someone else saved this clip. Compare both versions before saving.", "clip": public_row(row)}
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        db.execute("UPDATE clips SET annotation=?,status=?,revision=revision+1,updated_at=?,updated_by=? WHERE id=? AND revision=?",
                   (text, status, now, editor.strip(), clip_id, revision))
        db.execute("INSERT INTO history(clip_id,revision,annotation,status,editor,saved_at) VALUES(?,?,?,?,?,?)",
                   (clip_id, revision + 1, text, status, editor.strip(), now))
        updated = public_row(db.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone())
    return 200, {"clip": updated}


class Handler(BaseHTTPRequestHandler):
    server_version = 'TaigiReview'

    def log_message(self, fmt, *args):
        # Never log authorization, paths, query strings, or transcript text.
        pass

    def cors(self):
        origin = self.headers.get('Origin', '')
        if origin in self.server.allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')

    def respond(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        supplied = self.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + self.server.access_key).encode()):
            self.respond(401, {"error": "Open your private invitation link to access this review."})
            return False
        return True

    def do_OPTIONS(self):
        if self.headers.get('Origin') not in self.server.allowed_origins:
            return self.respond(403, {"error": "Origin not allowed"})
        self.send_response(204)
        self.cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, Range')
        self.send_header('Access-Control-Max-Age', '3600')
        self.end_headers()

    def review_route(self, path):
        # Choose per request; never mutate the shared server's DB path.
        if path.startswith('/api/dev2/'):
            return '/api/' + path[len('/api/dev2/'):], self.server.dev2_db_path
        return path, self.server.db_path

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/health':
            return self.respond(200, {"ok": True, "service": "taigi-review"})
        if not self.authorized():
            return
        try:
            if path == '/api/recordings' or path.startswith('/api/recordings/'):
                return recordings.get(self, path, parse_qs(urlparse(self.path).query))
            path, db_path = self.review_route(path)
            if db_path is None:
                return self.respond(503, {"error": "Dev2 review is not available yet. Please retry shortly."})
            with connect(db_path) as db:
                source = json.loads(db.execute("SELECT value FROM metadata WHERE key='source'").fetchone()[0])
                if path == '/api/meta':
                    stats = dict(db.execute("SELECT count(*) total, sum(status='reviewed') reviewed, sum(status='flagged') flagged, sum(annotation != original) corrected, sum(duration) seconds FROM clips").fetchone())
                    seq = db.execute("SELECT coalesce(max(sequence),0) FROM history").fetchone()[0]
                    return self.respond(200, {"source": source, "stats": stats, "sequence": seq})
                if path == '/api/clips':
                    query = parse_qs(urlparse(self.path).query)
                    offset = max(0, int(query.get('offset', ['0'])[0]))
                    limit = max(1, min(100, int(query.get('limit', ['30'])[0])))
                    q = query.get('q', [''])[0][:200]
                    status = query.get('status', ['all'])[0]
                    where, params = [], []
                    if status in STATUSES:
                        where.append('status=?'); params.append(status)
                    elif status == 'corrected':
                        where.append('annotation != original')
                    elif status != 'all':
                        return self.respond(400, {"error": "Invalid filter"})
                    if q:
                        where.append("(instr(id,?) > 0 OR instr(original,?) > 0 OR instr(annotation,?) > 0)")
                        params.extend([q, q, q])
                    clause = ' WHERE ' + ' AND '.join(where) if where else ''
                    total = db.execute('SELECT count(*) FROM clips' + clause, params).fetchone()[0]
                    rows = db.execute('SELECT * FROM clips' + clause + ' ORDER BY position LIMIT ? OFFSET ?', params + [limit, offset]).fetchall()
                    return self.respond(200, {"clips": [public_row(r) for r in rows], "total": total, "offset": offset})
                if path == '/api/changes':
                    since = max(0, int(parse_qs(urlparse(self.path).query).get('since', ['0'])[0]))
                    latest = db.execute('SELECT coalesce(max(sequence),0) FROM history').fetchone()[0]
                    rows = db.execute('SELECT * FROM clips WHERE id IN (SELECT clip_id FROM history WHERE sequence>?) ORDER BY position', (since,)).fetchall()
                    return self.respond(200, {"clips": [public_row(r) for r in rows], "sequence": latest})
                if path == '/api/export':
                    rows = db.execute('SELECT * FROM clips ORDER BY position').fetchall()
                    return self.respond(200, {"source": source, "exported_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), "clips": [public_row(r) for r in rows]})
                match = re.fullmatch(r'/api/clips/([A-Za-z0-9][A-Za-z0-9_-]{0,127})(/history|/audio)?', path)
                if match:
                    row = db.execute('SELECT * FROM clips WHERE id=?', (match[1],)).fetchone()
                    if row is None:
                        return self.respond(404, {"error": "Clip not found in dev set"})
                    if match[2] == '/audio':
                        return self.audio(row['audio_path'])
                    if match[2] == '/history':
                        rows = db.execute('SELECT revision,annotation,status,editor,saved_at FROM history WHERE clip_id=? ORDER BY revision DESC LIMIT 100', (match[1],)).fetchall()
                        return self.respond(200, {"history": [dict(r) for r in rows]})
                    return self.respond(200, {"clip": public_row(row)})
            return self.respond(404, {"error": "Not found"})
        except (ValueError, TypeError):
            return self.respond(400, {"error": "Invalid request"})
        except (sqlite3.Error, OSError):
            return self.respond(503, {"error": "The shared store is temporarily unavailable. Your draft has not been saved."})

    def audio(self, filename):
        file = Path(filename)
        size = file.stat().st_size
        start, end, code = 0, size - 1, 200
        value = self.headers.get('Range')
        if value:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()):
                return self.respond(416, {"error": "Invalid byte range"})
            if match[1]:
                start = int(match[1]); end = min(int(match[2]), size - 1) if match[2] else size - 1
            else:
                start = max(0, size - int(match[2]))
            if start > end or start >= size:
                return self.respond(416, {"error": "Range unavailable"})
            code = 206
        self.send_response(code)
        self.cors()
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Cache-Control', 'private, max-age=86400')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if code == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with file.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                data = stream.read(min(65536, remaining))
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)

    def do_PUT(self):
        if not self.authorized():
            return
        if self.headers.get('Origin') and self.headers['Origin'] not in self.server.allowed_origins:
            return self.respond(403, {"error": "Origin not allowed"})
        path = urlparse(self.path).path
        recording = re.fullmatch(r'/api/recordings/(' + recordings.ID_PATTERN + ')', path)
        path, db_path = self.review_route(path)
        match = recording or re.fullmatch(r'/api/clips/([A-Za-z0-9][A-Za-z0-9_-]{0,127})', path)
        if not match:
            return self.respond(404, {"error": "Not found"})
        if db_path is None:
            return self.respond(503, {"error": "Dev2 review is not available yet. Please retry shortly."})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                return self.respond(413, {"error": "Request too large"})
            payload = json.loads(self.rfile.read(length))
            writer = recordings.save if recording else save
            code, body = writer(db_path, match[1], payload)
            self.respond(code, body)
        except (ValueError, UnicodeError, TypeError):
            self.respond(400, {"error": "Invalid request"})
        except sqlite3.Error:
            self.respond(503, {"error": "Save failed. Please retry; your draft is still in the editor."})

    def do_POST(self):
        if not self.authorized():
            return
        if self.headers.get('Origin') and self.headers['Origin'] not in self.server.allowed_origins:
            return self.respond(403, {"error": "Origin not allowed"})
        if urlparse(self.path).path != '/api/recordings':
            return self.respond(404, {"error": "Not found"})
        try:
            self.connection.settimeout(120)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= recordings.MAX_BODY:
                return self.respond(413, {"error": "Recording upload is too large"})
            payload = json.loads(self.rfile.read(length))
            code, body = recordings.create(self.server.db_path, payload)
            self.respond(code, body)
        except (ValueError, UnicodeError, TypeError) as error:
            self.respond(400, {"error": str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else 'Invalid recording upload'})
        except (sqlite3.Error, OSError):
            self.respond(503, {"error": "Recording could not be saved. Keep your take and retry."})


def make_server(host, port, db_path, access_key, origins, *, dev2_db_path=None):
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path = str(db_path)
    server.dev2_db_path = str(dev2_db_path) if dev2_db_path is not None else None
    server.access_key = access_key
    server.allowed_origins = origins
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if len(config['access_key']) < 32:
        raise ValueError('Access key must contain at least 32 characters')
    initialize(config['db_path'], config['manifest'])
    os.chmod(config['db_path'], 0o600)
    dev2 = config.get('dev2')
    if dev2:
        if Path(dev2['db_path']).resolve() == Path(config['db_path']).resolve():
            raise ValueError('Dev2 requires its own review database')
        initialize(dev2['db_path'], dev2['manifest'], DEV2_COUNT, source=DEV2_SOURCE, fingerprint=DEV2_FINGERPRINT)
        os.chmod(dev2['db_path'], 0o600)
    server = make_server('127.0.0.1', config.get('port', 8766), config['db_path'], config['access_key'],
                         {'https://jefflai108.github.io', 'http://localhost:4321', 'http://127.0.0.1:4321'},
                         dev2_db_path=dev2['db_path'] if dev2 else None)
    print(f'Taigi dev review listening on 127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
