#!/usr/bin/env python3
"""Publishable summaries and a pinned audio archive from a completed local run."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'tts/audio/v3-benchmark-2026-09-25'
TAG = 'tts-v3-benchmark-2026-09-25'


def percentile(values, q):
    values = sorted(values)
    index = (len(values) - 1) * q
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (index - lo), 3)


def summary(rows):
    return {
        'count': len(rows),
        'p50TtfbMs': percentile([r['ttfb_ms'] for r in rows], 0.5),
        'p95TtfbMs': percentile([r['ttfb_ms'] for r in rows], 0.95),
        'p50TotalMs': percentile([r['total_ms'] for r in rows], 0.5),
        'p95TotalMs': percentile([r['total_ms'] for r in rows], 0.95),
        'medianAudioSeconds': round(statistics.median(r['duration_seconds'] for r in rows), 3),
        'medianRtf': round(statistics.median(r['total_ms'] / 1000 / r['duration_seconds'] for r in rows), 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    corpus = json.loads((args.run / 'corpus.json').read_text())
    run = json.loads((args.run / 'run.json').read_text())
    assert hashlib.sha256((args.run / 'corpus.json').read_bytes()).hexdigest() == run['corpus_sha256']
    assert (ROOT / 'src/data/tts-corpus.json').read_bytes() == (args.run / 'corpus.json').read_bytes()
    attempts = [json.loads(line) for line in (args.run / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    measured = [r for r in attempts if not r['warmup'] and r['ok']]
    expected = {(m['id'], v['id'], p['id']) for m in corpus['models'] for v in corpus['voices'] for p in corpus['paragraphs']}
    assert {(r['model_id'], r['voice_id'], r['paragraph_id']) for r in measured} == expected, 'Incomplete benchmark'
    assert len(measured) == len(expected) == 280, 'Duplicate or missing successful measurements'
    warmups = [r for r in attempts if r['warmup'] and r['ok']]
    assert len(warmups) == 14
    records = []
    members = []
    archive = args.run / (TAG + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for row in sorted(measured, key=lambda r: r['key']):
            source = Path(row['audio_file'])
            payload = source.read_bytes()
            assert hashlib.sha256(payload).hexdigest() == row['sha256']
            assert len(payload) == row['bytes']
            member = PREFIX + '/' + row['model_id'] + '/' + row['voice_slug'] + '/' + row['paragraph_id'] + '.mp3'
            target.writestr(member, payload)
            members.append({'path': member, 'bytes': len(payload), 'sha256': row['sha256']})
            records.append({'modelId': row['model_id'], 'voiceId': row['voice_id'], 'paragraphId': row['paragraph_id'], 'audioPath': '/' + member, 'durationSeconds': row['duration_seconds'], 'ttfbMs': row['ttfb_ms'], 'totalMs': row['total_ms'], 'bytes': row['bytes'], 'sha256': row['sha256'], 'connectionReused': row['connection_reused']})
    by_voice = {v['id']: {m['id']: summary([r for r in measured if r['voice_id'] == v['id'] and r['model_id'] == m['id']]) for m in corpus['models']} for v in corpus['voices']}
    by_model = {m['id']: summary([r for r in measured if r['model_id'] == m['id']]) for m in corpus['models']}
    result = {
        'schemaVersion': 2,
        'generatedOn': '2026-09-25',
        'defaultModelId': corpus['defaultModelId'],
        'models': corpus['models'],
        'voices': corpus['voices'],
        'paragraphs': corpus['paragraphs'],
        'settings': corpus['settings'],
        'seed': corpus['requestSeed'],
        'method': {
            'endpoint': run['endpoint'], 'transport': run['transport'],
            'outputFormat': corpus['outputFormat'], 'concurrency': 1,
            'scoredRequests': len(measured), 'warmupRequests': len(warmups),
            'failedAttempts': sum(not r['ok'] for r in attempts),
            'requestsWithReusedConnection': sum(r['connection_reused'] for r in measured),
            'scheduleSeed': corpus['scheduleSeed'],
            'percentileMethod': 'Linear interpolation at (n - 1) × percentile.',
            'inputCharacters': sum(len(p['text']) for p in corpus['paragraphs']),
            'minParagraphCharacters': min(len(p['text']) for p in corpus['paragraphs']),
            'maxParagraphCharacters': max(len(p['text']) for p in corpus['paragraphs']),
            'startedAt': measured[0]['started_at'], 'lastRequestStartedAt': measured[-1]['started_at'],
            'timeToFirstByte': run['time_to_first_byte'], 'totalTime': run['total_time'],
            'order': run['order'], 'warmups': run['warmups'],
        },
        'byVoice': by_voice,
        'byModel': by_model,
        'records': records,
    }
    (ROOT / 'src/data/tts-benchmark.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    public_data = ROOT / 'public/tts/data'
    public_data.mkdir(parents=True, exist_ok=True)
    (public_data / 'v3-benchmark.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    paragraph_by_id = {p['id']: p for p in corpus['paragraphs']}
    voices_by_id = {v['id']: v for v in corpus['voices']}
    fields = ['model_id', 'voice', 'voice_id', 'paragraph_id', 'text', 'ttfb_ms', 'total_ms', 'audio_seconds', 'connection_reused', 'audio_url']
    with (public_data / 'v3-benchmark.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({'model_id': row['modelId'], 'voice': voices_by_id[row['voiceId']]['label'], 'voice_id': row['voiceId'], 'paragraph_id': row['paragraphId'], 'text': paragraph_by_id[row['paragraphId']]['text'], 'ttfb_ms': row['ttfbMs'], 'total_ms': row['totalMs'], 'audio_seconds': row['durationSeconds'], 'connection_reused': row['connectionReused'], 'audio_url': 'https://jefflai108.github.io' + row['audioPath']})
    manifest = {'version': 1, 'releaseTag': TAG, 'archiveName': archive.name, 'archiveBytes': archive.stat().st_size, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': members}
    (ROOT / 'scripts/tts-benchmark-assets.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'archive': str(archive), 'archive_bytes': archive.stat().st_size, 'records': len(records), 'by_model': by_model, 'failed_attempts': result['method']['failedAttempts'], 'reused_connections': result['method']['requestsWithReusedConnection']}, indent=2))


if __name__ == '__main__':
    main()
