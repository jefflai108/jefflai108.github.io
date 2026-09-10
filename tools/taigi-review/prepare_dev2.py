#!/usr/bin/env python3
"""Materialize only the pinned private validation2 shards, outside the public site.

Requires huggingface_hub and pyarrow; authenticate with the usual HF login.
Usage: python prepare_dev2.py --out /private/path/validation2
The output must not already exist. No review database is modified.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import wave

from huggingface_hub import snapshot_download
import pyarrow.parquet as pq

REVISION = '7889df22aa03f5dd1805737d24c5d39729a60a54'
SHARDS = {
    'validation2-00000-of-00002.parquet': '44754f725b8f25fa017fdc98a687e6f479ba30af9b5a7f74165a5f4651658afe',
    'validation2-00001-of-00002.parquet': 'c9f5afe10d3b12fbe25fce90f24847a2ff2f76dc008db01e94a947f27c1b736d',
}


def prepare(out):
    out = Path(out).absolute()
    public = Path(__file__).resolve().parents[2] / 'public'
    if out.resolve().is_relative_to(public) or out.exists():
        raise ValueError('Choose a new private output directory outside public/')
    snapshot = Path(snapshot_download('jefflai108/streaming-taigi-asr', repo_type='dataset',
                    revision=REVISION, allow_patterns=['data/' + name for name in SHARDS]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.validation2-', dir=out.parent) as temp:
        stage = Path(temp) / 'dataset'
        stage.mkdir(mode=0o700)
        (stage / 'audio').mkdir(mode=0o700)
        rows, seen, seconds = [], set(), 0.0
        for filename, digest in SHARDS.items():
            shard = snapshot / 'data' / filename
            with shard.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise ValueError('HF shard fingerprint mismatch')
            for batch in pq.ParquetFile(shard).iter_batches(batch_size=64, columns=['id', 'text', 'audio', 'audio_sha256']):
                for row in batch.to_pylist():
                    rid = row['id']
                    if not re.fullmatch(r'taigi-dev2-[0-9]{8}', rid) or rid in seen:
                        raise ValueError('Invalid or duplicate validation2 ID')
                    seen.add(rid)
                    data = row['audio']['bytes']
                    if hashlib.sha256(data).hexdigest() != row['audio_sha256']:
                        raise ValueError('Audio fingerprint mismatch')
                    with wave.open(io.BytesIO(data)) as wav:
                        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                            raise ValueError('Unexpected audio format')
                        seconds += wav.getnframes() / wav.getframerate()
                    relative = f'audio/{rid}.wav'
                    (stage / relative).write_bytes(data)
                    rows.append({'id': rid, 'audio': relative, 'text': row['text']})
        if len(rows) != 5133:
            raise ValueError('Unexpected validation2 clip count')
        manifest = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode()
        (stage / 'manifest.jsonl').write_bytes(manifest)
        receipt = {'repo': 'jefflai108/streaming-taigi-asr', 'config': 'default', 'split': 'validation2',
                   'revision': REVISION, 'clips': len(rows), 'seconds': seconds,
                   'manifest_sha256': hashlib.sha256(manifest).hexdigest(), 'shards': SHARDS}
        (stage / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')
        stage.rename(out)
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    prepare(parser.parse_args().out)
