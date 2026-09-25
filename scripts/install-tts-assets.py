#!/usr/bin/env python3
"""Verify the pinned TTS archive and all members before installing audio."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


def install(archive, destination, manifest):
    if manifest.get('version') != 1:
        raise ValueError('Unsupported manifest version')
    if archive.stat().st_size != manifest['archiveBytes']:
        raise ValueError('Archive size mismatch')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archiveSha256']:
        raise ValueError('Archive SHA-256 mismatch')
    expected = {}
    for entry in manifest['files']:
        path = entry['path']
        pure = PurePosixPath(path)
        if pure.is_absolute() or '..' in pure.parts or '\\' in path or not re.fullmatch(r'tts/audio/v3-benchmark-[0-9-]+/eleven_v3(?:_conversational)?/[a-z0-9-]+/p[0-9]{2}\.mp3', path):
            raise ValueError('Unsafe or unexpected audio path: ' + path)
        if path in expected:
            raise ValueError('Duplicate manifest member')
        if not isinstance(entry['bytes'], int) or not 0 < entry['bytes'] <= 10 * 1024 * 1024:
            raise ValueError('Invalid member size')
        if not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise ValueError('Invalid member checksum')
        expected[path] = entry
    if not expected or sum(e['bytes'] for e in expected.values()) > 512 * 1024 * 1024:
        raise ValueError('Invalid total audio size')
    root = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Archive inventory mismatch')
        for name in names:
            info = source.getinfo(name)
            entry = expected[name]
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Symlinks are not allowed')
            if info.file_size != entry['bytes'] or hashlib.sha256(source.read(name)).hexdigest() != entry['sha256']:
                raise ValueError('Audio size or SHA-256 mismatch: ' + name)
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError('Destination escapes output directory')
        # The complete archive is validated before any audio is written.
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(name))
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('tts-benchmark-assets.json'))
    args = parser.parse_args()
    count = install(args.archive, args.destination, json.loads(args.manifest.read_text()))
    print(f'Installed {count} verified TTS samples into {args.destination}')


if __name__ == '__main__':
    main()
