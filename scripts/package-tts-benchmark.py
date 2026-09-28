#!/usr/bin/env python3
"""Publishable summaries and a pinned audio archive from a completed local run."""
import argparse
import csv
from datetime import date as calendar_date
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]


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
    parser.add_argument('--language', choices=['zh-TW', 'en', 'en-US'], default='zh-TW')
    parser.add_argument('--style', choices=['emotion', 'vocal'], help='Mandarin tagged style run')
    parser.add_argument('--family', choices=['v3', 'v4'], default='v3')
    parser.add_argument('--pilot', choices=['microphone'], help='One-passage custom-tag pilot')
    parser.add_argument('--date', help='Immutable release date (YYYY-MM-DD)')
    args = parser.parse_args()
    assert not args.style or args.language == 'zh-TW', 'Style runs are Mandarin only'
    suffix = {'zh-TW': '', 'en': '-en', 'en-US': '-en-us'}[args.language]
    if args.style:
        suffix = '-zh-' + args.style
    date = args.date or ('2026-09-28' if args.family == 'v4' or args.pilot else '2026-09-25')
    calendar_date.fromisoformat(date)
    data_suffix = ('-v4' if args.family == 'v4' else '') + suffix
    download_name = args.family + '-benchmark' + suffix
    if args.pilot:
        assert not args.style and args.language == 'zh-TW'
        data_suffix = '-microphone'
        download_name = 'microphone-pilot'
    tag = 'tts-' + download_name + '-' + date
    prefix = 'tts/audio/' + download_name + '-' + date
    corpus = json.loads((args.run / 'corpus.json').read_text())
    if args.pilot:
        assert corpus['audioTags'] == ['[speaking into the microphone]']
        assert [p['id'] for p in corpus['paragraphs']] == ['p01']
        assert [m['id'] for m in corpus['models']] == ['eleven_v3', 'eleven_v4', 'eleven_v4_turbo']
        source = json.loads((ROOT / 'src/data/tts-corpus.json').read_text())
        assert corpus['voices'] == source['voices']
        assert corpus['paragraphs'][0]['spokenText'] == source['paragraphs'][0]['text']
        assert corpus['paragraphs'][0]['text'] == corpus['audioTags'][0] + ' ' + source['paragraphs'][0]['text']
    if args.style:
        assert corpus['audioTagCategory'] == args.style
        expected_models = ['eleven_v4', 'eleven_v4_turbo'] if args.family == 'v4' else ['eleven_v3']
        assert [m['id'] for m in corpus['models']] == expected_models
        assert all(len(p['audioTags']) == 1 for p in corpus['paragraphs'])
    if args.family == 'v4' and not args.pilot:
        source = json.loads((ROOT / ('src/data/tts-corpus' + suffix + '.json')).read_text())
        original = {p['id']: p for p in source['paragraphs']}
        assert all(p == original[p['id']] for p in corpus['paragraphs']), 'V4 must use the exact original passages and tags'
        assert corpus['voices'] == source['voices'], 'Voice comparison must use the same voices'
        assert corpus['requestSeed'] == source['requestSeed']
        assert corpus['outputFormat'] == source['outputFormat']
    run = json.loads((args.run / 'run.json').read_text())
    assert hashlib.sha256((args.run / 'corpus.json').read_bytes()).hexdigest() == run['corpus_sha256']
    assert (ROOT / ('src/data/tts-corpus' + data_suffix + '.json')).read_bytes() == (args.run / 'corpus.json').read_bytes()
    attempts = [json.loads(line) for line in (args.run / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    measured = [r for r in attempts if not r['warmup'] and r['ok']]
    expected = {(m['id'], v['id'], p['id']) for m in corpus['models'] for v in corpus['voices'] for p in corpus['paragraphs']}
    assert {(r['model_id'], r['voice_id'], r['paragraph_id']) for r in measured} == expected, 'Incomplete benchmark'
    assert len(measured) == len(expected), 'Duplicate or missing successful measurements'
    warmups = [r for r in attempts if r['warmup'] and r['ok']]
    assert len(warmups) == len(corpus['voices']) * len(corpus['models'])
    records = []
    members = []
    archive = args.run / (tag + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for row in sorted(measured, key=lambda r: r['key']):
            source = Path(row['audio_file'])
            payload = source.read_bytes()
            assert hashlib.sha256(payload).hexdigest() == row['sha256']
            assert len(payload) == row['bytes']
            member = prefix + '/' + row['model_id'] + '/' + row['voice_slug'] + '/' + row['paragraph_id'] + '.mp3'
            target.writestr(member, payload)
            members.append({'path': member, 'bytes': len(payload), 'sha256': row['sha256']})
            records.append({'modelId': row['model_id'], 'voiceId': row['voice_id'], 'paragraphId': row['paragraph_id'], 'audioPath': '/' + member, 'durationSeconds': row['duration_seconds'], 'ttfbMs': row['ttfb_ms'], 'totalMs': row['total_ms'], 'bytes': row['bytes'], 'sha256': row['sha256'], 'connectionReused': row['connection_reused']})
    by_voice = {v['id']: {m['id']: summary([r for r in measured if r['voice_id'] == v['id'] and r['model_id'] == m['id']]) for m in corpus['models']} for v in corpus['voices']}
    by_model = {m['id']: summary([r for r in measured if r['model_id'] == m['id']]) for m in corpus['models']}
    result = {
        'schemaVersion': 2,
        'generatedOn': date,
        'defaultModelId': corpus['defaultModelId'],
        'models': corpus['models'],
        'voices': corpus['voices'],
        'paragraphs': corpus['paragraphs'],
        'settings': corpus['settings'],
        'seed': corpus['requestSeed'],
        'method': {
            'endpoint': run['endpoint'], 'transport': run['transport'],
            'outputFormat': corpus['outputFormat'], 'concurrency': 1,
            'audioTags': sorted({tag for p in corpus['paragraphs'] for tag in p.get('audioTags', corpus.get('audioTags', []))}),
            'audioTagCategory': corpus.get('audioTagCategory'),
            'tagsVaryByPassage': any('audioTags' in p for p in corpus['paragraphs']),
            'warmupAudioTags': corpus.get('warmupAudioTags', corpus.get('audioTags', [])),
            'tagPlacement': 'Prefix each passage and warm-up' if corpus.get('audioTags') or corpus.get('audioTagCategory') else 'None',
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
    (ROOT / ('src/data/tts-benchmark' + data_suffix + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    public_data = ROOT / 'public/tts/data'
    public_data.mkdir(parents=True, exist_ok=True)
    (public_data / (download_name + '.json')).write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    paragraph_by_id = {p['id']: p for p in corpus['paragraphs']}
    voices_by_id = {v['id']: v for v in corpus['voices']}
    fields = ['model_id', 'voice', 'voice_id', 'paragraph_id', 'text', 'ttfb_ms', 'total_ms', 'audio_seconds', 'connection_reused', 'audio_url']
    with (public_data / (download_name + '.csv')).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in records:
            writer.writerow({'model_id': row['modelId'], 'voice': voices_by_id[row['voiceId']]['label'], 'voice_id': row['voiceId'], 'paragraph_id': row['paragraphId'], 'text': paragraph_by_id[row['paragraphId']]['text'], 'ttfb_ms': row['ttfbMs'], 'total_ms': row['totalMs'], 'audio_seconds': row['durationSeconds'], 'connection_reused': row['connectionReused'], 'audio_url': 'https://jefflai108.github.io' + row['audioPath']})
    manifest = {'version': 1, 'releaseTag': tag, 'archiveName': archive.name, 'archiveBytes': archive.stat().st_size, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': members}
    (ROOT / ('scripts/tts-benchmark' + data_suffix + '-assets.json')).write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'archive': str(archive), 'archive_bytes': archive.stat().st_size, 'records': len(records), 'by_model': by_model, 'failed_attempts': result['method']['failedAttempts'], 'reused_connections': result['method']['requestsWithReusedConnection']}, indent=2))


if __name__ == '__main__':
    main()
