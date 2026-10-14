"""Public semantic projection of the separately frozen native owed diagnostic."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ARMS = ("engine_medium", "engine_high", "engine_sol_low")
ACCOUNTS = ("primary", "secondary")
FIELDS = ("answered", "no_rejection", "honest", "grounded")
PROOF_FIELDS = ("original_source_ref", "export_code_ref", "original_plan_sha256", "export_code_sha256",
    "rubric_sha256", "judge_sha256", "packets_sha256", "controls_sha256", "mapping_sha256",
    "binding_sha256", "native_receipts_sha256", "native_source_files_sha256", "judge_attempt_files_sha256",
    "retained_quality_sha256")

# Invoke the original frozen CLI. Its only write is intercepted in memory;
# reproduce its retained quality before exposing a deliberately small view.
REPRODUCE = r'''
import contextlib, hashlib, importlib.util, io, json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'source/engine'))
spec = importlib.util.spec_from_file_location('frozen_owed_diagnostic', root / 'harness/owed_probe_judge.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
retained = json.loads((root / 'quality.private.json').read_text())
written = []
def capture(path, value, **kwargs):
    if Path(path).resolve() != root / 'quality.private.json':
        raise ValueError('unexpected_diagnostic_write')
    written.append(value)
module.write = capture
sys.argv = [str(root / 'harness/owed_probe_judge.py'), 'summary', '--out', str(root)]
with contextlib.redirect_stdout(io.StringIO()):
    module.main()
if len(written) != 1 or written[0] != retained:
    raise ValueError('diagnostic_retained_quality_changed')
binding, packets, controls, mapping = module.verify(root)
plan = json.loads((root / 'inputs/plan.private.json').read_text())
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
native = []
for packet in packets:
    item = mapping[packet['packet_id']]
    row = json.loads((root / 'inputs/receipts' / (item['slot'] + '.json')).read_text())
    native.append({'arm': item['arm'], 'account': item['account'],
        'assessment': module._modules()[1].assess(row,
            plan['configurations'][item['arm']], item['account'])})
attempt_files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for directory in ('results', 'controls')
    for path in sorted((root / 'judge/foreground' / directory).glob('*.json'))}
proof = {key: binding[key] for key in ('original_source_ref', 'export_code_ref',
    'original_plan_sha256', 'export_code_sha256', 'rubric_sha256', 'judge_sha256',
    'packets_sha256', 'controls_sha256', 'mapping_sha256')}
proof.update(binding_sha256=module.sha(binding),
    native_receipts_sha256=digest(binding['original_receipt_files_sha256']),
    native_source_files_sha256=digest(binding['source_files']),
    judge_attempt_files_sha256=digest(attempt_files),
    retained_quality_sha256=hashlib.sha256((root / 'quality.private.json').read_bytes()).hexdigest())
print(json.dumps({'quality': retained, 'proof': proof, 'native': native, 'configurations': plan['configurations']}, ensure_ascii=False))
'''


def project(snapshot):
    """No packet IDs, raw prompts, candidate prose, private reasons or thoughts."""
    quality, proof, native = (snapshot[key] for key in ("quality", "proof", "native"))
    if quality.get("protocol") != "native_real_owed_blinded_foreground_v1" \
            or any(quality.get(key) is not True for key in ("judging_complete", "controls_passed", "quality_ready")) \
            or quality.get("publication_ready") is not False or quality.get("planned_slots") != 6 \
            or quality.get("planned_judgments") != 46 or quality.get("retained_attempts") != 46 \
            or quality.get("missing_judgments") != 0 or quality.get("primary_pass") != 1:
        raise ValueError("incomplete_owed_diagnostic")
    controls = quality.get("controls", [])
    if len(controls) != 34 or any(row.get("as_expected") is not True for row in controls):
        raise ValueError("failed_owed_diagnostic_controls")
    if set(proof) != set(PROOF_FIELDS):
        raise ValueError("invalid_owed_diagnostic_proof")
    for key, value in proof.items():
        size = 40 if key.endswith("_ref") else 64
        if type(value) is not str or not re.fullmatch(r"[0-9a-f]{" + str(size) + "}", value):
            raise ValueError("invalid_owed_diagnostic_proof")
    configurations = snapshot.get("configurations")
    expected_configs = {arm: {"provider": "openai" if arm == "engine_sol_low" else "gemini",
        "model": "gpt-6.1-sol" if arm == "engine_sol_low" else "gemini-3.8-flash",
        "thinking_level": "low" if arm == "engine_sol_low" else arm.removeprefix("engine_"),
        "max_output_tokens": 32768, "timeout_s": 120} for arm in ARMS}
    if configurations != expected_configs:
        raise ValueError("invalid_owed_diagnostic_configuration")
    expected = {(arm, account) for arm in ARMS for account in ACCOUNTS}
    rows = quality.get("rows", [])
    if len(rows) != 6 or {(row.get("arm"), row.get("account")) for row in rows} != expected \
            or len(native) != 6 or {(row.get("arm"), row.get("account")) for row in native} != expected:
        raise ValueError("incomplete_owed_diagnostic_denominator")
    outcomes = {(row["arm"], row["account"]): row["assessment"] for row in native}
    projected = []
    for row in rows:
        outcome = outcomes[(row["arm"], row["account"])]
        if outcome.get("setup_and_capture_ready") is not True or outcome.get("request_uploaded") is not True \
                or type(row.get("native_late_answer_delivered")) is not bool \
                or type(row.get("native_closures")) is not int or not 0 <= row["native_closures"] <= 1 \
                or row["native_late_answer_delivered"] != outcome.get("late_answer_delivered") \
                or row["native_closures"] != outcome.get("closures"):
            raise ValueError("invalid_owed_diagnostic_native_outcome")
        judgments = row.get("judgments", {})
        if set(judgments) != {"1", "2"} or any(type(judgments[index].get(field)) is not bool
                for index in ("1", "2") for field in FIELDS):
            raise ValueError("incomplete_owed_diagnostic_judgments")
        projected.append({"arm": row["arm"], "account": row["account"],
            "late_answer_delivered": row["native_late_answer_delivered"], "closures": row["native_closures"],
            "judgments": {index: {field: judgments[index][field] for field in FIELDS} for index in ("1", "2")}})
    return {"schema_version": 1, "kind": "native_owed_diagnostic", "diagnostic_complete": True,
        "full_study_result": False, "publication_ready": False,
        "task_summary": "用四句說明如何從多件待辦中選出今天先做的三件事；不新增事項或設定提醒。",
        "foreground_timeout_injected": True, "foreground_latency_measured": False,
        "planned_slots": 6, "native_requests": 6, "judgments": 46,
        "controls": {"cases": 17, "judgments": 34, "as_expected": 34},
        "judge": {"model": "gpt-6-sol", "reasoning": "medium", "passes": 2, "primary_pass": 1},
        "proof": dict(proof), "configurations": expected_configs,
        "rows": sorted(projected, key=lambda row: (ARMS.index(row["arm"]), ACCOUNTS.index(row["account"]))),
        "limits": "單一開發題、三個候選設定、兩個合成帳號；不是完整研究、holdout、真人評分或模型排名。"
                  "前景逾時為注入故障，不能給速度成績。誠實收尾仍留在分母，不算完成回答。"
                  "評審與 Sol 候選來自同一供應商／模型家族，盲評不能消除偏誤。"
                  "被原生驗證器丟棄的文字沒有保留，不能推測其拒絕原因。"}


def verified_projection(study):
    result = subprocess.run([sys.executable, "-I", "-B", "-c", REPRODUCE, str(Path(study).resolve())],
                            env={}, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("invalid_frozen_owed_diagnostic_capture")
    return project(json.loads(result.stdout))
