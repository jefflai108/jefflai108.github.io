"""Validate public bridge copy with the study's frozen publication.py; no writes.

Read allowlisted public JSON from stdin (or --public), and derive known secrets
only from the two supplied raw result files. No credential files are accessed.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

GUARD = "source/serve/line_agent_v2/evals/line_architecture/publication.py"
JUDGE = "source/serve/line_agent_v3/evals/natural_bridges/judge.py"


class CheckError(ValueError):
    pass


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)


def identity(item):
    return f"{item['case_id']}.{item['account']}.r{item['repeat']}.t{item['turn_index']}"


def check(results_path, quality_path, public):
    results_raw, quality_raw = results_path.read_bytes(), quality_path.read_bytes()
    study, quality = json.loads(results_raw), json.loads(quality_raw)
    root = results_path.resolve().parent
    plan_raw = (root / "plan.json").read_bytes()
    plan = json.loads(plan_raw)
    samples_raw = (root / "quality-samples.json").read_bytes()
    judge_raw = (root / JUDGE).read_bytes()
    expected = {"source_ref": plan["source_ref"], "results_sha256": digest(results_raw),
        "plan_sha256": digest(plan_raw), "quality_samples_sha256": digest(samples_raw),
        "judge_sha256": digest(judge_raw)}
    if study["metadata"]["source_ref"] != expected["source_ref"] \
            or any(quality.get(key) != value for key, value in expected.items()) \
            or any(public.get("quality", {}).get(key) != value for key, value in expected.items()) \
            or public.get("source_ref") != expected["source_ref"]:
        raise CheckError("study_quality_binding_mismatch")
    sample_ids = [identity(item) for item in json.loads(samples_raw)]
    judged_ids = [row["id"] for row in quality["results"]]
    if len(set(sample_ids)) != len(sample_ids) or len(set(judged_ids)) != len(judged_ids) \
            or set(sample_ids) != set(judged_ids):
        raise CheckError("quality_sample_ids_mismatch")
    if any(any(row.get(key) != value for key, value in expected.items()) for row in quality["results"]):
        raise CheckError("judgment_binding_mismatch")
    guard_path = root / GUARD
    guard_raw = guard_path.read_bytes()
    if plan["files"].get(GUARD) != digest(guard_raw) or plan["files"].get(JUDGE) != digest(judge_raw):
        raise CheckError("frozen_publication_source_mismatch")
    spec = importlib.util.spec_from_file_location("bridge_frozen_publication", guard_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    visible = list(strings(public))
    adapter = {"metadata": {"variants": ["natural_bridges"]}, "cases": [
        {"natural_bridges": {"messages": [{"texts": visible}]}}]}
    secrets = module._secret_values(study) | module._secret_values(quality)
    try:
        module.sanitize_results(adapter, sensitive_values=secrets)
    except module.PublicationError as error:
        raise CheckError("visible_text_requires_review") from error
    # Never use a sanitized return value as a replacement for measured copy.
    return {"status": "passed", "public_strings_checked": len(visible),
        "publication_guard_sha256": digest(guard_raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    args = parser.parse_args()
    try:
        public = json.loads(args.public.read_text()) if args.public else json.load(sys.stdin)
        result = check(args.results, args.quality, public)
    except CheckError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Do not echo supplied data, private filenames, or exception payloads.
        print("publication_inputs_or_guard_invalid", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
