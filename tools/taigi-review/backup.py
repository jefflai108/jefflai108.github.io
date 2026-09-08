#!/usr/bin/env python3
"""Consistent daily snapshots of the single authoritative review DB."""
from datetime import datetime, timezone
from pathlib import Path
import json, os, sqlite3
root = Path.home() / 'Library/Application Support/Taigi Review'
config = json.loads((root / 'config.json').read_text())
folder = root / 'backups'
folder.mkdir(mode=0o700, exist_ok=True)
target = folder / ('annotations-' + datetime.now(timezone.utc).strftime('%Y-%m-%d') + '.sqlite3')
source = sqlite3.connect(config['db_path'])
backup = sqlite3.connect(target)
try:
    source.backup(backup)
finally:
    backup.close(); source.close()
os.chmod(target, 0o600)
print('Daily annotation snapshot saved')
