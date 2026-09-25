#!/usr/bin/env python3
"""Generate a resumable, sequential ElevenLabs streaming benchmark.

Reads ELEVENLABS_API_KEY from the environment; writes private raw results to
--output. Uses the same corpus and settings for every voice/model pair. Failed
attempts and warm-ups remain in the log and never enter successful timing stats.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import os
import random
import re
import shutil
import subprocess
import time


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, default=Path(__file__).resolve().parents[1] / 'src/data/tts-corpus.json')
    parser.add_argument('--warmup-only', action='store_true')
    args = parser.parse_args()
    key = os.environ['ELEVENLABS_API_KEY'].strip()
    corpus_bytes = args.corpus.read_bytes()
    corpus = json.loads(corpus_bytes)
    assert len(corpus['paragraphs']) == 20
    assert len({p['id'] for p in corpus['paragraphs']}) == 20
    assert len({v['id'] for v in corpus['voices']}) == 7
    for paragraph in corpus['paragraphs']:
        assert len(re.findall('[。！？]', paragraph['text'])) == paragraph['sentences']
        assert 1 <= paragraph['sentences'] <= 3
        assert '[' not in paragraph['text'] and ']' not in paragraph['text']
    args.output.mkdir(parents=True, exist_ok=True)
    corpus_hash = hashlib.sha256(corpus_bytes).hexdigest()
    meta_path = args.output / 'run.json'
    if meta_path.exists():
        assert json.loads(meta_path.read_text())['corpus_sha256'] == corpus_hash, 'Corpus changed; choose a new output directory'
    else:
        meta_path.write_text(json.dumps({'started_at': stamp(), 'corpus_sha256': corpus_hash, 'endpoint': 'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream', 'transport': 'HTTP/1.1 over TLS, persistent connection when available', 'concurrency': 1, 'time_to_first_byte': 'Request start to first non-empty audio response-body bytes received. Not first audible playback.', 'total_time': 'Request start to the complete response body. Local file writing and MP3 decoding are excluded.', 'warmups': 'One unscored short warm-up per voice/model pair before the measured calls.', 'order': 'Deterministic randomized paragraph blocks; randomized voice/model order inside each block.'}, indent=2) + '\n')
        (args.output / 'corpus.json').write_bytes(corpus_bytes)
    log = args.output / 'attempts.jsonl'
    previous = [json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.exists() else []
    done = {r['key'] for r in previous if r.get('ok')}
    conn = http.client.HTTPSConnection('api.elevenlabs.io', timeout=60)
    ffprobe = shutil.which('ffprobe')
    ffmpeg = shutil.which('ffmpeg')
    assert ffprobe and ffmpeg, 'ffprobe and ffmpeg are required to verify the audio'

    def synthesize(voice, model, paragraph, warmup=False):
        job_key = '/'.join([model['id'], voice['slug'], paragraph['id']])
        if job_key in done:
            return
        destination = args.output / ('warmups' if warmup else 'audio') / model['id'] / voice['slug'] / (paragraph['id'] + '.mp3')
        for attempt in range(1, 3):
            result = {'key': job_key, 'voice_id': voice['id'], 'voice_slug': voice['slug'], 'voice_label': voice['label'], 'model_id': model['id'], 'paragraph_id': paragraph['id'], 'characters': len(paragraph['text']), 'warmup': warmup, 'attempt': attempt, 'started_at': stamp(), 'connection_reused': conn.sock is not None}
            payload = json.dumps({'text': paragraph['text'], 'model_id': model['id'], 'voice_settings': corpus['settings'], 'seed': corpus['requestSeed'], 'apply_text_normalization': 'auto'}, ensure_ascii=False).encode()
            started = time.perf_counter_ns()
            try:
                conn.request('POST', '/v1/text-to-speech/' + voice['id'] + '/stream?output_format=' + corpus['outputFormat'], body=payload, headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg', 'Accept-Encoding': 'identity'})
                response = conn.getresponse()
                result.update({'http_status': response.status, 'headers_ms': (time.perf_counter_ns() - started) / 1e6, 'content_type': response.getheader('Content-Type'), 'request_id': response.getheader('request-id') or response.getheader('x-request-id'), 'character_cost': response.getheader('character-cost')})
                if response.status != 200:
                    error_body = response.read().decode(errors='replace').replace(key, '[redacted]')
                    result['error'] = error_body[:2000]
                    raise RuntimeError('HTTP ' + str(response.status))
                chunks = []
                first_byte = None
                while True:
                    chunk = response.read1(65536)
                    received = time.perf_counter_ns()
                    if not chunk:
                        break
                    if first_byte is None:
                        first_byte = received
                        result['first_chunk_bytes'] = len(chunk)
                    chunks.append(chunk)
                finished = time.perf_counter_ns()
                response.close()
                audio = b''.join(chunks)
                assert first_byte is not None and audio and 'audio' in result['content_type'], 'Missing audio payload'
                result.update({'ttfb_ms': round((first_byte - started) / 1e6, 3), 'total_ms': round((finished - started) / 1e6, 3), 'chunks': len(chunks), 'bytes': len(audio), 'sha256': hashlib.sha256(audio).hexdigest()})
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(audio)
                probe = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,sample_rate,channels', '-of', 'json', str(destination)], capture_output=True, text=True, timeout=15, check=True)
                info = json.loads(probe.stdout)
                assert any(s.get('codec_name') == 'mp3' for s in info.get('streams', [])), 'No MP3 audio stream'
                result['duration_seconds'] = float(info['format']['duration'])
                assert result['duration_seconds'] > 0
                subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-i', str(destination), '-f', 'null', '-'], capture_output=True, timeout=20, check=True)
                result.update({'ok': True, 'audio_file': str(destination)})
            except Exception as exc:
                result['ok'] = False
                result.setdefault('error', (type(exc).__name__ + ': ' + str(exc)).replace(key, '[redacted]')[:2000])
                conn.close()
            with log.open('a') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
                stream.flush()
            if result['ok']:
                done.add(job_key)
                scored = sum(not k.endswith('/warmup') for k in done)
                print(json.dumps({'completed': scored, 'warmup': warmup, 'voice': voice['label'], 'model': model['id'], 'paragraph': paragraph['id'], 'ttfb_ms': result['ttfb_ms'], 'total_ms': result['total_ms'], 'duration_seconds': result['duration_seconds']}, ensure_ascii=False), flush=True)
                return
            print(json.dumps({'failed': job_key, 'attempt': attempt, 'error': result['error']}, ensure_ascii=False), flush=True)
            if result.get('http_status') in [400, 401, 402, 403, 404, 422]:
                raise RuntimeError('Request rejected; inspect attempts.jsonl before continuing')
            if attempt < 2:
                time.sleep(2)
        raise RuntimeError('Two failed attempts; partial results preserved')

    rng = random.Random(corpus['scheduleSeed'])
    pairs = [(voice, model) for voice in corpus['voices'] for model in corpus['models']]
    warmups = list(pairs)
    rng.shuffle(warmups)
    for voice, model in warmups:
        synthesize(voice, model, {'id': 'warmup', 'text': corpus['warmupText']}, warmup=True)
    if not args.warmup_only:
        paragraphs = list(corpus['paragraphs'])
        rng.shuffle(paragraphs)
        for paragraph in paragraphs:
            block = list(pairs)
            rng.shuffle(block)
            for voice, model in block:
                synthesize(voice, model, paragraph)
    conn.close()
    print(json.dumps({'finished_at': stamp(), 'scored_completed': sum(not k.endswith('/warmup') for k in done), 'output': str(args.output)}), flush=True)


if __name__ == '__main__':
    main()
