#!/usr/bin/env python3
"""Verify and install the public TaiwanCorpus snapshot from its release namespace."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
import zipfile


DEFAULT_SOURCE = Path(__file__).with_name("taiwan-corpus-assets.json")
SOURCE = {"schema": "taiwan-corpus-public-source/v1", "repository": "jefflai108/jefflai108.github.io",
          "release_tag": "taiwan-corpus-public", "manifest_asset": "taiwan-corpus-manifest.json"}
MEMBERS = {"index.html", "app.js", "style.css", "favicon.svg", "data/tree.json"}
SOURCES = {"ptt", "dcard", "threads"}
MAX_MANIFEST = 64 * 1024
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_TREE = 256 * 1024 * 1024
MAX_ASSET = 2 * 1024 * 1024
ARCHIVE_NAME = re.compile(r"taiwan-corpus-public-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\.zip\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")


def json_object(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) \
            or set(value) - set(required) - set(optional):
        raise ValueError("Unexpected public manifest or index fields")


def number(value, *, maximum=1_000_000_000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid public count or size")
    return value


def string(value, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Invalid public string")
    return value


def asset_url(name):
    if name != SOURCE["manifest_asset"] and not ARCHIVE_NAME.fullmatch(name):
        raise ValueError("Asset name is outside the public snapshot namespace")
    return "https://github.com/" + SOURCE["repository"] + "/releases/download/" + SOURCE["release_tag"] + "/" + name


def load_source(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST or json_object(raw) != SOURCE:
        raise ValueError("Unexpected release repository, tag or manifest asset")


class ReleaseRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {
                "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"} \
                or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            raise ValueError("Unexpected release asset redirect")
        if parsed.hostname == "github.com" and parsed.path != urlsplit(request.full_url).path:
            raise ValueError("Release redirect changed the pinned repository, tag or asset")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def download(name, cap):
    url = asset_url(name)
    headers = {"User-Agent": "TaiwanCorpus-public-installer", "Accept-Encoding": "identity"}
    if name == SOURCE["manifest_asset"]:
        # Both pointer reads must observe the mutable asset afresh. The query is
        # generated here; the repository, release tag and asset path stay pinned.
        url += "?check=" + uuid.uuid4().hex
        headers["Cache-Control"] = "no-cache"
    request = Request(url, headers=headers)
    with build_opener(ReleaseRedirect()).open(request, timeout=60) as response:
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdigit() or int(length) > cap):
            raise ValueError("Release asset exceeds its size bound")
        data = response.read(cap + 1)
    if len(data) > cap:
        raise ValueError("Release asset exceeds its size bound")
    return data


def check_hash(data, size, digest):
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Release asset size or SHA-256 mismatch")


def validate_manifest(raw):
    if len(raw) > MAX_MANIFEST:
        raise ValueError("Public manifest is too large")
    value = json_object(raw)
    fields(value, {"schema", "destination", "archive_name", "asset_name", "archive_bytes", "archive_sha256", "files",
                   "generated_at", "content_mode", "total_posts", "total_replies", "source_counts", "taxonomy_version"},
           {"release_tag", "url", "repository"})
    if value["schema"] != "taiwan-corpus-public-export/v1" or value["destination"] != "taiwan-corpus" \
            or value["content_mode"] != "public-index":
        raise ValueError("Only the approved public index can be installed here")
    name = value["archive_name"]
    if not isinstance(name, str) or not ARCHIVE_NAME.fullmatch(name):
        raise ValueError("Snapshot ZIP must have an immutable versioned name")
    for key, expected in {"release_tag": SOURCE["release_tag"], "repository": SOURCE["repository"],
                          "asset_name": name, "url": asset_url(name)}.items():
        if key in value and value[key] != expected:
            raise ValueError("Manifest points outside the pinned release namespace")
    if not number(value["archive_bytes"], maximum=MAX_ARCHIVE) or not isinstance(value["archive_sha256"], str) \
            or not HASH.fullmatch(value["archive_sha256"]) \
            or not name.endswith("-" + value["archive_sha256"][:12] + ".zip"):
        raise ValueError("Invalid archive identity")
    if not isinstance(value["files"], dict) or set(value["files"]) != MEMBERS:
        raise ValueError("Public snapshot inventory must contain exactly five files")
    for name, info in value["files"].items():
        fields(info, {"bytes", "sha256"})
        if not number(info["bytes"], maximum=MAX_TREE if name == "data/tree.json" else MAX_ASSET) \
                or not isinstance(info["sha256"], str) or not HASH.fullmatch(info["sha256"]):
            raise ValueError("Invalid member size or digest")
    number(value["total_posts"])
    number(value["total_replies"])
    string(value["generated_at"], 100)
    string(value["taxonomy_version"], 100)
    return value


def source_url(value, source):
    if value is None:
        return
    string(value, 2048)
    patterns = {
        "ptt": r"https://www\.ptt\.cc/bbs/[A-Za-z0-9_-]{1,40}/M\.[0-9]{9,12}\.A\.[A-Fa-f0-9]{1,8}\.html",
        "dcard": r"https://www\.dcard\.tw/f/[A-Za-z0-9_-]{1,80}/p/[0-9]{1,30}(?:/b/[1-9][0-9]{0,9})?(?:\?cid=[A-Za-z0-9_-]{1,100})?",
        "threads": r"https://www\.threads\.com/@[a-z0-9._]{1,30}/post/[A-Za-z0-9_-]{1,64}",
    }
    if not re.fullmatch(patterns[source], value):
        raise ValueError("Unsafe or noncanonical source link")


def validate_tree(raw, manifest):
    tree = json_object(raw)
    fields(tree, {"schema", "mode", "generated_at", "taxonomy_version", "total_posts", "total_replies",
                  "source_counts", "topics", "leaves"})
    if tree["schema"] != "taiwan-corpus-discovery/v1" or tree["mode"] != "public-index":
        raise ValueError("Public tree mode or schema mismatch")
    for key in ("generated_at", "taxonomy_version", "total_posts", "total_replies", "source_counts"):
        if tree[key] != manifest[key]:
            raise ValueError("Manifest and public tree disagree")
    fields(tree["source_counts"], SOURCES)
    for counts in tree["source_counts"].values():
        fields(counts, {"posts", "replies"})
        number(counts["posts"])
        number(counts["replies"])
    if not isinstance(tree["topics"], list) or not isinstance(tree["leaves"], list):
        raise ValueError("Invalid public topic or leaf inventory")
    branches = {}
    for topic in tree["topics"]:
        fields(topic, {"id", "label", "label_en", "description", "children"})
        topic_id = string(topic["id"], 100)
        if topic_id in branches or not isinstance(topic["children"], list):
            raise ValueError("Invalid or duplicate public topic")
        branches[topic_id] = set()
        for key in ("label", "label_en", "description"):
            string(topic[key], 1000)
        for child in topic["children"]:
            fields(child, {"id", "label", "description", "coverage_target"})
            child_id = string(child["id"], 100)
            if child_id in branches[topic_id] or type(child["coverage_target"]) is not bool:
                raise ValueError("Invalid or duplicate public branch")
            branches[topic_id].add(child_id)
            string(child["label"], 1000)
            string(child["description"], 1000)
    counts = {source: {"posts": 0, "replies": 0} for source in SOURCES}
    identifiers = set()
    for leaf in tree["leaves"]:
        fields(leaf, {"id", "source", "community", "url", "published_at", "collected_at", "topic_id", "branch_id",
                      "reply_count", "engagement", "title", "assignment"})
        identifier = leaf["id"]
        if not isinstance(identifier, str) or not HASH.fullmatch(identifier) or identifier in identifiers \
                or leaf["source"] not in SOURCES or leaf["branch_id"] not in branches.get(leaf["topic_id"], set()):
            raise ValueError("Invalid, duplicate or unassigned public root")
        identifiers.add(identifier)
        string(leaf["title"], 160)
        string(leaf["community"], 200)
        for key in ("published_at", "collected_at"):
            if leaf[key] is not None:
                string(leaf[key], 100)
        fields(leaf["assignment"], {"method"})
        if leaf["assignment"]["method"] not in {"keyword", "community", "discovery_hint", "unclassified"}:
            raise ValueError("Invalid public assignment method")
        fields(leaf["engagement"], {"likes", "comments", "pushes", "boos"})
        for count in leaf["engagement"].values():
            if count is not None:
                number(count)
        source_url(leaf["url"], leaf["source"])
        counts[leaf["source"]]["posts"] += 1
        counts[leaf["source"]]["replies"] += number(leaf["reply_count"])
    if counts != tree["source_counts"] or len(identifiers) != number(tree["total_posts"]) \
            or sum(count["replies"] for count in counts.values()) != number(tree["total_replies"]):
        raise ValueError("Public root inventory and counts disagree")


def verify_archive(data, manifest):
    check_hash(data, manifest["archive_bytes"], manifest["archive_sha256"])
    verified = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) != len(MEMBERS) or {member.filename for member in members} != MEMBERS or archive.comment:
            raise ValueError("ZIP inventory does not match the public snapshot")
        for member in members:
            kind = stat.S_IFMT(member.external_attr >> 16)
            if member.orig_filename != member.filename or member.is_dir() or kind not in (0, stat.S_IFREG) \
                    or member.flag_bits & 1 or member.comment:
                raise ValueError("ZIP must contain only canonical regular files")
            expected = manifest["files"][member.filename]
            if member.file_size != expected["bytes"]:
                raise ValueError("ZIP member size mismatch")
            with archive.open(member) as stream:
                content = stream.read(expected["bytes"] + 1)
            check_hash(content, expected["bytes"], expected["sha256"])
            verified[member.filename] = content
    validate_tree(verified["data/tree.json"], manifest)
    return verified


def write_assets(verified, output_root, manifest):
    marker = {"schema": "taiwan-corpus-public-snapshot/v1", "archive_sha256": manifest["archive_sha256"],
              "asset_name": manifest["asset_name"], "generated_at": manifest["generated_at"],
              "total_posts": manifest["total_posts"]}
    contents = {**verified, "snapshot.json": (json.dumps(marker, separators=(",", ":")) + "\n").encode()}
    root = Path(output_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Output root must be an existing directory")
    root = root.resolve(strict=True)
    destination = root / "taiwan-corpus"
    for name in contents:
        path = destination / name
        for current in (path, *path.parents):
            if current == root:
                break
            if current.is_symlink() or current.exists() and (
                    not current.is_file() if current == path else not current.is_dir()):
                raise ValueError("Unsafe public asset destination")
    if destination.exists() and any(str(path.relative_to(destination)) not in set(contents) | {"data"}
                                    for path in destination.rglob("*")):
        raise ValueError("Destination contains unexpected files; refusing a mixed snapshot")
    for name, content in contents.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            temporary.chmod(0o644)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return len(contents)


def install(archive_path, output_root, manifest_path):
    with Path(manifest_path).open("rb") as stream:
        manifest = validate_manifest(stream.read(MAX_MANIFEST + 1))
    with Path(archive_path).open("rb") as stream:
        data = stream.read(manifest["archive_bytes"] + 1)
    return write_assets(verify_archive(data, manifest), output_root, manifest)


def install_release(output_root, source_path=DEFAULT_SOURCE):
    load_source(source_path)
    raw = download(SOURCE["manifest_asset"], MAX_MANIFEST)
    manifest = validate_manifest(raw)
    verified = verify_archive(download(manifest["archive_name"], manifest["archive_bytes"]), manifest)
    if download(SOURCE["manifest_asset"], MAX_MANIFEST) != raw:
        raise ValueError("Release manifest changed during verification; retry the build")
    return write_assets(verified, output_root, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path, help="Existing dist/ or public/ directory")
    parser.add_argument("--archive", type=Path, help="Offline ZIP; requires --manifest")
    parser.add_argument("--manifest", type=Path, help="Offline release manifest; requires --archive")
    args = parser.parse_args()
    if bool(args.archive) != bool(args.manifest):
        parser.error("--archive and --manifest must be supplied together")
    try:
        count = install(args.archive, args.output_root, args.manifest) if args.archive else install_release(args.output_root)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, zipfile.BadZipFile) as error:
        parser.exit(1, "TaiwanCorpus installation failed: " + str(error) + "\n")
    print(f"Verified and installed {count} public TaiwanCorpus snapshot files.")


if __name__ == "__main__":
    main()
