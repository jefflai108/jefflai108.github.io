#!/usr/bin/env python3
"""Install the pinned public gallery images without storing image bytes in Git."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


DEFAULT_MANIFEST = Path(__file__).with_name("image-comparison-assets.json")


def relative_path(value):
    if not isinstance(value, str) or not value or any(char in value for char in ("\\", "\0", ":")):
        raise ValueError("Invalid relative asset path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("Asset paths must stay inside the destination")
    return Path(*path.parts)


def checked_bytes(data, expected, label):
    if len(data) != expected["bytes"]:
        raise ValueError(f"Size mismatch: {label}")
    if hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {label}")


def check_destination(root, path):
    """Reject existing links/files that would redirect or obstruct installation."""
    for current in (path, *path.parents):
        if current == root:
            break
        if current.is_symlink():
            raise ValueError(f"Destination contains a symlink: {current}")
        if current.exists():
            if current == path:
                if not current.is_file():
                    raise ValueError(f"Asset destination is not a regular file: {current}")
            elif not current.is_dir():
                raise ValueError(f"Asset parent is not a directory: {current}")


def install(archive_path, output_root, manifest_path=DEFAULT_MANIFEST):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    destination = relative_path(manifest["destination"])
    expected_files = manifest["files"]
    if not isinstance(expected_files, dict) or not expected_files:
        raise ValueError("Manifest must list the expected images")
    for name, expected in expected_files.items():
        relative_path(name)
        if not name.endswith(".jpg") or type(expected["bytes"]) is not int or expected["bytes"] <= 0:
            raise ValueError(f"Invalid image manifest entry: {name}")

    archive_size = manifest["archive_bytes"]
    if type(archive_size) is not int or archive_size <= 0:
        raise ValueError("Invalid archive size in manifest")
    with Path(archive_path).open("rb") as source:
        archive_data = source.read(archive_size + 1)
    checked_bytes(archive_data, {
        "bytes": archive_size, "sha256": manifest["archive_sha256"]
    }, "archive")

    # Validate the entire archive before creating directories or writing images.
    verified = {}
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ValueError("Archive contains duplicate filenames")
        for member in members:
            if member.orig_filename != member.filename:
                raise ValueError("Archive contains a noncanonical filename")
            relative_path(member.filename)
            file_type = stat.S_IFMT(member.external_attr >> 16)
            if member.is_dir() or file_type not in (0, stat.S_IFREG):
                raise ValueError("Archive must contain regular files only")
        if set(names) != set(expected_files):
            raise ValueError("Archive members do not exactly match the manifest")
        for member in members:
            expected = expected_files[member.filename]
            if member.file_size != expected["bytes"]:
                raise ValueError(f"ZIP member size mismatch: {member.filename}")
            with archive.open(member) as source:
                data = source.read(expected["bytes"] + 1)
            checked_bytes(data, expected, member.filename)
            verified[member.filename] = data

    root = Path(output_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Output root must be an existing directory")
    targets = {name: root / destination / relative_path(name) for name in verified}
    for target in targets.values():
        check_destination(root, target)
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(verified[name])
            temporary.chmod(0o644)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return len(verified)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output_root", type=Path, help="Existing dist/ or public/ directory")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        count = install(args.archive, args.output_root, args.manifest)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Image asset installation failed: {error}\n")
    print(f"Verified and installed {count} public gallery images.")


if __name__ == "__main__":
    main()
