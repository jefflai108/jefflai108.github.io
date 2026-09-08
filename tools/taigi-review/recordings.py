"""Private user recordings, separate from the fixed HF dev corpus."""
import base64
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
import wave

FIELDS = 'id,title,annotation,status,duration,created_by,created_at,updated_by,updated_at,revision'
STATUSES = {'unreviewed', 'reviewed', 'flagged'}
ID_PATTERN = r'rec-[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}'
MAX_BODY = 20 * 1024 * 1024
MAX_AUDIO = 12 * 1024 * 1024
DECODERS = threading.BoundedSemaphore(2)

@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db: yield db
    finally: db.close()

def initialize(path):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS recordings (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, annotation TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('unreviewed','reviewed','flagged')),
          duration REAL NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_by TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
          upload_sha256 TEXT NOT NULL, mime TEXT NOT NULL, original_audio BLOB NOT NULL,
          audio_wav BLOB NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_recordings_created ON recordings(created_at DESC,id);
        CREATE TABLE IF NOT EXISTS recording_history (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          recording_id TEXT NOT NULL REFERENCES recordings(id), revision INTEGER NOT NULL,
          annotation TEXT NOT NULL, status TEXT NOT NULL, editor TEXT NOT NULL,
          saved_at TEXT NOT NULL, UNIQUE(recording_id,revision));
        ''')

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def normalize_audio(data):
    if not DECODERS.acquire(timeout=15): raise ValueError('Other recordings are being saved. Please retry in a moment.')
    try:
        with tempfile.TemporaryDirectory(prefix='taigi-recording-') as folder:
            source, target = Path(folder)/'input', Path(folder)/'audio.wav'
            source.write_bytes(data)
            result = subprocess.run(['/opt/homebrew/bin/ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,wav,ogg',
                '-i', str(source), '-map', '0:a:0', '-vn', '-t', '121', '-ac', '1', '-ar', '16000',
                '-c:a', 'pcm_s16le', '-threads', '1', str(target)], capture_output=True, timeout=45)
            if result.returncode or not target.exists(): raise ValueError('This recording could not be decoded. Please record another take.')
            with wave.open(str(target), 'rb') as wav: duration = wav.getnframes()/wav.getframerate()
            if not .1 <= duration <= 120.5: raise ValueError('Record between 0.1 seconds and 2 minutes per clip.')
            return target.read_bytes(), duration
    except subprocess.TimeoutExpired:
        raise ValueError('Processing took too long. Please retry with a shorter recording.')
    finally: DECODERS.release()

def create(path, payload):
    if not isinstance(payload,dict) or set(payload) != {'id','title','annotation','status','editor','mime','audio_base64'}:
        return 400, {'error':'Invalid recording fields'}
    rid, title, text, status, editor, mime, encoded = (payload[k] for k in ['id','title','annotation','status','editor','mime','audio_base64'])
    if not isinstance(rid,str) or not re.fullmatch(ID_PATTERN,rid): return 400, {'error':'Invalid recording ID'}
    if not isinstance(title,str) or len(title)>120 or not isinstance(text,str) or len(text)>10000: return 400, {'error':'Title or transcript is too long'}
    if not isinstance(status,str) or status not in STATUSES or not isinstance(editor,str) or not 1<=len(editor.strip())<=80: return 400, {'error':'Enter your name and a valid review status'}
    if not isinstance(mime,str) or len(mime)>100 or mime.split(';')[0].strip() not in {'audio/webm','audio/mp4','audio/ogg','audio/wav','audio/x-wav'}: return 400, {'error':'Unsupported audio format'}
    if not isinstance(encoded,str) or len(encoded)>MAX_AUDIO*4//3+4: return 413, {'error':'This recording is too large. Keep clips under 2 minutes.'}
    try: data = base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError): return 400, {'error':'Invalid audio data'}
    if not 32<=len(data)<=MAX_AUDIO: return 400, {'error':'The recording is empty or too large'}
    digest = hashlib.sha256(data).hexdigest()
    # Audio identity makes retries safe even if an upload response was lost.
    with connect(path) as db:
        row = db.execute(f'SELECT {FIELDS},upload_sha256 FROM recordings WHERE id=?',(rid,)).fetchone()
        if row:
            if row['upload_sha256'] != digest: return 409, {'error':'This recording ID already contains a different take. Start a new recording.'}
            return 200, {'recording':{k:row[k] for k in row.keys() if k!='upload_sha256'},'created':False}
    wav, duration = normalize_audio(data)
    timestamp = now()
    title = title.strip() or f'Taigi recording · {timestamp[:10]}'
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        inserted=db.execute('INSERT OR IGNORE INTO recordings VALUES(?,?,?,?,?,?,?,?,?,0,?,?,?,?)',
            (rid,title,text,status,duration,editor.strip(),timestamp,editor.strip(),timestamp,digest,mime,data,wav)).rowcount
        if inserted:
            db.execute('INSERT INTO recording_history(recording_id,revision,annotation,status,editor,saved_at) VALUES(?,0,?,?,?,?)',(rid,text,status,editor.strip(),timestamp))
        row=db.execute(f'SELECT {FIELDS},upload_sha256 FROM recordings WHERE id=?',(rid,)).fetchone()
        if row['upload_sha256']!=digest: return 409, {'error':'This recording ID already contains a different take'}
        result={k:row[k] for k in row.keys() if k!='upload_sha256'}
    return 201 if inserted else 200, {'recording':result,'created':bool(inserted)}

def save(path, rid, payload):
    if not isinstance(payload,dict) or set(payload)!={'annotation','status','revision','editor'}: return 400, {'error':'Invalid annotation fields'}
    text,status,revision,editor=(payload[k] for k in ['annotation','status','revision','editor'])
    if not isinstance(text,str) or len(text)>10000 or type(revision) is not int or revision<0 or not isinstance(status,str) or status not in STATUSES or not isinstance(editor,str) or not 1<=len(editor.strip())<=80:
        return 400, {'error':'Enter a valid transcript, status, revision, and name'}
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute(f'SELECT {FIELDS} FROM recordings WHERE id=?',(rid,)).fetchone()
        if not row: return 404, {'error':'Recording not found'}
        if row['revision']!=revision:
            if row['annotation']==text and row['status']==status: return 200, {'recording':dict(row)}
            return 409, {'error':'A collaborator saved a different transcript. Compare both versions.', 'recording':dict(row)}
        timestamp=now()
        db.execute('UPDATE recordings SET annotation=?,status=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=? AND revision=?',(text,status,editor.strip(),timestamp,rid,revision))
        db.execute('INSERT INTO recording_history(recording_id,revision,annotation,status,editor,saved_at) VALUES(?,?,?,?,?,?)',(rid,revision+1,text,status,editor.strip(),timestamp))
        result=dict(db.execute(f'SELECT {FIELDS} FROM recordings WHERE id=?',(rid,)).fetchone())
    return 200, {'recording':result}

def get(handler,path,query):
    with connect(handler.server.db_path) as db:
        if path in {'/api/recordings','/api/recordings/export'}:
            export=path.endswith('/export')
            offset=max(0,int(query.get('offset',['0'])[0])); q=query.get('q',[''])[0][:200] if not export else ''
            clause=' WHERE instr(title,?)>0 OR instr(annotation,?)>0 OR instr(created_by,?)>0' if q else ''
            args=[q,q,q] if q else []
            total=db.execute('SELECT count(*) FROM recordings'+clause,args).fetchone()[0]
            suffix='' if export else ' LIMIT 30 OFFSET ?'
            rows=db.execute(f'SELECT {FIELDS} FROM recordings'+clause+' ORDER BY created_at DESC,id'+suffix,args+([] if export else [offset])).fetchall()
            return handler.respond(200, {'recordings':[dict(r) for r in rows],'total':total,'offset':offset,'source':'user_recordings'})
        match=re.fullmatch(r'/api/recordings/('+ID_PATTERN+r')(/audio|/history)?',path)
        if not match: return handler.respond(404, {'error':'Recording not found'})
        if match[2]=='/audio':
            row=db.execute('SELECT audio_wav FROM recordings WHERE id=?',(match[1],)).fetchone()
            if not row: return handler.respond(404, {'error':'Recording not found'})
            return send_audio(handler,row[0])
        row=db.execute(f'SELECT {FIELDS} FROM recordings WHERE id=?',(match[1],)).fetchone()
        if not row: return handler.respond(404, {'error':'Recording not found'})
        if match[2]=='/history':
            rows=db.execute('SELECT revision,annotation,status,editor,saved_at FROM recording_history WHERE recording_id=? ORDER BY revision DESC LIMIT 100',(match[1],)).fetchall()
            return handler.respond(200, {'history':[dict(r) for r in rows]})
        return handler.respond(200, {'recording':dict(row)})

def send_audio(handler,data):
    size=len(data); start=0; end=size-1; code=200
    value=handler.headers.get('Range')
    if value:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
        if not match or not any(match.groups()): return handler.respond(416, {'error':'Invalid byte range'})
        if match[1]: start=int(match[1]); end=min(int(match[2]),size-1) if match[2] else size-1
        else: start=max(0,size-int(match[2]))
        if start>end or start>=size: return handler.respond(416, {'error':'Range unavailable'})
        code=206
    handler.send_response(code); handler.cors()
    handler.send_header('Content-Type','audio/wav');handler.send_header('Cache-Control','private, max-age=86400')
    handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Length',str(end-start+1))
    if code==206: handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers();handler.wfile.write(data[start:end+1])
