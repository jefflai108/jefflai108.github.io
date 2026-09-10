#!/usr/bin/env python3
"""Consistent daily snapshots of each authoritative review database."""
from datetime import datetime, timezone
from pathlib import Path
import json, os, sqlite3
root = Path.home() / 'Library/Application Support/Taigi Review'
config = json.loads((root / 'config.json').read_text())
folder = root / 'backups'
folder.mkdir(mode=0o700, exist_ok=True)
databases = {'annotations': config['db_path']}
if config.get('dev2'):
    databases['annotations-dev2'] = config['dev2']['db_path']
for name, path in databases.items():
    target = folder / (name + '-' + datetime.now(timezone.utc).strftime('%Y-%m-%d') + '.sqlite3')
    source = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)
    backup = sqlite3.connect(target)
    try:
        source.backup(backup)
    finally:
        backup.close(); source.close()
    os.chmod(target, 0o600)
print('Daily annotation snapshot saved')
