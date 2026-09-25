#!/usr/bin/env python3
"""Keep previously shared benchmark URLs working after the /line-v3/ move."""
import argparse
import html
import json
from pathlib import Path
import shutil
from urllib.parse import quote


def install(root):
    root = root.resolve(strict=True)
    source, legacy = root / "line-v3", root / "line-v2"
    if not (source / "index.html").is_file():
        raise ValueError("Build the LINE v3 site first")
    if legacy.exists():
        raise ValueError("Legacy output must be fresh")
    files = sorted(source.rglob("*"))
    if source.is_symlink() or any(path.is_symlink() for path in files):
        raise ValueError("Benchmark output must not contain symlinks")
    pages = assets = 0
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = legacy / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() != ".html":
            # JSON/download/image URLs cannot follow an HTML redirect. Keep
            # their exact bytes available under the already shared path too.
            shutil.copyfile(path, target)
            assets += 1
            continue
        url = "/line-v3/" + quote(relative.as_posix(), safe="/")
        if relative.as_posix() == "index.html":
            url = "/line-v3/"
        escaped = html.escape(url, quote=True)
        script_url = json.dumps(url).replace("<", "\\u003c")
        target.write_text(
            '<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="0;url={escaped}">'
            f'<link rel="canonical" href="{escaped}">'
            '<title>HeyMachi 比較頁已搬家</title>'
            f'<p>比較頁已搬到 <a href="{escaped}">LINE v3</a>。</p>'
            f'<script>location.replace({script_url}+location.search+location.hash);</script>'
            '</html>\n', encoding="utf-8")
        pages += 1
    return {"redirect_pages": pages, "preserved_downloads": assets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.output_root)))
