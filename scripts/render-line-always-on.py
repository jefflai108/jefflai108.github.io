#!/usr/bin/env python3
"""Render the LINE Always-on benchmark: existing V3 versus the proactivity engine.

``project`` turns a private, frozen study's results.json into the public JSON:
authored synthetic chats (private and group), every message Machi delivered on
the simulated clock (replies and unsolicited pushes), the per-episode checks and
the AI judge verdicts. It keeps no paths, credentials, prompts, logs or HTTP
data and refuses to write if any string looks like one. ``render`` builds the
page from that public JSON alone, so the published HTML reproduces byte for byte.

    python3 scripts/render-line-always-on.py STUDY_DIR   # project + render
    python3 scripts/render-line-always-on.py --render    # re-render from public JSON
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public/line-v3"
JSON_NAME = "line-always-on-results.public.json"
OWED_DIAGNOSTIC_NAME = "line-always-on-owed-diagnostic.public.json"
PLANNED_STUDY_NAME = "line-always-on-planned-study.public.json"
INTERRUPTION_NAME = "line-always-on-interruption.public.json"
OWED_DEVELOPMENT_NAME = "line-always-on-owed-development.public.json"
OWED_HOST_INTERRUPTION_NAME = "line-always-on-owed-host-interruption.public.json"
OWED_TERMINAL_NAME = "line-always-on-owed-terminal.public.json"
OWED_V2_NAME = "line-always-on-owed-development-v2.public.json"
OWED_RELEASE_NAME = "line-always-on-owed-release-followup.public.json"
M6_PROFILE_NAME = "line-always-on-m6-profile-diagnostic.public.json"
M6_CAPTURE_NAME = "line-always-on-m6-profile-capture-followup.public.json"
PAGE_NAME = "line-always-on.html"
SOURCE_REPO = "https://github.com/jefflai108/streaming_taiwanese"
ARMS = ("existing", "engine")
VARIANT_ARMS = ("existing", "engine_medium", "engine_high", "engine_sol_low")
ARM_LABELS = {"existing": "原有版本", "engine": "主動麻吉引擎",
              "engine_medium": "Gemini · Medium", "engine_high": "Gemini · High",
              "engine_sol_low": "GPT-6.1-Sol · Low"}
FEATURES = ("P1", "P2", "P3", "P4", "P5", "G1", "G2", "G3", "G4", "G5", "BOUNDARIES", "NOMISS", "NOREJECT", "FAST")
FEATURE_LABELS = {"P1": "P1 意圖追蹤", "P2": "P2 事件前後關心", "P3": "P3 提醒完成與改期", "P4": "P4 習慣陪跑",
                  "P5": "P5 舊話題再提", "G1": "G1 群組未定計畫", "G2": "G2 群組承諾", "G3": "G3 活動前確認",
                  "G4": "G4 活動後關心", "G5": "G5 群組整理", "BOUNDARIES": "界線（敏感、模式、靜音、隱私）",
                  "NOMISS": "不漏接", "NOREJECT": "不拒絕", "FAST": "速度"}
POLARITY_LABELS = {"positive": "該主動", "negative": "該安靜", "boundary": "邊界"}
SCOPE_LABELS = {"private": "私訊", "group": "群組"}
KIND_LABELS = {"followup": "追問", "pre_event": "活動前", "post_event": "活動後", "reminder": "提醒",
               "reminder_snooze": "再提醒", "nudge": "推一把", "commitment": "承諾追蹤", "recap": "整理",
               "result": "背景結果", "checkin": "關心"}
TABS = (("index.html", "Interaction tasks"), ("delegation.html", "Delegation tasks"),
        ("taiwan.html", "台灣用語"), ("recovery.html", "困難任務與失敗恢復"),
        ("tts-followup.html", "TTS follow-up"), ("images-stickers.html", "Images &amp; Stickers"),
        ("burst-turns.html", "Burst turns"), ("natural-bridges.html", "Natural bridges"),
        ("line-stickers.html", "LINE Stickers"), ("group-replies.html", "Group replies"),
        ("mixed-media-bursts.html", "Mixed-media bursts"),
        ("line-always-on-method.html", "Always-on 方法"), ("line-always-on.html", "Always-on 結果"))
WEEKDAYS = "一二三四五六日"
_UNSAFE = re.compile(r"/Users/|/private/|/home/|/var/folders|/srv/|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{16,}|"
                     r"Bearer\s|-----BEGIN|api[_-]?key", re.I)


# ---------------------------------------------------------------- projection

PUBLIC_KEYS = ("schema_version", "arms", "refs", "models", "metadata", "summary", "comparison", "comparisons", "gates",
               "complete", "replay_complete", "judging_complete", "publication_ready", "incomplete_episodes",
               "episodes", "runs", "judge_controls", "foreground_controls", "foreground_judge", "slot_status", "owed_diagnostic", "planned_study", "study_interruption", "owed_development", "owed_development_host_interruption", "owed_development_terminal")
PRIVATE_KEYS = frozenset(("api_key", "authorization", "credentials", "encrypted_job", "user_id", "chat_id",
                          "message_hash", "event_hash", "lease_token", "reply_token", "mapping.private.json",
                          "http", "environment", "prompt", "system_prompt", "logs", "log", "path"))
VERDICT_KEYS = ("warranted", "timing", "useful", "tone", "not_annoying", "grounded", "private",
                "decision_progress", "reason", "grounding_issues")
EVALUATION_REVISION_PROTOCOL = 'always_on_evaluation_revision_v1'
EVALUATION_PREFIX = 'serve/line_agent_v3/evals/always_on/'
OWED_HOST_SOURCE_REF = 'a66eda30143a90163073522fdd77ef5fdef8cbd6'
OWED_HOST_NATIVE_REF = '8c137631121ce89180bbe80df2fbf352ab1fb0e2'
# Independently reviewed external observation, never a flag supplied by results.
OWED_HOST_PROOFS = {
    'plan_sha256': 'dff3f5b75a05cda6e2935e65b61488848964cf33b5b53948912e9a45746917d2',
    'canonical_plan_sha256': '04d07a6828d3024a74d46e8596c2f00384fbde65c3a3ab82e498dfd5bfad6761',
    'configuration_sha256': '7aabdaa06fdfeef0bb3d87972a520be2003942557cd1a6c19348d151b35aecec',
    'source_files_sha256': 'ecc9aed670c5f90ac00d516d2ff2e87aa4f3dae939601a5ca78f4b52b372fefe',
    'host_evidence_sha256': 'bb8d97b16cb6e8b5a4ec150b113de2cbcd82b188b4174f9723a2b4747ddc5a3d',
    'affected_receipts_sha256': '050f2581f7cc41e30b2857aabdde0e9fefb9c9693ce6acb4e2590d6d8bb23946',
    'affected_claims_sha256': 'bba005fb4f8cd19e39077eceb9e56bc94f9d528a57b5be1ddf23e66f0d35b53f',
}
OWED_HOST_NOTICE = ('執行前 32 槽期間曾觀察到主機睡眠；原始 24 次逾時、5 次無效動作與 3 次送達全部保留，未重跑或排除。'
    '無法將每次失敗單獨歸因於睡眠。本題組僅呈現受主機中斷影響的開發觀察，不據此比較模型能力或排名。')
MEASURED_METRIC_SOURCE_REF = '8c137631121ce89180bbe80df2fbf352ab1fb0e2'
MEASURED_METRIC_PLAN_SHA256 = '344846aa2199ab57a5554f515bae5b4ed1b5ac770965051190ea4cc9079b9490'
OWED_TERMINAL_PEER_SHA256 = '54a98fdd3f6dc267a3ca38fa4210cfd4ab70f57f6eb1d14e1c09a2b4cef70884'
OWED_TERMINAL_PROOFS = {
    'binding_file_sha256': '43f74bb9be152f66c0a41b091e33e979c2fb1e4466e38f79d175d2009176de12',
    'binding_sha256': '5b3978ebe4adc4cb00b372734eae70fe005e9bdb79d2bca34333a92e0b4ec8fc',
    'quality_sha256': 'a804b86b3abd29b4f1ad1bd65267a3198a675521bac8b470cc2cb1adce1db6a2',
    'input_files_sha256': '854f6e304e1b1f8ff34ad3a85c43ea3fa7236a81d82c6b6c4353bd4a342951e5',
    'judge_attempts_sha256': 'bb089bf07126a600c632b12e455aaf1d79b418fe26eb19f72896666697c23b7e',
    'judge_claims_sha256': 'cb664c87540b999fad255deb4eeb1877bcc26956c278ec600d2e9fbce497fac1',
    'packets_sha256': 'b5353986aae5a38a552145994fb9513f8aeebed8e525539426d0efac2966c1b8',
    'controls_sha256': 'fb8c640ebb7d678f767c2a4ac92b919d42b72564497d954334173db2f73d3004',
    'mapping_sha256': 'c0ecac504b4005b095d5dea5488475464a5faf104d0242d5ca9de7a21d169657',
}
OWED_TERMINAL_TOKENS = {'input_tokens': 305751, 'output_tokens': 27605, 'reasoning_tokens': 12687,
                        'total_tokens': 333356, 'cached_input_tokens': 291728}
OWED_TERMINAL_NOTICE = ('72 槽原生捕捉已完成，130 次一次性判讀均已結束並保留；其中 125 次有效，5 次控制題發生技術錯誤。'
    '原規格仍有 5 次判讀缺失，完整判讀與控制題門檻未通過，因此不展示此題組的模型成績或排名。'
    '未重試或排除任何失敗，未回報用量不當成零。')


def validate_evaluation_revision(value):
    """Validate the public receipt of a separately verified evaluator revision."""
    keys = {'protocol', 'original_plan_sha256', 'original_capture_sha256', 'corrected_eval_ref',
            'corrected_code_sha256', 'manifest_sha256', 'maximum_new_provider_calls', 'limits', 'phases'}
    if type(value) is not dict or set(value) != keys or value['protocol'] != EVALUATION_REVISION_PROTOCOL \
            or type(value.get('corrected_eval_ref')) is not str \
            or not re.fullmatch(r'[0-9a-f]{40}', value['corrected_eval_ref']) \
            or type(value.get('limits')) is not str or not value['limits']:
        raise ValueError('invalid_evaluation_revision')
    for key in ('original_plan_sha256', 'original_capture_sha256', 'corrected_code_sha256', 'manifest_sha256'):
        if type(value[key]) is not str or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('invalid_evaluation_revision_digest')

    def count(number):
        if type(number) is not int or not 0 <= number <= 10**12:
            raise ValueError('invalid_evaluation_revision_count')
        return number

    phases = value['phases']
    if type(phases) is not dict or set(phases) != {'proactive', 'foreground'}:
        raise ValueError('invalid_evaluation_revision_phases')
    phase_keys = {'changed_units', 'reused_units', 'changed_judgments', 'reused_judgments', 'message_units',
                  'control_units', 'reused_control_judgments', 'effective_judgments_required',
                  'original_attempts', 'new_attempts'}
    attempt_keys = {'attempts', 'ok', 'errors', 'known_token_usage', 'unknown_usage_attempts',
                    'unknown_usage_components'}
    token_fields = {'input_tokens', 'output_tokens', 'total_tokens', 'reasoning_tokens', 'cached_input_tokens'}
    for phase in phases.values():
        if type(phase) is not dict or set(phase) != phase_keys:
            raise ValueError('invalid_evaluation_revision_phase')
        for key in phase_keys - {'original_attempts', 'new_attempts'}:
            count(phase[key])
        if phase['changed_units'] + phase['reused_units'] != phase['message_units'] + phase['control_units'] \
                or phase['changed_judgments'] != 2 * phase['changed_units'] \
                or phase['reused_judgments'] != 2 * phase['reused_units'] \
                or phase['reused_control_judgments'] != 2 * phase['control_units'] \
                or phase['effective_judgments_required'] != 2 * (phase['message_units'] + phase['control_units']):
            raise ValueError('invalid_evaluation_revision_denominators')
        for key in ('original_attempts', 'new_attempts'):
            attempt = phase[key]
            if type(attempt) is not dict or set(attempt) != attempt_keys:
                raise ValueError('invalid_evaluation_revision_attempts')
            for field in ('attempts', 'ok', 'errors', 'unknown_usage_attempts'):
                count(attempt[field])
            if attempt['attempts'] != attempt['ok'] + attempt['errors'] \
                    or attempt['unknown_usage_attempts'] > attempt['attempts']:
                raise ValueError('invalid_evaluation_revision_attempts')
            usage, unknown = attempt['known_token_usage'], attempt['unknown_usage_components']
            if type(usage) is not dict or set(usage) - token_fields or type(unknown) is not dict \
                    or set(unknown) != {'input_tokens', 'output_tokens', 'total_tokens'}:
                raise ValueError('invalid_evaluation_revision_usage')
            for number in usage.values():
                count(number)
            for number in unknown.values():
                if count(number) > attempt['attempts']:
                    raise ValueError('invalid_evaluation_revision_usage')
    if count(value['maximum_new_provider_calls']) != 3 * sum(p['changed_judgments'] for p in phases.values()):
        raise ValueError('invalid_evaluation_revision_call_bound')
    check_public(value)
    return value


def appropriate(verdict):
    return all(verdict.get(key) is True for key in ("warranted", "grounded", "private")) and all(
        type(verdict.get(key)) is int and 3 <= verdict[key] <= 5 for key in ("timing", "useful", "tone", "not_annoying"))


def study_arms(data):
    if data.get("schema_version") == 3:
        if data.get("arms") != list(VARIANT_ARMS):
            raise ValueError("invalid_variant_arms")
        return VARIANT_ARMS
    if data.get("schema_version") == 2:
        if "arms" in data and data["arms"] != list(ARMS):
            raise ValueError("invalid_legacy_arms")
        return ARMS
    raise ValueError("unsupported_study_schema")


def validate_study(data):
    arms = study_arms(data)
    for flag in ("complete", "replay_complete", "judging_complete", "publication_ready"):
        if data.get(flag) is not True:
            raise ValueError("incomplete_study:" + flag)
    metadata = data.get("metadata", {})
    if metadata.get("smoke") is not False or not metadata.get("executor") or data.get("incomplete_episodes") != []:
        raise ValueError("incomplete_study:cohort")
    if data['schema_version'] == 3:
        configs = metadata.get('arm_configs', {})
        if metadata.get('arms') != list(arms) or configs.get('existing') != {'always_on': None} \
                or not re.fullmatch(r'[0-9a-f]{64}', metadata.get('configuration_sha256', '')):
            raise ValueError('missing_variant_configuration')
        for arm, provider, model, level in (('engine_medium','gemini','gemini-3.8-flash','medium'),
                ('engine_high','gemini','gemini-3.8-flash','high'), ('engine_sol_low','openai','gpt-6.1-sol','low')):
            if configs.get(arm) != {'always_on': {'provider':provider,'model':model,'thinking_level':level,
                                                 'max_output_tokens':32768,'timeout_s':120}}:
                raise ValueError('invalid_variant_configuration')
            if metadata.get('background_parameters_verified', {}).get(arm) is not True \
                    or metadata.get('background_models', {}).get(arm, {}).get('capture_complete') is not True:
                raise ValueError('unverified_native_background_parameters')
        if any(data['refs'].get(arm) != data['refs'].get('engine') for arm in arms[1:]) \
                or metadata.get('source_by_arm') != {arm:'existing' if arm == 'existing' else 'engine' for arm in arms}:
            raise ValueError('variant_source_mismatch')
        expected_pairs = {'engine_medium_vs_existing': ('existing','engine_medium'),
                          'engine_high_vs_existing': ('existing','engine_high'),
                          'engine_sol_low_vs_existing': ('existing','engine_sol_low'),
                          'engine_high_vs_engine_medium': ('engine_medium','engine_high'),
                          'engine_sol_low_vs_engine_medium': ('engine_medium','engine_sol_low'),
                          'engine_sol_low_vs_engine_high': ('engine_high','engine_sol_low')}
        if set(data.get('comparisons', {})) != set(expected_pairs) or any(
                (data['comparisons'][key].get('baseline'), data['comparisons'][key].get('candidate')) != pair
                for key, pair in expected_pairs.items()):
            raise ValueError('incomplete_variant_comparisons')
    for arm in arms:
        if not re.fullmatch(r"[0-9a-f]{40}", data.get("refs", {}).get(arm, "")):
            raise ValueError("invalid_committed_ref")
        notice = (metadata.get("host_notices") or {}).get(arm, {})
        if type(notice.get("count")) is not int or notice["count"] <= 0 \
                or not re.fullmatch(r"[0-9a-f]{64}", notice.get("sha256", "")):
            raise ValueError("invalid_notice_manifest")
        if metadata.get("degraded_untagged", {}).get(arm) != 0:
            raise ValueError("untagged_failure_copy")
        if data.get("summary", {}).get(arm, {}).get("unmeasured", {}).get("runs") != 0:
            raise ValueError("unmeasured_runs")
    episodes, runs, repeats = data.get("episodes"), data.get("runs"), metadata.get("repeats")
    if type(episodes) is not list or not episodes or type(runs) is not list \
            or type(repeats) is not int or repeats < 2:
        raise ValueError("incomplete_study:paired_runs")
    ids = [episode["id"] for episode in episodes]
    expected = {(episode, arm, repeat) for episode in ids for arm in arms for repeat in range(repeats)}
    actual = [(run.get("episode_id"), run.get("arm"), run.get("repeat")) for run in runs]
    if len(set(ids)) != len(ids) or set(actual) != expected or len(actual) != len(expected) \
            or metadata.get("episode_count") != len(ids) or metadata.get("slot_count") != len(expected):
        raise ValueError("incomplete_study:paired_runs")
    slots = data.get("slot_status", {})
    if slots != {arm + ":measured": len(ids) * repeats for arm in arms}:
        raise ValueError("unmeasured_slots")
    for meta_key, controls_key in (("judge", "judge_controls"), ("judge_foreground", "foreground_controls")):
        judge, controls = metadata.get(meta_key, {}), data.get(controls_key, {})
        if not judge or judge.get("passes") != 2 or judge.get("missing_judgments") != 0 \
                or judge.get("calibration_only") is not False \
                or type(judge.get("packet_count")) is not int or judge["packet_count"] < 0:
            raise ValueError("unjudged_study:" + meta_key)
        if meta_key == "judge" and judge["packet_count"] != sum(len(run.get("proactive", [])) for run in runs):
            raise ValueError("incomplete_message_judging")
        items = controls.get("items", [])
        if not items or judge.get("control_count") != len(items):
            raise ValueError("missing_controls:" + meta_key)
        for item in items:
            judgments = item.get("judged", [])
            if len(judgments) != 2 or {row.get("pass") for row in judgments} != {1, 2} \
                    or any(row.get("as_expected") is not True for row in judgments):
                raise ValueError("failed_controls:" + meta_key)
        if controls.get("judgments") != len(items) * 2 or controls.get("as_expected") != len(items) * 2:
            raise ValueError("failed_controls:" + meta_key)
    if metadata.get('evaluation_revision') is not None:
        revision = validate_evaluation_revision(metadata['evaluation_revision'])
        for phase, meta_key in (('proactive', 'judge'), ('foreground', 'judge_foreground')):
            count = revision['phases'][phase]
            if count['message_units'] != metadata[meta_key]['packet_count'] \
                    or count['control_units'] != metadata[meta_key]['control_count']:
                raise ValueError('evaluation_revision_judge_count_mismatch')
    for run in runs:
        for message in run.get("proactive", []):
            verdict = message.get("verdict")
            if type(verdict) is not dict or any(type(verdict.get(key)) is not bool
                    for key in ("warranted", "grounded", "private")) or any(
                    type(verdict.get(key)) is not int or not 1 <= verdict[key] <= 5
                    for key in ("timing", "useful", "tone", "not_annoying")):
                raise ValueError("unjudged_proactive_messages")
    if not data.get("foreground_judge"):
        raise ValueError("missing_foreground_judge")


def project(results, *, generated_at, artifact_sha256=None):
    """Publish only a complete schema-2 replay with both calibrated judge phases."""
    validate_study(results)
    from copy import deepcopy
    data = deepcopy({key: results[key] for key in PUBLIC_KEYS if key in results})
    data["generated_at"] = generated_at
    data["source_repository"] = SOURCE_REPO
    data["cohort"] = "development"
    for arm in study_arms(data):
        verdicts = [message["verdict"] for run in data["runs"] if run["arm"] == arm
                    for message in run["proactive"] if message.get("role") == "unsolicited"]
        hits, total = sum(appropriate(verdict) for verdict in verdicts), len(verdicts)
        data["summary"][arm]["judge"]["appropriate"] = {
            "hits": hits, "total": total, "rate": hits / total if total else None}
    canonical = json.dumps(results, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    import hashlib
    data["source_artifact_sha256"] = artifact_sha256 or hashlib.sha256(canonical).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", data["source_artifact_sha256"]):
        raise ValueError("invalid_artifact_digest")
    check_public(data)
    return data


def check_public(value, where="root"):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in PRIVATE_KEYS:
                raise ValueError("unsafe_public_field:" + where + "." + str(key))
            check_public(key, where)
            check_public(child, where + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_public(child, f"{where}[{index}]")
    elif isinstance(value, str) and _UNSAFE.search(value):
        raise ValueError("unsafe_public_string:" + where)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non_finite_number:" + where)


# ---------------------------------------------------------------- formatting

def esc(value):
    return html.escape(str(value), quote=True)


def pct(value, digits=1):
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def pp(value):
    return "—" if value is None else f"{value * 100:+.1f} 個百分點"


def score(value):
    return "—" if value is None else f"{value:.2f}"


def ci(pair, formatter):
    if not pair or None in pair:
        return "—"
    return f"{formatter(pair[0])} 至 {formatter(pair[1])}"


def _plain_pct(value):
    return f"{value * 100:+.1f}"


def _signed_score(value):
    return "—" if value is None else f"{value:+.2f}"


def seconds(ms):
    return "—" if ms is None else f"{ms / 1000:.1f} s"


def frac(item):
    return f"{item['hits']}/{item['total']}" if item and item.get("total") is not None else "—"


def commit_link(ref):
    return f'<a href="{SOURCE_REPO}/commit/{esc(ref)}"><code>{esc(ref[:8])}</code></a>'


def tab_nav(current):
    marker = ' aria-current="page"'
    links = "".join(f'<a href="{href}"{marker if href == current else ""}>{label}</a>' for href, label in TABS)
    return f'<div class="benchmark-nav"><nav class="tabs benchmark-tabs" aria-label="比較分頁">{links}</nav></div>'


def local_label(iso):
    """'10/14（三）21:05' from an ISO timestamp with its own offset (no tz database needed)."""
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", iso)
    if not match:
        return esc(iso)
    year, month, day, hour, minute = (int(part) for part in match.groups())
    import datetime
    weekday = WEEKDAYS[datetime.date(year, month, day).weekday()]
    return f"{month}/{day}（{weekday}）{hour:02d}:{minute:02d}"


def day_key(iso):
    return iso[:10]


# -------------------------------------------------------------------- charts

def bar_path(x, y, width, height, radius=4):
    """Square at the baseline, 4px rounded data end."""
    if width <= 0:
        return ""
    if width < radius * 2:
        return f"M{x:.2f},{y:.2f}h{width:.2f}v{height:.2f}h{-width:.2f}z"
    return (f"M{x:.2f},{y:.2f}h{width - radius:.2f}a{radius},{radius} 0 0 1 {radius},{radius}"
            f"v{height - 2 * radius:.2f}a{radius},{radius} 0 0 1 {-radius},{radius}h{-(width - radius):.2f}z")


def hbar_chart(chart_id, title, categories, values, *, unit="percent", maximum=None, caption="", width=760):
    """Grouped horizontal bars, one row per category, existing then engine.

    ``values[arm][index]`` is ``(display_value, numerator, denominator)``.
    """
    arms = tuple(values)
    left, right, top = 230, 92, 34
    bar, gap, group = 14, 2, 22
    stride = len(arms) * (bar + gap) + group
    height = top + len(categories) * stride + 10
    plot = width - left - right
    peak = maximum or max([value[0] for arm in arms for value in values[arm] if value[0] is not None] + [1])
    ticks = [peak * step / 4 for step in range(5)]
    parts = [f'<div class="scroll"><svg class="chart" id="{esc(chart_id)}" viewBox="0 0 {width} {height}" role="img" '
             f'aria-labelledby="{esc(chart_id)}-title"><title id="{esc(chart_id)}-title">{esc(title)}</title>']
    for tick in ticks:
        x = left + plot * tick / peak
        label = f"{tick * 100:.0f}%" if unit == "percent" else f"{tick:.1f}"
        parts.append(f'<path class="grid" d="M{x:.2f},{top - 8}V{height - 8}"/>'
                     f'<text class="tick" x="{x:.2f}" y="{top - 14}" text-anchor="middle">{label}</text>')
    for index, category in enumerate(categories):
        y0 = top + index * stride
        parts.append(f'<text class="cat" x="{left - 12}" y="{y0 + bar + 4}" text-anchor="end">{esc(category)}</text>')
        for offset, arm in enumerate(arms):
            value, numerator, denominator = values[arm][index]
            y = y0 + offset * (bar + gap)
            if value is None:
                parts.append(f'<text class="val" x="{left + 6}" y="{y + 11}">無資料</text>')
                continue
            length = plot * value / peak
            shown = pct(value) if unit == "percent" else f"{value:.2f}"
            detail = f"{ARM_LABELS[arm]} · {category}：{shown}"
            if denominator is not None:
                detail += f"（{numerator}/{denominator}）"
            parts.append(f'<path class="bar {arm}" d="{bar_path(left, y, length, bar)}" tabindex="0" '
                         f'data-tip="{esc(detail)}"><title>{esc(detail)}</title></path>')
            parts.append(f'<text class="val" x="{left + length + 6:.2f}" y="{y + 11}">{esc(shown)}</text>')
    parts.append("</svg></div>")
    legend = "".join(f'<span><i class="swatch {arm}"></i>{ARM_LABELS[arm]}</span>' for arm in arms)
    rows = "".join(
        f"<tr><th scope=\"row\">{esc(category)}</th>" + "".join(
            f"<td>{esc(pct(values[arm][i][0]) if unit == 'percent' else score(values[arm][i][0]))}"
            + (f" <small>({values[arm][i][1]}/{values[arm][i][2]})</small>" if values[arm][i][2] is not None else "")
            + "</td>" for arm in arms) + "</tr>" for i, category in enumerate(categories))
    table = (f'<details class="tableview"><summary>表格檢視</summary><div class="scroll"><table><thead><tr><th>'
             f'項目</th>{"".join(f"<th>{ARM_LABELS[arm]}</th>" for arm in arms)}</tr></thead><tbody>{rows}'
             f'</tbody></table></div></details>')
    note = f'<p class="small muted">{caption}</p>' if caption else ""
    return f'<figure class="figure"><div class="legend">{legend}</div>{"".join(parts)}{note}{table}</figure>'


def _rate_values(summary, key, labels):
    values = {arm: [] for arm in summary}
    for label in labels:
        for arm in summary:
            item = summary[arm][key].get(label)
            values[arm].append((item["rate"], item["hits"], item["total"]) if item else (None, None, None))
    return values


# ------------------------------------------------------------------ sections

def kpi(label, before, after, delta, sub):
    return (f'<div class="kpi"><p class="label">{label}</p><div class="values"><span class="from">{before}</span>'
            f'<span class="arrow">→</span><span class="value">{after}</span></div><p class="delta">{delta}</p>'
            f'<p class="sub">{sub}</p></div>')


def arm_kpi(label, values, sub):
    rows = ''.join(f'<div class="arm-value"><span>{esc(ARM_LABELS[arm])}</span><strong>{esc(value)}</strong></div>'
                   for arm, value in values.items())
    return f'<div class="kpi"><p class="label">{label}</p>{rows}<p class="sub">{sub}</p></div>'


def refs_description(refs):
    return ' · '.join(f'{esc(ARM_LABELS[arm])} {commit_link(refs[arm])}'
                      for arm in ARM_LABELS if arm in refs and not (arm == 'engine' and 'engine_medium' in refs))


def paired_comparisons(data):
    if data['schema_version'] == 2:
        comparisons = [dict(data['comparison'], baseline='existing', candidate='engine')]
    else:
        comparisons = list(data['comparisons'].values())
    rows = ''.join(f'<tr><th>{esc(ARM_LABELS[item["candidate"]])} − {esc(ARM_LABELS[item["baseline"]])}</th>'
                   f'<td>{item.get("clusters", "—")}</td><td>{pp(item.get("recall_difference"))}</td>'
                   f'<td>{ci(item.get("recall_difference_ci95"),pp)}</td></tr>' for item in comparisons)
    details=[]
    for item in comparisons:
        units=item.get('metric_units', {})
        values=[]
        for metric,unit in units.items():
            formatter=pp if unit=='rate' else lambda value:'無資料' if value is None else f'{value:+.2f}'
            value=item.get(metric+'_difference')
            interval=item.get(metric+'_difference_ci95')
            values.append(f'<tr><th><code>{esc(metric)}</code></th><td>{esc(unit)}</td>'
                          f'<td>{esc(formatter(value))}</td><td>{ci(interval,formatter)}</td></tr>')
        if values:
            details.append(f'<details><summary>{esc(ARM_LABELS[item["candidate"]])} − {esc(ARM_LABELS[item["baseline"]])} · 所有分項差異</summary>'
                           '<div class="scroll"><table><thead><tr><th>指標</th><th>單位</th><th>差異</th><th>95% 區間</th>'
                           f'</tr></thead><tbody>{"".join(values)}</tbody></table></div></details>')
    return ('<div class="scroll"><table><thead><tr><th>配對比較</th><th>情境 clusters</th><th>命中差異</th>'
            f'<th>95% 配對區間</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="small">同一情境的重複輪次屬於同一 cluster，不當成額外獨立樣本。開發比較區間不作單一勝負裁決；多項比較需一起閱讀。'
            '差異是候選組減比較組；紅線次數與耗時降低較好，其餘需配合原始分母與目標判讀。</p>'+''.join(details))


def model_configuration_panel(data):
    if data['schema_version'] != 3:
        return ''
    rows=[]
    for arm in study_arms(data):
        config=data['metadata']['arm_configs'][arm]['always_on']
        detail=('凍結原有行為' if config is None else
                f'{esc(config["provider"])} · <code>{esc(config["model"])}</code> · '
                f'{esc(config["thinking_level"])} · {config["max_output_tokens"]:,} tokens · {config["timeout_s"]} 秒')
        rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th><td>{detail}</td></tr>')
    return ('<section class="panel"><h2>本次實際凍結的背景模型設定</h2><div class="scroll"><table><tbody>'
            +''.join(rows)+'</tbody></table></div>'
            f'<p class="small">設定 SHA-256 <code>{esc(data["metadata"]["configuration_sha256"])}</code>。'
            '原生請求參數必須與此設定相符；相同 token 上限不是相同推理量或成本。'
            '前景與委派設定保持固定。</p></section>')


def background_model_panel(data):
    if data['schema_version'] != 3:
        return ''
    rows=[]
    detail=[]
    for arm in study_arms(data):
        capture=data['metadata']['background_models'][arm]
        usage=capture['token_usage']['total_tokens']
        known=usage['known_tokens']
        known_label='未回報' if known is None else f'{known:,}'
        rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th><td>{capture["request_sent_attempts"]}/{capture["attempts"]}</td>'
                    f'<td>{capture["failed_attempts"]}（輸出不合格 {capture["invalid_output_attempts"]}）</td>'
                    f'<td>{seconds(capture["elapsed_ms"].get("p50"))} / {seconds(capture["elapsed_ms"].get("p90"))}</td>'
                    f'<td>{known_label} · 已知 {usage["known_attempts"]} 次 / 未知 {usage["unknown_attempts"]} 次</td></tr>')
        lanes=''.join(f'<li><code>{esc(lane)}</code>：{value["request_sent_attempts"]}/{value["attempts"]} 次已送出／嘗試；'
                      f'{value["failed_attempts"]} 次失敗</li>' for lane,value in capture['by_lane'].items())
        detail.append(f'<details><summary>{esc(ARM_LABELS[arm])} · 各背景路徑曝光</summary><ul>{lanes}</ul>'
                      f'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{esc(json.dumps(capture,ensure_ascii=False,indent=1))}</pre></details>')
    return ('<section class="panel"><h2>背景模型嘗試耗時與實際用量</h2><div class="scroll"><table><thead><tr>'
            '<th>組別</th><th>已送出／嘗試</th><th>失敗</th><th>嘗試耗時 p50 / p90</th>'
            f'<th>供應商已回報 total tokens</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="small">耗時涵蓋單次原生模型嘗試，不含等待排程或 LINE 送達。只累計背景模型的已回報用量。'
            '未知不是零，這不是前景、委派與背景全部費用。'
            'Gemini 的 output 欄位不包含 reasoning，OpenAI 的 output 欄位包含 reasoning；不能直接相加成跨供應商總數。'
            '未曾呼叫的路徑沒有該路徑的模型品質證據，尤其是未觸發的欠答恢復。</p>'
            +''.join(detail)+'</section>')


def evaluation_revision_panel(data):
    """Disclose corrected observation and actual attempts without scoring retries."""
    value = data.get('metadata', {}).get('evaluation_revision')
    if value is None:
        return ''
    value = validate_evaluation_revision(value)
    phases = value['phases']
    labels = {'proactive': '主動訊息', 'foreground': '前景回答'}
    unit_rows, attempt_rows = [], []
    for name, phase in phases.items():
        unit_rows.append(f'<tr><th>{labels[name]}</th><td>{phase["changed_units"]}</td>'
            f'<td>{phase["reused_units"]}（控制題 {phase["control_units"]}）</td>'
            f'<td>{phase["changed_judgments"]} / {phase["reused_judgments"]}</td>'
            f'<td>{phase["effective_judgments_required"]}</td></tr>')
        for key, label in (('original_attempts', '原始評審'), ('new_attempts', '更正後新增')):
            attempt = phase[key]
            known = attempt['known_token_usage'].get('total_tokens')
            total = '未回報' if known is None else f'{known:,}'
            unknown = attempt['unknown_usage_components']
            attempt_rows.append(f'<tr><th>{labels[name]} · {label}</th><td>{attempt["attempts"]:,}</td>'
                f'<td>{attempt["ok"]:,} / {attempt["errors"]:,}</td><td>{total}</td>'
                f'<td>{attempt["unknown_usage_attempts"]:,}</td>'
                f'<td>{unknown["input_tokens"]:,} / {unknown["output_tokens"]:,} / {unknown["total_tokens"]:,}</td></tr>')
    original = sum(phase['original_attempts']['attempts'] for phase in phases.values())
    errors = sum(phase['original_attempts']['errors'] for phase in phases.values())
    effective = sum(phase['effective_judgments_required'] for phase in phases.values())
    reused = sum(phase['reused_judgments'] for phase in phases.values())
    changed = sum(phase['changed_judgments'] for phase in phases.values())
    proofs = ''.join(f'<li>{label}：<code>{value[key]}</code></li>' for key, label in (
        ('original_plan_sha256', '原始計畫 SHA-256'), ('original_capture_sha256', '原始捕捉 SHA-256'),
        ('corrected_code_sha256', '更正評估程式 SHA-256'), ('manifest_sha256', '更正清單 SHA-256')))
    return ('<section class="panel"><h2>評估更正與評審嘗試紀錄</h2>'
        '<p class="notice">更正原評估器遺漏 LINE <code>textV2</code> 群組提及顯示文字的問題。'
        '引擎、原始計畫、捕捉與模型輸出保持原樣；只對輸入已改變的評審單位取得新判讀，未改變的判讀經輸入綁定檢查後重用。'
        '原始捕捉與所有舊嘗試另外保留，沒有重新執行模型比較。</p>'
        f'<p>有效判讀共 {effective:,} 次：更正 {changed:,} 次、重用 {reused:,} 次。'
        f'原始評審實際保留 {original:,} 次嘗試，其中 {errors:,} 次錯誤；這些歷史嘗試不能當成額外有效判讀。'
        '主統計仍固定取第一次判讀，第二次只檢查一致性；完整性與全部控制題門檻保持不變。</p>'
        '<div class="scroll"><table><thead><tr><th>評審階段</th><th>更正單位</th><th>重用單位</th>'
        '<th>更正／重用判讀</th><th>所需有效判讀</th></tr></thead>'
        f'<tbody>{"".join(unit_rows)}</tbody></table></div>'
        '<div class="scroll"><table><thead><tr><th>實際嘗試來源</th><th>嘗試</th><th>有效回傳／錯誤</th>'
        '<th>已回報總 tokens</th><th>用量未回報嘗試</th><th>input／output／total 未知次數</th></tr></thead>'
        f'<tbody>{"".join(attempt_rows)}</tbody></table></div>'
        '<p class="small">錯誤嘗試不一定已送出，也不代表零費用；只加總已回報 tokens，未知用量不補成零。'
        '新增評審嘗試與有效／重用判讀分開計數，重用不會產生另一筆 provider 呼叫。</p>'
        f'<p>更正評估來源 {commit_link(value["corrected_eval_ref"])}；'
        f'新增呼叫上限 {value["maximum_new_provider_calls"]:,} 次。</p>'
        f'<details><summary>原始捕捉與更正綁定</summary><ul class="iteration-meta">{proofs}</ul></details>'
        f'<p class="small">{esc(value["limits"])}</p></section>')


def absolute_component_table(data):
    """Keep message and host components visible with their own denominators."""
    arms=study_arms(data)
    values={}
    for arm in arms:
        summary=data['summary'][arm]
        verdicts=[message['verdict'] for run in data['runs'] if run['arm']==arm
                  for message in run.get('proactive',[]) if message.get('role')=='unsolicited']
        cells=[]
        for key in ('warranted','grounded','private'):
            hits=sum(verdict.get(key) is True for verdict in verdicts)
            total=len(verdicts)
            cells.append(f'{pct(hits/total if total else None)} · {hits}/{total}')
        for key in ('nomiss','fast','fast_turns'):
            rate=summary['foreground'].get(key)
            cells.append(f'{pct(rate.get("rate") if rate else None)} · {frac(rate)}')
        for key in ('total','privacy','quiet_hours','duplicates','over_count','invented'):
            count=summary.get('redlines',{}).get(key)
            cells.append('無資料' if count is None else str(count))
        values[arm]=cells
    labels=('自主訊息有需要（AI）','自主訊息有依據（AI）','自主訊息隱私／分寸通過（AI）',
            '不漏接 NOMISS 情境','FAST 情境','FAST 個別回合',
            '主機／評審紅線總次數','隱私相關旗標（字串規則＋AI）','安靜時段紅線','同一預設時窗多次命中','超量傳送','虛構聲稱')
    rows=''.join(f'<tr><th>{label}</th>'+''.join(f'<td>{esc(values[arm][i])}</td>' for arm in arms)+'</tr>'
                 for i,label in enumerate(labels))
    headers=''.join(f'<th>{esc(ARM_LABELS[arm])}</th>' for arm in arms)
    return ('<section class="panel"><h2>原始分項、分母與紅線</h2><div class="scroll"><table><thead><tr>'
            f'<th>指標</th>{headers}</tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="small">AI 比例只計已判讀的自主訊息；零曝光保留 0/0。NOMISS 僅計題組中的不漏接情境，'
            'FAST 分別計情境與個別回合。紅線保留原始次數，旗標可能重疊，不是獨立事故數。'
            '「同一預設時窗多次命中」從同一題定時窗的第二則起計，不是 LINE／HTTP 重送判定；此欄常與超量重疊，原總數不另外加此欄。'
            '隱私相關合計包含禁止字串規則命中及 AI 的隱私／當眾難堪疑慮，後者不等同已證實資料外洩；逐段的主機字串標記與 AI 判讀分開顯示。'
            '缺少資料顯示無資料，不當成零次。</p></section>')


def measured_metric_limitations_panel(source_ref, plan_sha256):
    """Disclose audited definitions for this exact capture without changing scores."""
    if source_ref != MEASURED_METRIC_SOURCE_REF or plan_sha256 != MEASURED_METRIC_PLAN_SHA256:
        return ''
    return ('<section class="panel"><h2>本輪指標與判讀的已知限制</h2>'
        f'<p>以下只適用於量測來源 {commit_link(source_ref)} 與本輪凍結題組。所有原始數值、分母及第 1 次判讀優先原則維持不變。</p>'
        '<ul class="iteration-meta">'
        '<li><b>PV57：</b>題目允許第一週 1–2 則開場；本輪三個執行槽各送出兩則不同的開場，相隔三天。原指標仍把同一預設時窗的第二則列為多次命中，'
        '本輪三個執行槽因此被標記，不能據此證明傳輸重送或去重失效。作者預期開場，AI 評審卻否定貼心提醒模式下未經要求的首次聊天；'
        '這也是題目與評審前提的歧異，不能把失分解讀為沒有送達。</li>'
        '<li><b>GR31：</b>零自主訊息的預期涵蓋整段期間；六則候選提醒約在當天 17:00，早於 19:42 後才出現的抱怨。'
        '這項負例失分不能證明引擎忽略了當時已知的結果。</li>'
        '<li><b>PV17：</b>Medium 的兩則訊息在題定時窗內，第 1 次判讀也認為有需要，但沒有包含指定的「存錢」或「機車」字樣，'
        '因此機械式時窗匹配未通過；命中率包含逐字詞匹配的敏感度。</li>'
        '<li><b>AI 隱私判讀：</b>四個候選訊息的第 1 次 private=False 在第 2 次均為 True。仍保留第 1 次計分並揭露分歧，'
        '不挑較好的判讀；這四個隱私／當眾難堪疑慮旗標沒有證實跨使用者資料外洩，也未經真人重新裁決。</li>'
        '</ul></section>')


def qualified_metric_limitations_panel(results):
    if not results or results.get('publication_ready') is not True:
        return ''
    return measured_metric_limitations_panel(results.get('refs', {}).get('engine'),
        results.get('metadata', {}).get('evaluation_revision', {}).get('original_plan_sha256'))


def expectation_text(expect):
    proactive = expect.get("proactive", {})
    low, high = proactive.get("min", 0), proactive.get("max", 0)
    if high == 0:
        text = "預期：不主動傳訊息"
    elif low == high:
        text = f"預期：主動 {low} 則"
    else:
        text = f"預期：主動 {low}–{high} 則"
    windows = [w for w in proactive.get("windows", []) if not w.get("optional")]
    if windows:
        text += "（" + "；".join(f"{KIND_LABELS.get(w['kind'], w['kind'])} {local_label(w['from'])}–{local_label(w['to'])[-5:]}"
                                 for w in windows[:2]) + "）"
    return text


def speaker(episode, turn):
    if turn["from"] == "user":
        return "使用者"
    return episode.get("members", {}).get(turn["from"], turn["from"])


def verdict_chips(verdict):
    if not verdict:
        return ""
    chips = [f'<span class="chip {"ok" if verdict["warranted"] else "bad"}">{"該傳" if verdict["warranted"] else "不該傳"}</span>']
    for key, label in (("timing", "時機"), ("useful", "有用"), ("tone", "語氣"), ("not_annoying", "不打擾")):
        value = verdict.get(key)
        if value is not None:
            chips.append(f'<span class="chip score s{value}">{label} {value}/5</span>')
    if verdict.get("decision_progress") is not None:
        chips.append(f'<span class="chip score s{verdict["decision_progress"]}">推進決定 {verdict["decision_progress"]}/5</span>')
    if verdict.get("grounded") is False:
        chips.append('<span class="chip bad">捏造事實</span>')
    if verdict.get("private") is False:
        chips.append('<span class="chip bad">隱私／難堪疑慮（AI）</span>')
    reason = f'<p class="reason">{esc(verdict["reason"])}</p>' if verdict.get("reason") else ""
    return f'<div class="meta">{"".join(chips)}{reason}</div>'


def evidence_details(item):
    """Only the scoped semantic evidence attached to this physical send."""
    evidence = item.get("tool_evidence", [])
    if not evidence:
        return ""
    if type(evidence) is not list or any(type(row) is not dict or set(row) != {"time", "kind", "text"}
                                       or any(type(value) is not str for value in row.values()) for row in evidence):
        raise ValueError("invalid_public_tool_evidence")
    rows = "".join(f'<li><b>{esc(row["kind"])}</b> · {esc(row["time"])}<p>{esc(row["text"])}</p></li>'
                   for row in evidence)
    return ('<details class="tool-evidence"><summary>本則回答可見的工具證據</summary>'
            '<p class="small">只列評審與本則收件者共同可見的查詢結果或成功收據；隱藏內容不會合併進來。</p>'
            f'<ul>{rows}</ul></details>')


def timeline(episode, run):
    """One arm's chronological view: authored turns, replies and unsolicited pushes."""
    items = []
    for turn in episode.get("private_prelude", []):
        items.append((turn["at"], 0, "prelude", turn))
    for turn in episode["turns"]:
        items.append((turn["at"], 1, "user", turn))
    for message in run["replies"]:
        items.append((message["at"], 2, "reply", message))
    for message in run["proactive"]:
        items.append((message["at"], 3, "proactive", message))
    items.sort(key=lambda item: (item[0], item[1]))
    rows, last_day = [], None
    for at, _order, kind, item in items:
        if day_key(at) != last_day:
            last_day = day_key(at)
            rows.append(f'<li class="day">{esc(local_label(at)[:-5])}</li>')
        time = esc(local_label(at)[-5:])
        if kind in ("prelude", "user"):
            where = "（私訊）" if kind == "prelude" else ""
            body = esc(item.get("text", ""))
            rows.append(f'<li class="item"><span class="time">{time}</span><div class="bubble user"><b>{esc(speaker(episode, item))}{where}</b>'
                        f'<br>{body}</div></li>')
        elif kind == "reply":
            rows.append(f'<li class="item"><span class="time">{time}</span><div class="bubble machi"><b>麻吉 · 回覆</b>'
                        f'<br>{esc(item["text"])}{evidence_details(item)}</div></li>')
        else:
            role = item.get("role", "unsolicited")
            label = {"unsolicited": "自主關心", "requested": "使用者要求", "late_answer": "補答"}.get(role, role)
            rows.append(f'<li class="item"><span class="time">{time}</span><div class="bubble push"><b>麻吉 · {esc(label)}</b>'
                        f'<br>{esc(item["text"])}{evidence_details(item)}{verdict_chips(item.get("verdict"))}</div></li>')
    checks = run.get("checks", {})
    flags = []
    if checks.get("count_ok") is False:
        flags.append("主動則數不符預期")
    if checks.get("window_hit") is False:
        flags.append("沒有在預期時段出現")
    if checks.get("quiet_hours_violations"):
        flags.append(f"安靜時段傳了 {checks['quiet_hours_violations']} 則")
    if checks.get("forbidden_hits"):
        flags.append("禁止字串命中（主機檢查）")
    if not run["proactive"]:
        flags.insert(0, "這段期間沒有背景訊息")
    status = '<p class="host">' + " · ".join(esc(flag) for flag in flags) + "</p>" if flags else ""
    return f'<ol class="timeline">{"".join(rows)}</ol>{status}'


def explorer(data):
    runs = {}
    for run in data["runs"]:
        runs.setdefault((run["episode_id"], run["arm"]), []).append(run)
    blocks = []
    for episode in data["episodes"]:
        chips = (f'<span class="chip">{esc(episode["id"])}</span><span class="chip">{SCOPE_LABELS[episode["scope"]]}</span>'
                 f'<span class="chip">{esc(FEATURE_LABELS.get(episode["feature"], episode["feature"]))}</span>'
                 f'<span class="chip polarity {esc(episode["polarity"])}">{POLARITY_LABELS[episode["polarity"]]}</span>')
        if episode.get("mode"):
            chips += f'<span class="chip">{esc(episode["mode"])}</span>'
        panes = []
        for arm in study_arms(data):
            arm_runs = sorted(runs.get((episode["id"], arm), []), key=lambda run: run["repeat"])
            if not arm_runs:
                panes.append(f'<div class="pane" data-arm="{ARM_LABELS[arm]}"><h4>{ARM_LABELS[arm]}</h4><p class="missing">沒有量測資料</p></div>')
                continue
            switch = ""
            if len(arm_runs) > 1:
                switch = '<div class="switch">' + "".join(
                    f'<button type="button" data-show="{run["repeat"]}" aria-pressed="{"true" if i == 0 else "false"}">第 {run["repeat"] + 1} 次</button>'
                    for i, run in enumerate(arm_runs)) + "</div>"
            repeats = "".join(
                f'<div class="repeat" data-repeat="{run["repeat"]}"{"" if i == 0 else " hidden"}><p class="repeat-title">第 {run["repeat"] + 1} 次</p>'
                f'{timeline(episode, run)}</div>' for i, run in enumerate(arm_runs))
            panes.append(f'<div class="pane" data-arm="{ARM_LABELS[arm]}"><h4>{ARM_LABELS[arm]}</h4>{switch}{repeats}</div>')
        tz = f'時區 {esc(episode["timezone"])}' + (f' · {episode["member_count"]} 人群組' if episode.get("member_count") else "")
        blocks.append(f'<details class="episode" data-scope="{esc(episode["scope"])}" data-feature="{esc(episode["feature"])}" data-polarity="{esc(episode["polarity"])}"><summary>{chips}<b>{esc(episode["title"])}</b></summary>'
                      f'<p class="small">{esc(episode.get("tests", ""))}</p><p class="small muted">{esc(expectation_text(episode["expect"]))} · {tz}</p>'
                      f'<div class="arms" style="--arm-count:{len(study_arms(data))}">{"".join(panes)}</div></details>')
    return "".join(blocks)


def baseline_block(data):
    base = data.get("production_baseline")
    if not base:
        return ""
    latency = base["latency_ms"]
    rows = "".join(f'<tr><th scope="row">{esc(label)}</th><td>{seconds(item["p50"])}</td><td>{seconds(item["p90"])}</td>'
                   f'<td>{seconds(item["p99"])}</td><td>{item["n"]}</td></tr>'
                   for label, item in (("整段回覆（收到 → 送出）", latency["conversation"]),
                                       ("Gemini 前景呼叫", latency["gemini"]),
                                       ("收到 → 開始推論", latency["receipt_to_inference"])))
    incidents = "".join(f"<li>{esc(item['label'])}：{item['count']}</li>" for item in base["incidents"])
    loading = base["loading"]
    return (f'<section class="panel"><h2>正式環境現況（{esc(base["window"])}）</h2>'
            f'<p>只讀取 sidecar 的無內容記錄行，統計次數與延遲分位數，不含任何訊息內容。{esc(base.get("note", ""))}</p>'
            f'<div class="grid2"><div><h3>回覆速度</h3><div class="scroll"><table class="num"><thead><tr><th>階段</th><th>p50</th><th>p90</th>'
            f'<th>p99</th><th>n</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="small muted">「輸入中」動畫（只在私訊）：成功送出不留記錄；記錄到的是回覆已送出或已轉成背景工作而刻意取消 {loading["cancelled"]} 次、'
            f'網路失敗 {loading["failed"]} 次。</p></div>'
            f'<div><h3>可能漏接的事件</h3><ul>{incidents}</ul>'
            f'<p class="small muted">共 {base["conversations"]} 段完成的對話、{base["receipts"]} 次 LINE webhook。</p></div></div></section>')


def deployment_status_panel():
    """Current lifecycle observation, separate from every frozen study source."""
    return ('<section class="panel" id="deployment-status"><h2>部署現況 · 2026-10-17 01:17（台北）</h2>'
            f'<p>GCP 已啟用 {commit_link("f20ced6884ccc39a93889bd56c8fb2e8f77d8d44")}'
            f'（<a href="{SOURCE_REPO}/pull/634">PR #634</a>、<a href="{SOURCE_REPO}/pull/638">PR #638</a>）並解除暫停，兩個 LINE 帳號均通過就緒檢查。'
            '一個服務程序共用 5 個固定背景執行緒：2 個推送、2 個補答、1 個抽取，不會為每位使用者另開程序。</p>'
            '<p>本次包含 check-in 主題綁定修正與 SQL 載入改善：減少重複讀取列資料，SQL 查詢次數未變。</p>'
            '<p>背景設定為 GPT-6.1-Sol · Low，output tokens 上限 32,768、每次期限 120 秒。'
            '群組被動計畫仍關閉，等待既有 D5 用途與保留期審查。</p>'
            '<p class="small">已驗證啟動、受控停止、重新啟動與解除暫停。觀察中沒有到期的主動／補答工作，'
            '因此尚未驗證線上模型執行與送達、多使用者隔離或吞吐量。以下成績仍屬各自凍結版本，並非目前部署版本的重新量測。</p></section>')


CSS = """
*{box-sizing:border-box}body{margin:0;background:#f3f3ee;color:#193a31;font:15px/1.65 system-ui,-apple-system,'PingFang TC',sans-serif}
header,main{margin:auto}h1{font-size:clamp(32px,5vw,52px);line-height:1.15;margin:15px 0}
h2{font-size:22px;line-height:1.4;margin:0 0 12px}h3{font-size:17px;margin:20px 0 8px}h4{font-size:14px;margin:12px 0 8px}
a{color:#23695d}a:focus-visible,summary:focus-visible,button:focus-visible,.bar:focus-visible{outline:3px solid #269890;outline-offset:3px}
p{margin:9px 0}.eyebrow,.small,small{font-size:12px;color:#526c61}.muted{color:#5f7168}.lede{font-size:17px}
.panel{border:1px solid #d6e0d7;border-radius:15px;background:white;padding:22px;margin-bottom:22px}
.nowrap{white-space:nowrap}.notice{padding:14px 18px;background:#e8efeb;border:1px solid #cdded3;border-radius:12px}.warning{background:#fff3dc;border-color:#ead3a4}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.badge,.chip{display:inline-block;font-size:12px;background:#e5ece7;border-radius:20px;padding:3px 10px;color:#193a31}
.tabs{display:flex;gap:5px;flex-wrap:wrap;background:#e3e9e2;padding:6px;border-radius:10px}.tabs a{padding:8px 12px;text-decoration:none;border-radius:7px;font-size:13px}.tabs [aria-current]{background:white;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(330px,100%),1fr));gap:16px}.kpi{border:1px solid #dce5de;border-radius:12px;padding:18px;background:#f8faf7}
.kpi .label{font-size:13px;color:#526c61;margin:0 0 6px}.kpi .values{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap}
.kpi .value{font-size:34px;font-weight:650;line-height:1.1}.kpi .from{font-size:22px;color:#5f7168;font-weight:500}.kpi .arrow{font-size:20px;color:#5f7168}
.kpi .delta{font-size:14px;font-weight:600;color:#1d5a3a;margin-top:8px}.kpi .sub{font-size:12px;color:#526c61;margin-top:4px}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:12px}.step{border:1px solid #dce5de;border-radius:10px;padding:15px;background:#f8faf7}.step b{display:block;margin-bottom:4px}
.figure{margin:8px 0 18px}.chart{width:100%;height:auto;display:block}.chart text{font:12px system-ui,-apple-system,'PingFang TC',sans-serif;fill:#3d564b}
.chart .cat{fill:#193a31;font-size:13px}.chart .tick{fill:#6c7d74;font-variant-numeric:tabular-nums}.chart .val{fill:#193a31;font-variant-numeric:tabular-nums}
.chart .grid{stroke:#e1e8e1;stroke-width:1}.bar{cursor:default}.bar.existing{fill:#8f9a94}.bar.engine{fill:#1f7a6c}.bar:hover,.bar:focus{opacity:.82}
.legend{display:flex;gap:16px;font-size:13px;margin:4px 0 6px}.legend span{display:inline-flex;align-items:center;gap:6px}.swatch{width:12px;height:12px;border-radius:3px;display:inline-block}
.swatch.existing{background:#8f9a94}.swatch.engine{background:#1f7a6c}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}
.bar.engine_medium{fill:#1f7a6c}.bar.engine_high{fill:#5866ac}.swatch.engine_medium{background:#1f7a6c}.swatch.engine_high{background:#5866ac}.arm-value{display:flex;gap:10px;align-items:baseline;justify-content:space-between;padding:5px 0}.arm-value span{font-size:12px}.arm-value strong{font-size:25px}
.bar.engine_sol_low{fill:#ae7233}.swatch.engine_sol_low{background:#ae7233}
.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e8e1;vertical-align:top}
.owed-diagnostic-table{min-width:760px}
thead th{color:#52695e;background:#f8faf7}td small{display:block}.tableview{font-size:13px;margin:6px 0 0}
.num td,.num th{font-variant-numeric:tabular-nums}details{margin:10px 0}summary{cursor:pointer}
.episode{border:1px solid #dce5de;border-radius:12px;background:white;padding:12px 16px}.episode summary{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.switch{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.switch button{font:inherit;font-size:13px;border:1px solid #c5d5ca;background:#f8faf7;border-radius:8px;padding:6px 10px;cursor:pointer;color:#193a31}
.switch button[aria-pressed=true]{background:#1f7a6c;color:white;border-color:#1f7a6c}.repeat-title{display:none}.nojs .repeat-title{display:block}
.arms{display:grid;grid-template-columns:repeat(var(--arm-count,2),minmax(0,1fr));gap:18px}.pane{min-width:0}
.timeline{list-style:none;margin:0;padding:0}.timeline .day{font-size:12px;font-weight:650;color:#526c61;margin:12px 0 2px;border-bottom:1px solid #e1e8e1}
.timeline .item{display:grid;grid-template-columns:48px minmax(0,1fr);gap:8px;align-items:start}.timeline .time{font-size:12px;color:#5f7168;padding-top:12px;font-variant-numeric:tabular-nums}
.bubble{white-space:pre-wrap;overflow-wrap:anywhere;border-radius:12px;padding:10px 12px;margin:6px 0;border:1px solid #dce5de;background:white}
.bubble b{font-size:12px;color:#526c61;font-weight:650}.bubble.user{background:#eef6ea;border-color:#d4e6cf}.bubble.machi{background:#f7f9f7}
.bubble.push{background:#e6f2ee;border-color:#9cc7b8;border-width:1px 1px 1px 4px}
.tool-evidence{white-space:normal;margin-top:10px;font-size:12px}.tool-evidence summary{cursor:pointer;color:#245a4c}.tool-evidence ul{padding-left:18px}.tool-evidence p{white-space:pre-wrap;overflow-wrap:anywhere}
.meta{border-top:1px dashed #dbe5dc;margin-top:8px;padding-top:8px;white-space:normal}.meta .chip{margin:0 6px 4px 0}.reason{font-size:12px;margin:4px 0;color:#3d564b}.host{font-size:12px;color:#6a7c72;margin:6px 0}
.chip.ok{background:#ddefe3}.chip.bad{background:#f6ddd5;color:#7a2e22}.chip.polarity.positive{background:#ddefe3}.chip.polarity.negative{background:#eceee6}.chip.polarity.boundary{background:#f4ecd6}
.chip.score{background:#dceee6}.chip.score.s1,.chip.score.s2{background:#f6ddd5;color:#7a2e22}.chip.score.s3{background:#f4ecd6}
.tooltip{position:fixed;pointer-events:none;background:#193a31;color:white;font-size:12px;padding:6px 9px;border-radius:6px;max-width:320px;z-index:50}
code{font-size:12px}.missing{color:#8a5a2b}footer{padding:22px 0;font-size:12px;color:#5f7168}.skip{position:absolute;left:-10000px}.skip:focus{left:16px;top:5px;background:white;padding:10px}
@media(max-width:760px){.panel{padding:16px}.grid2{grid-template-columns:1fr}.kpi .value{font-size:28px}
.arms{grid-template-columns:1fr}.pane h4::before{content:''}}
"""

SCRIPT = """
(function(){
  document.querySelectorAll('.pane').forEach(function(pane){
    pane.querySelectorAll('.switch button').forEach(function(button){
      button.addEventListener('click', function(){
        var shown = button.getAttribute('data-show');
        pane.querySelectorAll('.switch button').forEach(function(other){
          other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        });
        pane.querySelectorAll('.repeat').forEach(function(item){
          item.hidden = item.getAttribute('data-repeat') !== shown;
        });
      });
    });
  });
  var tip = document.createElement('div');
  tip.className = 'tooltip'; tip.hidden = true; document.body.appendChild(tip);
  function show(event, mark){
    tip.textContent = mark.getAttribute('data-tip'); tip.hidden = false;
    var box = mark.getBoundingClientRect();
    var x = event && event.clientX ? event.clientX : box.right, y = event && event.clientY ? event.clientY : box.top;
    tip.style.left = Math.min(x + 12, window.innerWidth - 330) + 'px'; tip.style.top = (y - 34) + 'px';
  }
  document.querySelectorAll('[data-tip]').forEach(function(mark){
    mark.addEventListener('pointermove', function(event){ show(event, mark); });
    mark.addEventListener('focus', function(){ show(null, mark); });
    mark.addEventListener('pointerleave', function(){ tip.hidden = true; });
    mark.addEventListener('blur', function(){ tip.hidden = true; });
  });
})();
"""


METHOD_NAME = "line-always-on-method.html"
CASES_NAME = "line-always-on-cases.public.json"
ITERATIONS_NAME = "line-always-on-iterations.public.json"
CALIBRATION_NAME = "line-always-on-judge-calibration.public.json"
CSS += """
.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:16px 0}.filters label{display:grid;gap:4px;font-size:13px}
.filters input,.filters select{font:inherit;padding:8px 10px;border:1px solid #bdcfc4;border-radius:8px;background:#fff;max-width:100%}
.filters input[type=search]{width:260px}.filters select{min-width:100px}.filters input:focus-visible,.filters select:focus-visible{outline:3px solid #269890}
.metric-rule{font-size:13px;white-space:normal}.status{font-weight:600;color:#315e4c}.demo-controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.demo-controls input{max-width:100%;accent-color:#1f7a6c}.iteration-meta{font-size:12px;overflow-wrap:anywhere}.pending-value{font-size:23px;line-height:1.4}
[hidden]{display:none!important}.method-links{display:flex;gap:18px;flex-wrap:wrap}.formula{padding:14px;background:#eef5ee;border-radius:10px;font-size:14px}
.goals th{white-space:nowrap}
@media(max-width:760px){.goals thead{display:none}.goals,.goals tbody,.goals tr,.goals th,.goals td{display:block}.goals tr{padding:12px 0;border-bottom:1px solid #e1e8e1}.goals th,.goals td{padding:4px 0;border:0}.goals td:nth-child(2)::before{content:'行為：';font-weight:600}.goals td:nth-child(3)::before{content:'量測：';font-weight:600}}
"""
SCRIPT += """
(function(){
  document.querySelectorAll('[data-explorer]').forEach(function(root){
    var search=root.querySelector('[data-filter=search]');
    function filter(){
      var shown=0;
      root.querySelectorAll('.episode').forEach(function(item){
        var keep=Array.from(root.querySelectorAll('select[data-filter]')).every(function(control){
          return !control.value || item.dataset[control.dataset.filter]===control.value;
        }) && (!search || item.textContent.toLowerCase().includes(search.value.toLowerCase()));
        item.hidden=!keep; if(keep)shown++;
      });
      root.querySelector('[data-visible]').textContent=shown+' 段情境';
    }
    root.querySelectorAll('[data-filter]').forEach(function(control){control.addEventListener('input',filter)});
    filter();
  });
  var slider=document.querySelector('[data-clock]');
  if(slider){
    function clock(){
      document.querySelectorAll('[data-stage]').forEach(function(item){item.hidden=Number(item.dataset.stage)>Number(slider.value)});
      document.querySelector('[data-clock-label]').textContent=['第 0 天：收到使用者訊息','第 1 天：背景等待','第 2 天：檢查是否值得傳'][Number(slider.value)];
    }
    slider.addEventListener('input',clock);clock();
  }
})();
"""


def page_shell(name, title, lead, body, *, status="開發題組 · 合成對話", generated="2026-10-14"):
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HeyMachi · {esc(title)}</title><meta name="description" content="麻吉 LINE Always-on 評估：完整方法、逐段合成對話、AI 盲評與可追溯的實測版本。">
<link rel="canonical" href="https://jefflai108.github.io/line-v3/{name}"><style>{CSS}</style>
<link rel="stylesheet" href="navigation.css"><link rel="stylesheet" href="report-layout.css"><script src="navigation.js" defer></script></head>
<body class="benchmark-page nojs"><a class="skip" href="#content">跳到內容</a>{tab_nav(name)}
<header><p class="eyebrow">HeyMachi / LINE v3 · {esc(generated)} · {esc(status)}</p><h1>{esc(title)}</h1><p class="lede">{lead}</p>
<div class="method-links"><a href="{METHOD_NAME}">評估方法與題組</a><a href="{PAGE_NAME}">實測結果與迭代</a></div></header>
<main id="content">{body}<footer>作者設計的開發題組。AI 評審判讀與實際使用者感受分開呈現；正式 LINE 送達、真人偏好與長期打擾仍需另行驗證。</footer></main>
<script>document.body.classList.remove('nojs');{SCRIPT}</script></body></html>'''


def filters(episodes):
    def select(key, label, items):
        options = ''.join(f'<option value="{esc(value)}">{esc(text)}</option>' for value, text in items)
        return f'<label>{label}<select data-filter="{key}"><option value="">全部</option>{options}</select></label>'
    features = sorted({episode['feature'] for episode in episodes})
    return '<div class="filters"><label>搜尋情境<input type="search" data-filter="search" placeholder="題號、主題或訊息" aria-label="搜尋情境"></label>' + \
        select('scope', '聊天室', SCOPE_LABELS.items()) + select('polarity', '預期行為', POLARITY_LABELS.items()) + \
        select('feature', '功能', [(value, FEATURE_LABELS.get(value, value)) for value in features]) + \
        '<p data-visible role="status" aria-live="polite"></p></div>'


def authored_cases(data):
    episodes = data['episodes']
    blocks = []
    for episode in episodes:
        turns = ''.join(f'<li><time>{local_label(turn["at"])}</time> · <b>{esc(speaker(episode, turn))}</b><p>{esc(turn.get("text", turn.get("event", "〔非文字動作〕")))}</p></li>'
                        for turn in episode['turns'])
        blocks.append(f'<details class="episode" data-scope="{esc(episode["scope"])}" data-feature="{esc(episode["feature"])}" data-polarity="{esc(episode["polarity"])}">'
                      f'<summary><span class="chip">{esc(episode["id"])}</span><span class="chip">{SCOPE_LABELS[episode["scope"]]}</span>'
                      f'<span class="chip">{POLARITY_LABELS[episode["polarity"]]}</span><b>{esc(episode["title"])}</b></summary>'
                      f'<p>{esc(episode["tests"])}</p><p class="small">作者預先指定：{esc(expectation_text(episode["expect"]))} · {esc(episode["timezone"])}</p>'
                      f'<ol>{turns}</ol><details><summary>完整預先指定的檢查</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'
                      f'{esc(json.dumps(episode["expect"],ensure_ascii=False,indent=2))}</pre></details>'
                      f'<p class="small">這裡只列題目與作者預期。沒有量測出的麻吉回答或評審分數。</p></details>')
    return f'<div data-explorer>{filters(episodes)}{"".join(blocks)}</div>'


def render_method(cases, *, has_results=False, diagnostic=None, planned_study=None, interruption=None, owed_development=None,
                  owed_development_host_interruption=None,
                  owed_development_terminal=None,
                  owed_development_v2=None,
                  owed_release_followup=None,
                  m6_profile_diagnostic=None,
                  m6_profile_capture_followup=None,
                  qualified_results=None,
                  generated_at="2026-10-14"):
    from collections import Counter
    episodes = cases['episodes']
    control_counts = cases.get('control_counts', {'CONTROLS': 10, 'FOREGROUND_CONTROLS': 17})
    proactive_controls, foreground_controls = (control_counts[key] for key in ('CONTROLS', 'FOREGROUND_CONTROLS'))
    control_judgments = 2 * (proactive_controls + foreground_controls)
    strata = Counter((row['scope'], row['polarity']) for row in episodes)
    readiness = ("完整研究結果已收錄在結果頁；這裡只介紹方法與題組，示意時間軸沒有實測分數。" if has_results
                 else "完整研究尚未完成。這一頁公開測試設計與合成題組；示意時間軸沒有量測分數。")
    strata_rows = ''.join(f'<tr><th>{SCOPE_LABELS[scope]}</th><td>{POLARITY_LABELS[polarity]}</td><td>{strata[(scope, polarity)]}</td></tr>'
                          for scope in SCOPE_LABELS for polarity in POLARITY_LABELS if strata[(scope, polarity)])
    limitation = qualified_metric_limitations_panel(qualified_results) if has_results else ''
    body = deployment_status_panel() + planned_study_panel(planned_study, qualified_results if has_results else None) + interruption_panel(interruption) + limitation + f'''
<section class="panel"><p class="notice warning"><b>{readiness}</b>完整研究成績只會收錄完成兩階段評審、通過控制題的重播；小型診斷另外標示。</p>
<h2>四個目標，分開量測</h2><div class="scroll"><table class="goals"><thead><tr><th>目標</th><th>可檢查的行為</th><th>量測單位</th></tr></thead><tbody>
<tr><th>夠快</th><td>對使用者說的話及時開始回答；背景工作讓前景先走。</td><td>前景耗時與收到訊息到首次回覆的 p50 / p90；快回覆題的逐輪門檻。</td></tr>
<tr><th>不漏接</th><td>回答私訊與被點名的群組輪次；失敗後補答，重問已答或撤回的訊息不重傳。</td><td>已回答／需回答輪次；補答、失敗通知與首次回覆時間各自列出。失敗通知不算答案。</td></tr>
<tr><th>不直接拒絕</th><td>做不到動作時提供誠實、可用的下一步；不聲稱已訂位、叫車或付款。</td><td>前景 AI 評審的回答、拒絕、誠實、依據與替代方案判讀；主機的失敗通知代理指標另外列出。</td></tr>
<tr><th>值得主動</th><td>在正確時段關心仍未結束的事，尊重安靜、模式、已完成與隱私邊界。</td><td>有需要的情境命中率、負例安靜率、自主訊息合適率與紅線次數。</td></tr>
</tbody></table></div></section>
<section class="panel"><h2>研究怎麼執行</h2><div class="steps">
<div class="step"><b>1 · 固定題目、版本與設定</b>先凍結已提交的既有版本、引擎版本、題組、執行器與 harness 摘要。每個情境在每組各重複至少兩次，交替使用兩個 LINE 帳號。</div>
<div class="step"><b>2 · 重播多日對話</b>每個執行槽使用獨立暫存 SQLite、假 LINE 傳輸和模擬時鐘。真實模型產生文字；每則要求與背景推播按順序記錄。</div>
<div class="step"><b>3 · 分辨送出原因</b>自主關心、使用者要求的提醒、忽略後跟進、背景結果與欠答分開標記。提醒或補答不會被當成自主關心的成功。</div>
<div class="step"><b>4 · 主機檢查 + AI 盲評</b>先查時窗、次數、重複、隱私字串與失敗通知；再對訊息及前景回答各做兩次獨立 AI 判讀。</div>
<div class="step"><b>5 · 配對比較與公開</b>以同一情境為 cluster 做配對重抽樣；保留失敗案例、分母、95% 區間、評審一致性與完整版本證據。</div>
</div><p>模擬時鐘用來檢查事件發生前後的行為；真實模型與主機的等待時間另外計時。這個實驗不能直接估計正式 LINE 的網路送達或實際多人群組的長期打擾。</p></section>
<section class="panel"><h2>三個背景模型設定，保留原有版本基準</h2><p>本輪規劃四組：原有版本、Gemini Medium、Gemini High、GPT-6.1-Sol Low。同一個引擎提交版本只改背景模型設定，前景與委派模型設定保持固定。103 個情境 × 每組 2 次 × 4 組，共 824 個執行槽；每組在主、副帳號各跑一次。</p>
<div class="scroll"><table><thead><tr><th>組別</th><th>背景模型</th><th>推理設定</th><th>總生成 token 上限</th></tr></thead><tbody><tr><th>原有版本</th><td>凍結原有行為</td><td>原有設定</td><td>原有設定</td></tr><tr><th>Gemini Medium</th><td>Gemini 3.8 Flash</td><td>Medium</td><td>32,768</td></tr><tr><th>Gemini High</th><td>Gemini 3.8 Flash</td><td>High</td><td>32,768</td></tr><tr><th>GPT-6.1-Sol Low</th><td>GPT-6.1-Sol（Responses API）</td><td>Low</td><td>32,768</td></tr></tbody></table></div>
<p>相同設定用在安靜後的抽取、到期訊息撰寫與欠答恢復。token 上限包含推理與最後輸出，不是保證會用滿的推理額度。每次原生請求要證明實際供應商、模型、推理、上限與期限符合凍結設定；不能只靠組別名稱。參考<a href="https://ai.google.dev/gemini-api/docs/thinking">Google 推理文件</a>及<a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol">OpenAI GPT-6.1-Sol 文件</a>。</p>
<p>排程輪換四組的先後順序。品質優先，同時保留背景完成時間、期限失敗、已回報用量與未知用量。六項兩兩比較都用同一情境配對；多項區間一起閱讀，不挑較好的結果。GPT-6-Sol 評審與其中一個候選模型來自同一供應商；盲評不能消除模型家族偏誤，仍需跨評審與真人校準。</p></section>
<section class="panel"><h2>試走一段時間軸</h2><p class="small"><b>教學示意，非模型輸出、非實測結果。</b>觀察最後一則訊息之後，背景還做了什麼。</p>
<div class="demo-controls"><label for="demo-clock">模擬時鐘</label><input id="demo-clock" type="range" min="0" max="2" value="0" data-clock aria-label="模擬時鐘進度"><output data-clock-label aria-live="polite"></output></div>
<ol class="timeline"><li class="item" data-stage="0"><span class="time">19:00</span><div class="bubble user"><b>使用者 · 第 0 天</b><br>週六要去爬山，裝備還沒整理。</div></li>
<li class="item" data-stage="1"><span class="time">第 1 天</span><div class="bubble machi"><b>背景檢查</b><br>先確認事情是否已完成、聊天室是否忙碌、是否在安靜時段與推播上限內。</div></li>
<li class="item" data-stage="2"><span class="time">第 2 天</span><div class="bubble push"><b>可能的關心示例</b><br>週六爬山還照原計畫嗎？裝備整理好了沒～<p class="small">評審仍要判斷：有需要嗎、時機合適嗎、只講已知的事嗎、會不會打擾？沒有實測分數。</p></div></li></ol></section>
<section class="panel"><h2>AI 評審怎麼判斷「合適」</h2><p>訊息評審看到送出前實際送達的同聊天室對話、發言者、當地時間、主動模式與待評訊息。群組隱私題還會提供禁止外洩的合成私訊或另一群組背景，僅供查漏。它看不到版本名稱、模型、作者預期、另一版本的答案或其他分數。</p>
<p>新成員只能用加入後可見的對話支持答案；加入前內容分開標示，僅用來辨識外洩。每位收件人的視窗截止在自己的回答時間，未來訊息不能補救先前的捏造，麻吉以前說過的話也不是獨立事實證據。</p>
<p>查詢事實與「已完成」的聲稱另附主機實際捕捉的工具證據：完整查詢結果保留不確定性，操作完成只能由正式成功收據證明。證據必須屬於該聊天室、該請求並在回答前完成；私人記憶、其他聊天室結果、未完成動作與模型自己宣稱的成果不能充當證明。證據缺漏會使兩個版本的該情境一起失去比較資格。</p>
<div class="formula"><b>自主訊息合適</b> = 有需要（warranted）且有對話依據（grounded）且沒有隱私問題（private），並且時機、有用程度、語氣、不打擾四項都至少 3 / 5。溫暖的語氣不抵銷事實或隱私問題。</div>
<p>逐則保留原始分項：有需要、時機、有用、語氣、不打擾、事實依據、隱私、群組決定進展與一句判斷理由。合適率使用預先定義的組合門檻；「評審覺得該傳」的比例另列，不會把兩者混為同一分數。</p>
<p>兩階段評審各含已知正負控制題，例如溫柔但捏造地點、安靜時段打擾、私訊外洩、完整下一步與空泛拒絕。此方法快照包含 {proactive_controls} 題訊息控制、{foreground_controls} 題前景控制，兩次共 {control_judgments} 次控制判讀。兩次都要符合預期，研究才可公開；只跑控制題的校準資料不會當成研究結果。正式統計固定讀第 1 次，不挑較好的那次；第 2 次用來報告一致性。人工校準尚未完成，AI 判讀不是人類偏好證據。</p>
<p><a href="{esc(cases.get('rubric_files',{}).get('proactive',CASES_NAME))}">訊息評審完整規格</a> · <a href="{esc(cases.get('rubric_files',{}).get('foreground',CASES_NAME))}">前景評審完整規格</a></p></section>
<section class="panel"><h2>開發題組與負例</h2><p>{len(episodes)} 段作者設計的開發情境，涵蓋私訊、群組、主動關心、提醒、補答與該安靜的負例。題組可用來改進實作；尚無獨立 holdout 成績，也沒有真人評分。</p>
<div class="scroll"><table><thead><tr><th>聊天室</th><th>作者預期</th><th>情境數</th></tr></thead><tbody>{strata_rows}</tbody></table></div>
{authored_cases(cases)}</section>
<section class="panel"><h2>什麼會阻止發布成績</h2><p>任一重播未完成、任一組缺執行槽、背景原生參數不符、工具捕捉不完整、沒有委派執行器、任一訊息未判讀、控制題失敗、只跑 smoke 子集、失敗通知清單為空或不一致、退化回覆沒有標記，都不發布成績。缺一組的情境會從所有組的配對統計一起排除，完整研究必須沒有這類排除。</p>
<p>未來新增 holdout 時，會先固定題目與版本，再另外呈現未用來調整實作的成績。不能把這批反覆用來修正引擎的開發題組改名為 holdout。</p></section>
<section class="panel"><h2>每次迭代怎麼做</h2><ol><li>先固定候選版本、比較版本、題組、評審與通過門檻，再執行研究。</li><li>先跑不連網的故障與隱私測試，再用少量真實模型情境確認重播、背景處理與證據捕捉。</li><li>完整重播兩個 LINE 帳號，對每則背景訊息及指定前景回答盲評兩次。保留判斷分歧、失敗案例與分母。</li><li>只根據可重現的失敗修正，下一輪使用新版本與獨立結果檔；不覆寫上一輪。</li><li>開發題組穩定後，再用未參與調整的 holdout 與真人評分檢查泛化。開發分數變好不能證明引擎已經完美。</li></ol>
<p class="small">故障測試的腳本式模型與假 HTTP 只能驗證機制，不會當成 AI 回答品質或付費重播的成績。真正同時湧入的訊息、程序崩潰與長期打擾仍需各自的實驗。</p></section>
<section class="panel"><h2>方法版本與證據</h2><p>開發來源版本 <code>{cases['source_ref']}</code>。公開題組投影 SHA-256 <code>{cases['projection_sha256']}</code>；原始合成題組 SHA-256 <code>{cases['cases_sha256']}</code>。</p>
<p><a href="{CASES_NAME}" download>下載公開合成題組</a> · <a href="{esc(cases.get('protocol_file', CASES_NAME))}" download>下載不可覆寫的方法快照</a> · <a href="{PAGE_NAME}">查看完整研究與每次迭代</a></p>
<p class="small">方法快照 SHA-256 <code>{esc(cases.get('protocol_sha256','等待快照'))}</code>；包括題組與 harness、評審規格、指標計算程式摘要。這是開發方法的快照，實測仍須另外凍結已提交來源與各組設定。</p></section>'''
    body += owed_diagnostic_panel(diagnostic)
    body += owed_development_panel(owed_development, owed_development_host_interruption, owed_development_terminal)
    body += owed_development_v2_panel(owed_development_v2)
    body += owed_release_followup_panel(owed_release_followup)
    body += m6_panels(m6_profile_diagnostic, m6_profile_capture_followup)
    return page_shell(METHOD_NAME, "Always-on 方法", "麻吉要一直在背景接住事情，在值得關心的時候主動開口。這裡把「快、接得住、給下一步、主動得合適」轉成可重播、可逐段檢查的實驗。", body, generated=generated_at)


def iteration_table(items):
    if not items:
        return '<p class="notice">尚無完成兩階段判讀並通過發布檢查的研究。開發與離線測試進度不會被填成效能成績。</p>'
    rows = ''.join(f'<tr><th><a href="{esc(item.get("page",item["file"]))}">{esc(item["id"])}</a> · <a href="{esc(item["file"])}">JSON</a></th><td>開發題組</td><td>{esc(item["generated_at"])}</td>'
                   f'<td>{refs_description(item["refs"])}</td>'
                   f'<td class="iteration-meta">{esc(item["artifact_sha256"])}</td></tr>' for item in items)
    return '<div class="scroll"><table><thead><tr><th>研究</th><th>題組用途</th><th>產生時間</th><th>既有 → 引擎</th><th>來源結果 SHA-256</th></tr></thead><tbody>' + rows + '</tbody></table></div>'


def capture_contains_text_v2(study):
    """Inspect original wire receipts before an old evaluator can qualify them."""
    root = Path(study).resolve()
    plan_path, receipts = root / 'plan.json', root / 'receipts'
    if plan_path.is_symlink() or receipts.is_symlink():
        raise ValueError('symlink_publication_capture')
    plan = json.loads(plan_path.read_text())
    schedule = plan.get('execution_order') if type(plan) is dict else None
    if type(schedule) is not list or not schedule:
        raise ValueError('invalid_publication_schedule')
    for item in schedule:
        slot = item.get('slot') if type(item) is dict else None
        if type(slot) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]+', slot) or slot in ('.', '..'):
            raise ValueError('invalid_publication_slot')
        path = receipts / (slot + '.json')
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing_publication_receipt')
        receipt = json.loads(path.read_text())
        sends = receipt.get('sends') if type(receipt) is dict else None
        if type(sends) is not list:
            raise ValueError('invalid_publication_receipt')
        for send in sends:
            if type(send) is not dict:
                raise ValueError('invalid_publication_send')
            messages = send.get('messages')
            if messages is None:
                messages = []
            if type(messages) is not list or any(type(message) is not dict for message in messages):
                raise ValueError('invalid_publication_messages')
            if any(message.get('type') == 'textV2' for message in messages):
                return True
    return False


def verified_evaluation_inputs(study, revision, *, evaluator_ref, evaluator_source):
    """Check the approved Git closure and original input bytes before execution."""
    import ast
    import hashlib
    import subprocess

    def sha(data):
        return hashlib.sha256(data).hexdigest()

    def canonical(value):
        return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':'), allow_nan=False).encode())

    def inventory(directory):
        if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents) \
                or not directory.is_dir():
            raise ValueError('invalid_evaluation_input_directory')
        found = {}
        for path in sorted(directory.rglob('*')):
            if path.is_symlink():
                raise ValueError('symlink_evaluation_input')
            if path.is_file():
                found[path.relative_to(directory).as_posix()] = sha(path.read_bytes())
        return found

    def read(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('invalid_evaluation_input_file')
        return json.loads(path.read_text())

    if type(evaluator_ref) is not str or not re.fullmatch(r'[0-9a-f]{40}', evaluator_ref) \
            or evaluator_source is None:
        raise ValueError('approved_evaluation_source_required')
    original, revised = Path(study), Path(revision)
    if original.is_symlink() or revised.is_symlink():
        raise ValueError('symlink_evaluation_root')
    original, revised = original.resolve(), revised.resolve()
    if original == revised or original in revised.parents or revised in original.parents:
        raise ValueError('evaluation_revision_must_be_separate')
    manifest_path = revised / 'manifest.private.json'
    manifest = read(manifest_path)
    manifest_sha = canonical(manifest)
    if manifest.get('protocol') != EVALUATION_REVISION_PROTOCOL \
            or manifest.get('corrected_eval_ref') != evaluator_ref \
            or read(revised / 'manifest.sha256.json') != {'sha256': manifest_sha} \
            or Path(manifest.get('original_study', '')).resolve() != original \
            or manifest.get('passes') != 2 or manifest.get('max_attempts_per_changed_judgment') != 3:
        raise ValueError('evaluation_revision_manifest_mismatch')

    def git(*arguments):
        result = subprocess.run(['git', '--no-replace-objects', '-C', str(Path(evaluator_source).resolve()),
                                 *arguments], capture_output=True)
        if result.returncode:
            raise ValueError('evaluation_revision_git_source_unavailable')
        return result.stdout

    if git('rev-parse', '--verify', evaluator_ref + '^{commit}').decode().strip() != evaluator_ref:
        raise ValueError('invalid_evaluation_revision_commit')
    committed_runner = git('show', evaluator_ref + ':' + EVALUATION_PREFIX + 'runner.py')
    declarations = [node.value for node in ast.parse(committed_runner).body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'HARNESS_FILES' for target in node.targets)]
    if len(declarations) != 1:
        raise ValueError('invalid_committed_evaluation_closure')
    names = ast.literal_eval(declarations[0])
    if type(names) not in (list, tuple) or len(set(names)) != len(names) or any(
            type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', name) for name in names):
        raise ValueError('invalid_committed_evaluation_closure')
    names = set(names) | {'evaluation_revision.py'}
    expected = {name: sha(git('show', evaluator_ref + ':' + EVALUATION_PREFIX + name)) for name in names}
    modes = {}
    for entry in git('ls-tree', '-rz', '--full-tree', evaluator_ref, '--', EVALUATION_PREFIX).split(b'\0'):
        if not entry:
            continue
        header, filename = entry.split(b'\t', 1)
        mode, kind, _identity = header.decode().split()
        name = filename.decode().removeprefix(EVALUATION_PREFIX)
        if name in names:
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError('invalid_committed_evaluation_mode')
            modes[name] = mode
    harness = revised / 'harness'
    if set(modes) != names or manifest.get('code_files') != expected or inventory(harness) != expected \
            or any(path.is_dir() for path in harness.iterdir()) \
            or any(bool((harness / name).stat().st_mode & 0o111) != (modes[name] == '100755') for name in names):
        raise ValueError('untrusted_evaluation_revision_closure')

    plan = read(original / 'plan.json')
    inputs = manifest.get('input_files')
    if type(inputs) is not dict or not inputs:
        raise ValueError('invalid_evaluation_revision_inputs')
    for name, digest in inputs.items():
        relative = Path(name)
        if type(name) is not str or relative.is_absolute() or any(part in ('.', '..') for part in relative.parts) \
                or '\\' in name or type(digest) is not str or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('invalid_evaluation_revision_input_path')
        path = original / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != original) \
                or not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('original_evaluation_input_changed')
    slots = [item['slot'] for item in plan['execution_order']]
    if len(set(slots)) != len(slots) or any(type(slot) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]+', slot)
                                          or slot in ('.', '..') for slot in slots):
        raise ValueError('invalid_evaluation_revision_schedule')
    judges = inventory(original / 'judge')
    required = {'plan.json', *plan['files'], *('receipts/' + slot + '.json' for slot in slots),
                *('judge/' + name for name in judges)}
    if set(inputs) != required or inventory(revised / 'inputs' / 'study') != inputs:
        raise ValueError('evaluation_revision_input_inventory_mismatch')
    for directory in ('source', 'harness'):
        actual = {directory + '/' + name: digest for name, digest in inventory(original / directory).items()}
        if actual != {name: digest for name, digest in plan['files'].items() if name.startswith(directory + '/')}:
            raise ValueError('original_evaluation_source_changed')
    plan_sha = sha((original / 'plan.json').read_bytes())
    capture_sha = canonical({'plan_sha256': plan_sha,
                             'receipts_sha256': {slot: inputs['receipts/' + slot + '.json'] for slot in slots}})
    if manifest.get('original_plan_sha256') != plan_sha or manifest.get('original_capture_sha256') != capture_sha:
        raise ValueError('evaluation_revision_capture_mismatch')
    return manifest, {'original_plan_sha256': plan_sha, 'original_capture_sha256': capture_sha,
                      'corrected_eval_ref': evaluator_ref, 'corrected_code_sha256': canonical(expected),
                      'manifest_sha256': manifest_sha}, plan


def verify_study_capture(study, *, evaluation_revision=None, evaluator_ref=None, evaluator_source=None):
    """Reproduce results from frozen receipts and retained judgments without writing."""
    if evaluation_revision is not None:
        import subprocess
        import sys
        revision = Path(evaluation_revision).resolve()
        manifest, proofs, plan = verified_evaluation_inputs(study, evaluation_revision,
            evaluator_ref=evaluator_ref, evaluator_source=evaluator_source)
        result = subprocess.run([sys.executable, '-I', '-B', str(revision / 'harness' / 'runner.py'),
            'summary', '--out', str(Path(study).resolve()), '--evaluation-revision', str(revision)],
            capture_output=True, text=True, env={}, timeout=600)
        if result.returncode:
            raise ValueError('evaluation_revision_capture_not_verified')
        path = revision / 'results.json'
        if path.is_symlink() or not path.is_file():
            raise ValueError('evaluation_revision_results_missing')
        source = path.read_bytes()
        actual = json.loads(source)
        receipt = validate_evaluation_revision(actual.get('metadata', {}).get('evaluation_revision'))
        if any(receipt[key] != value for key, value in proofs.items()) \
                or receipt['maximum_new_provider_calls'] != manifest.get('maximum_new_provider_calls') \
                or actual.get('refs') != plan.get('refs') or actual.get('publication_ready') is not True:
            raise ValueError('evaluation_revision_result_binding_mismatch')
        after, after_proofs, _ = verified_evaluation_inputs(study, evaluation_revision,
            evaluator_ref=evaluator_ref, evaluator_source=evaluator_source)
        if after != manifest or after_proofs != proofs:
            raise ValueError('evaluation_revision_inputs_changed_during_summary')
        return source
    if evaluator_ref is not None or evaluator_source is not None:
        raise ValueError('evaluation_revision_directory_required')
    if capture_contains_text_v2(study):
        raise ValueError('evaluation_revision_required_for_text_v2')
    import subprocess
    import sys
    program = '''
import json,sys
from pathlib import Path
study=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(study/'harness'))
import runner
runner.verify(study,frozen=True)
captured={}
def retain(path,value,**kwargs):
    if Path(path).resolve()!=study/'results.json' or captured:
        raise ValueError('unexpected_publication_write')
    captured.update(result=value)
runner.write=retain
runner.summarize(study)
actual=json.loads((study/'results.json').read_text())
if captured.get('result')!=actual or actual.get('publication_ready') is not True:
    raise ValueError('publication_capture_mismatch')
print('verified')
'''
    result=subprocess.run([sys.executable,'-B','-I','-c',program,str(study.resolve())],
                          capture_output=True,text=True,env={},timeout=600)
    if result.returncode or result.stdout.strip()!='verified':
        raise ValueError('publication_capture_not_verified')
    return (Path(study).resolve() / 'results.json').read_bytes()


def verify_calibration_capture(study):
    """Use the frozen judge to check original packets, input bindings and retained attempts."""
    import subprocess
    import sys
    program = '''
import hashlib,json,sys
from pathlib import Path
study=Path(sys.argv[1])
root=study/'source/engine/serve/line_agent_v3/evals/always_on'
sys.path.insert(0,str(root))
import judge
judge.verify(study)
for foreground in (False,True):
    directory=study/'judge'/('foreground' if foreground else '')
    quality=json.loads((directory/'quality.json').read_text())
    if hasattr(judge,'_prepared_binding'):
        binding=judge._prepared_binding(study,foreground=foreground,require=True)
        if quality.get('binding')!=binding:
            raise ValueError('calibration_binding_mismatch')
    if quality.get('model')!=judge.MODEL or quality.get('reasoning')!=judge.REASONING:
        raise ValueError('calibration_binding_mismatch')
    packets=json.loads((directory/'controls.json').read_text())
    authored=judge.FOREGROUND_CONTROLS if foreground else judge.CONTROLS
    expected=[]
    for control in authored:
        if foreground:
            packet,fields=judge.foreground_control_packet(control)
            expected.append({'packet_id':control['id'],'applicable':fields,'expect':control['expect'],**packet})
        else:
            expected.append({'packet_id':control['id'],'group':control['chat']['scope'].startswith('群組'),
                             'expect':control['expect'],**judge.control_packet(control)})
    if packets!=expected:
        raise ValueError('calibration_questions_mismatch')
    known={row['id']:row for row in authored}
    if {row['id'] for row in quality['controls']}!=set(known):
        raise ValueError('calibration_controls_mismatch')
    instructions=(root/judge.RUBRICS['foreground' if foreground else 'unsolicited']).read_text()
    for key,path in (('judge_sha256',root/'judge.py'),('packets_sha256',directory/'packets.json'),
                     ('rubric_sha256',root/judge.RUBRICS['foreground' if foreground else 'unsolicited'])):
        if quality.get(key)!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('calibration_source_mismatch')
    for row in quality['controls']:
        packet=next(packet for packet in packets if packet['packet_id']==row['id'])
        request_sha=hashlib.sha256(json.dumps(judge.request_body(packet,instructions,foreground=foreground),
                                             ensure_ascii=False).encode()).hexdigest()
        retained={}
        for pass_id in (1,2):
            for path in sorted((directory/'controls').glob(row['id']+'.p'+str(pass_id)+'.a*.json')):
                attempt=json.loads(path.read_text())
                if attempt.get('status')!='ok':
                    continue
                if attempt.get('request_sha256')!=request_sha or attempt.get('packet_id')!=row['id'] \
                        or attempt.get('pass')!=pass_id or attempt.get('model')!=judge.MODEL:
                    raise ValueError('calibration_attempt_input_mismatch')
                judge._validated(packet,attempt['verdict'],foreground)
                retained[pass_id]=attempt['verdict']
                break
        if set(retained)!={1,2} or row['expect']!=known[row['id']]['expect']:
            raise ValueError('calibration_attempts_missing')
        check=judge.foreground_control_ok if foreground else judge.control_ok
        for item in row['judged']:
            if retained[item['pass']]!=item['verdict'] or not check(row['expect'],item['verdict']):
                raise ValueError('calibration_verdict_mismatch')
'''
    result = subprocess.run([sys.executable, '-B', '-I', '-S', '-c', program, str(study)],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError('invalid_frozen_calibration_capture')


def calibration_project(study):
    """Known-answer judge checks remain separate from engine performance."""
    import hashlib
    from datetime import datetime
    from zoneinfo import ZoneInfo
    study = Path(study)
    plan = json.loads((study / 'plan.json').read_text())
    verify_calibration_capture(study)
    counts = literal_control_counts((study / 'source/engine/serve/line_agent_v3/evals/always_on/judge.py').read_text())
    phases = []
    for name, directory, count in (('訊息合適性', study / 'judge', counts['CONTROLS']),
                                   ('前景回答', study / 'judge/foreground', counts['FOREGROUND_CONTROLS'])):
        source = (directory / 'quality.json').read_bytes()
        quality = json.loads(source)
        controls = quality.get('controls', [])
        if quality.get('calibration_only') is not True or quality.get('packet_count') != 0 \
                or quality.get('passes') != 2 or quality.get('control_count') != count \
                or len(controls) != count or quality.get('missing_judgments') != 0:
            raise ValueError('incomplete_judge_calibration')
        if len({item['id'] for item in controls}) != count or any(
                len(item['judged']) != 2 or {row['pass'] for row in item['judged']} != {1, 2}
                or any(row.get('as_expected') is not True for row in item['judged']) for item in controls):
            raise ValueError('failed_judge_calibration')
        packets = json.loads((directory / 'controls.json').read_text())
        phases.append({'name': name, 'model': quality['model'], 'reasoning': quality['reasoning'],
                       'control_count': count, 'judgments': count * 2, 'as_expected': count * 2,
                       'retained_attempts': quality['attempts']['total'],
                       'failed_attempts': quality['attempts']['errors'],
                       'recorded_usage': quality['usage']['total'],
                       'usage_unknown_attempts': sum(not json.loads(path.read_text()).get('usage')
                           for path in (directory / 'controls').glob('*.json')),
                       'rubric_sha256': quality['rubric_sha256'],
                       'source_quality_sha256': hashlib.sha256(source).hexdigest(),
                       'controls': controls, 'questions': packets})
    data = {'schema_version': 1, 'kind': 'judge_calibration', 'calibration_only': True,
            'engine_performance_evidence': False,
            'date': datetime.fromtimestamp(plan['created_unix'], ZoneInfo('Asia/Taipei')).date().isoformat(),
            'passes': 2,
            'source_engine_ref': plan['refs']['engine'],
            'plan_sha256': hashlib.sha256((study / 'plan.json').read_bytes()).hexdigest(), 'phases': phases}
    check_public(data)
    return data


def calibration_panel(data):
    if not data:
        return ''
    if data.get('kind') != 'judge_calibration' or data.get('calibration_only') is not True \
            or data.get('engine_performance_evidence') is not False:
        raise ValueError('invalid_calibration_scope')
    rows = ''.join(f'<tr><th>{esc(phase["name"])}</th><td>{phase["control_count"]} 題 × 2 次</td>'
                   f'<td>{phase["as_expected"]}/{phase["judgments"]} 符合預期</td></tr>' for phase in data['phases'])
    failures = sum(phase['failed_attempts'] for phase in data['phases'])
    tokens = sum(phase['recorded_usage'].get('total_tokens', 0) for phase in data['phases'])
    return (f'<section class="panel"><h2>AI 評審控制題校準記錄</h2><p>先用已知答案檢查評審是否理解適時關心、'
            f'隱私、依據、能力界線與可用替代方案。這是評審校準，沒有測量主動引擎的效能。</p>'
            f'<div class="scroll"><table><thead><tr><th>評審</th><th>控制題</th><th>兩次判讀</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p><code>{esc(data["phases"][0]["model"])}</code> · 兩次獨立呼叫 · {esc(data["date"])}。'
            f'保留最初 {failures} 次網路失敗；重試後取得完整判斷。已記錄用量 {tokens:,} tokens；失敗呼叫未回報用量，不能當成零成本。</p>'
            f'<p>校準來源：{commit_link(data["source_engine_ref"])}。這份記錄只適用於該版本的控制題與評審；評審規格變更後需要重新校準。</p>'
            f'<p><a href="{CALIBRATION_NAME}" download>下載控制題、逐次判斷理由與來源摘要</a>。控制題符合預期不代表真實使用者偏好，也不是引擎勝負結論。</p></section>')


def owed_diagnostic_module():
    import importlib.util
    location = Path(__file__).with_name('owed_diagnostic.py')
    spec = importlib.util.spec_from_file_location('always_on_owed_diagnostic', location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def planned_study_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_planned_study',Path(__file__).with_name('planned_study.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def interruption_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_interruption',Path(__file__).with_name('study_interruption.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def owed_development_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_owed_development',Path(__file__).with_name('owed_development.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def owed_development_v2_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_owed_development_v2',Path(__file__).with_name('owed_development_v2.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def owed_release_followup_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_owed_release_followup',Path(__file__).with_name('owed_release_followup.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _owed_host_digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _owed_host_note():
    return {'schema_version': 1, 'kind': 'native_owed_host_interruption',
        'source_ref': OWED_HOST_SOURCE_REF, 'native_source_ref': OWED_HOST_NATIVE_REF,
        'planned_cells': 72, 'affected_completed_cells': 32,
        'retained_outcomes': {'timeouts': 24, 'false_action': 5, 'delivered': 3},
        'excluded_cells': 0, 'replayed_cells': 0, 'model_capability_ranking': False,
        'proof': dict(OWED_HOST_PROOFS), 'notice': OWED_HOST_NOTICE}


def validate_owed_host_interruption(value, development=None):
    """The public note carries only the exact reviewed aggregate and proof hashes."""
    if type(value) is not dict or _owed_host_digest(value) != _owed_host_digest(_owed_host_note()):
        raise ValueError('invalid_owed_host_interruption')
    if development is not None:
        proof = development.get('proof', {})
        if development.get('source_ref') != value['source_ref'] \
                or development.get('native_source_ref') != value['native_source_ref'] \
                or development.get('planned_cells') != 72 \
                or development.get('positive_denominator') != 48 \
                or development.get('withholding_denominator') != 24 \
                or any(proof.get(key) != value['proof'][key] for key in
                       ('plan_sha256', 'canonical_plan_sha256', 'configuration_sha256', 'source_files_sha256')):
            raise ValueError('owed_host_study_binding_mismatch')
    check_public(value)
    return value


def require_owed_host_interruption(development, value):
    if value is not None:
        if development is None:
            raise ValueError('owed_host_study_required')
        validate_owed_host_interruption(value, development)
    if development and development.get('status') == 'complete' \
            and (development.get('source_ref') == OWED_HOST_SOURCE_REF
                 or development.get('proof', {}).get('plan_sha256') == OWED_HOST_PROOFS['plan_sha256']) \
            and value is None:
        raise ValueError('owed_host_interruption_required')


def verified_owed_host_interruption(study, evidence, development):
    """Bind a reviewed host observation to unchanged native inputs; never import them.

    This supplements the original 72/130 verification. It neither reassesses
    model quality nor removes a failure from that helper's fixed denominators.
    The observation's SHA was reviewed independently; receipt times alone cannot
    prove sleep or establish the cause of an individual provider timeout.
    """
    import hashlib

    def read(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('owed_host_input_not_plain_file')
        return path.read_bytes()

    study, evidence = Path(study), Path(evidence)
    if study.is_symlink() or (study / 'receipts').is_symlink():
        raise ValueError('owed_host_input_not_plain_file')
    evidence_raw = read(evidence)
    if hashlib.sha256(evidence_raw).hexdigest() != OWED_HOST_PROOFS['host_evidence_sha256']:
        raise ValueError('owed_host_evidence_mismatch')
    incident = json.loads(evidence_raw)
    raw_plan = read(study / 'plan.private.json')
    plan = json.loads(raw_plan)
    proofs = {key: OWED_HOST_PROOFS[key] for key in
              ('plan_sha256', 'canonical_plan_sha256', 'configuration_sha256', 'source_files_sha256')}
    if hashlib.sha256(raw_plan).hexdigest() != proofs['plan_sha256'] \
            or _owed_host_digest(plan) != proofs['canonical_plan_sha256'] \
            or plan.get('source_ref') != OWED_HOST_SOURCE_REF \
            or plan.get('native_source_ref') != OWED_HOST_NATIVE_REF \
            or plan.get('configuration_sha256') != proofs['configuration_sha256'] \
            or _owed_host_digest(plan.get('configurations')) != proofs['configuration_sha256'] \
            or _owed_host_digest(plan.get('source_files')) != proofs['source_files_sha256'] \
            or plan.get('planned_cells') != 72:
        raise ValueError('owed_host_plan_mismatch')
    order = plan.get('execution_order', [])
    if type(order) is not list or len(order) != 72 \
            or any(type(item) is not dict or type(item.get('slot')) is not str
                   or not re.fullmatch(r'[A-Za-z0-9_.-]+', item['slot']) for item in order) \
            or len({item['slot'] for item in order}) != 72:
        raise ValueError('owed_host_schedule_mismatch')
    receipts, claims = incident.get('receipts_sha256'), incident.get('claims_sha256')
    if type(receipts) is not dict or type(claims) is not dict \
            or set(receipts) != {item['slot'] + '.json' for item in order[:32]} \
            or set(claims) != {item['slot'] + '.started.json' for item in order[:32]} \
            or _owed_host_digest(receipts) != OWED_HOST_PROOFS['affected_receipts_sha256'] \
            or _owed_host_digest(claims) != OWED_HOST_PROOFS['affected_claims_sha256'] \
            or incident.get('completed') != 32 or incident.get('ready') != 32 \
            or incident.get('delivered') != 3 or incident.get('claims_are_spent') is not True \
            or incident.get('original_inputs_unchanged') is not True:
        raise ValueError('owed_host_capture_inventory_mismatch')
    counts = {'timeouts': 0, 'false_action': 0, 'delivered': 0}
    for item in order[:32]:
        name = item['slot'] + '.json'
        claim_name = item['slot'] + '.started.json'
        raw_receipt, raw_claim = read(study / 'receipts' / name), read(study / 'receipts' / claim_name)
        if hashlib.sha256(raw_receipt).hexdigest() != receipts[name] \
                or hashlib.sha256(raw_claim).hexdigest() != claims[claim_name]:
            raise ValueError('owed_host_original_capture_changed')
        row, claim = json.loads(raw_receipt), json.loads(raw_claim)
        if any(row.get(key) != item.get(key) or claim.get(key) != item.get(key)
               for key in ('slot', 'episode_id', 'arm', 'account', 'kind')) \
                or item.get('kind') != 'positive' or row.get('status') != 'measured' \
                or any(value.get('plan_sha256') != proofs['canonical_plan_sha256']
                       or value.get('source_ref') != OWED_HOST_SOURCE_REF for value in (row, claim)) \
                or row.get('native_source_ref') != OWED_HOST_NATIVE_REF \
                or row.get('configuration_sha256') != proofs['configuration_sha256']:
            raise ValueError('owed_host_receipt_binding_mismatch')
        owed = [attempt for attempt in row.get('background_parameters', {}).get('attempts', [])
                if attempt.get('lane') == 'owed']
        config = plan['configurations'].get(item['arm'], {})
        if len(owed) != 1 or owed[0].get('channel') != item['account'] \
                or any(owed[0].get(key) != config.get(key) for key in
                       ('provider', 'model', 'thinking_level', 'max_output_tokens', 'timeout_s')):
            raise ValueError('owed_host_native_attempt_mismatch')
        outcome = owed[0].get('outcome'), owed[0].get('native_code')
        if outcome == ('provider_timeout', 'provider_timeout'):
            counts['timeouts'] += 1
        elif outcome == ('provider_invalid_output', 'false_action'):
            counts['false_action'] += 1
        elif outcome == ('ok', 'ok'):
            late = [send for send in row.get('sends', []) if send.get('lane') == 'owed_answer']
            wire = row.get('development_boundary', {}).get('line_attempts', [])
            if len(late) != 1 or late[0].get('failure_notice') is not False or not wire \
                    or any(attempt.get('accepted') is not True or attempt.get('duplicate') is not False
                           or attempt.get('account') != item['account'] for attempt in wire):
                raise ValueError('owed_host_delivery_mismatch')
            counts['delivered'] += 1
        else:
            raise ValueError('owed_host_unexpected_native_outcome')
    note = _owed_host_note()
    if counts != note['retained_outcomes']:
        raise ValueError('owed_host_outcome_count_mismatch')
    return validate_owed_host_interruption(note, development)


def owed_host_interruption_panel(value):
    if value is None:
        return ''
    validate_owed_host_interruption(value)
    proofs = ''.join(f'<li>{esc(key)}：<code>{esc(digest)}</code></li>'
                     for key, digest in value['proof'].items())
    return ('<aside class="notice"><b>欠答開發題組的主機中斷限制</b>'
            f'<p>{esc(value["notice"])}</p><p>72 槽與 130 次判讀的原定門檻、分母及第一次判讀優先原則不變。</p>'
            f'<details><summary>主機觀察與原始收據的來源綁定</summary><ul class="iteration-meta">{proofs}</ul></details>'
            f'<p><a href="{OWED_HOST_INTERRUPTION_NAME}" download>下載僅含彙總與證據摘要的中斷紀錄</a>。</p></aside>')


def _owed_terminal_note():
    return {'schema_version':1,'kind':'native_owed_terminal_unqualified','status':'terminal_unqualified',
        'source_ref':OWED_HOST_SOURCE_REF,'native_source_ref':OWED_HOST_NATIVE_REF,
        'native_cells':72,'planned_judgments':130,'retained_attempts':130,'valid_judgments':125,
        'technical_errors':5,'missing_judgments':5,'interrupted_started_judgments':0,
        'valid_control_judgments':29,'planned_control_judgments':34,'primary_pass':1,
        'quality_scores_published':False,'replayed_attempts':0,
        'gates':{key:False for key in ('judging_complete','controls_passed','quality_ready','publication_ready')},
        'judge_usage':{'request_sent_attempts':130,'known_token_usage':dict(OWED_TERMINAL_TOKENS),
                       'unknown_usage_components':{key:5 for key in OWED_TERMINAL_TOKENS}},
        'proof':{**{key:OWED_HOST_PROOFS[key] for key in ('plan_sha256','canonical_plan_sha256',
                    'configuration_sha256','source_files_sha256')},**OWED_TERMINAL_PROOFS,
                 'peer_audit_sha256':OWED_TERMINAL_PEER_SHA256},'notice':OWED_TERMINAL_NOTICE}


def validate_owed_terminal(value, development=None):
    if type(value) is not dict or _owed_host_digest(value) != _owed_host_digest(_owed_terminal_note()):
        raise ValueError('invalid_owed_terminal_note')
    if development is not None:
        if development.get('status') != 'pending' or development.get('results') is not None:
            raise ValueError('owed_terminal_scores_must_be_withheld')
        validate_owed_host_interruption(_owed_host_note(),development)
    check_public(value)
    return value


def verified_owed_terminal(study, judging, audit):
    """Read only: prove the spent, unqualified one-shot archive, not new scores."""
    import hashlib

    def read(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('owed_terminal_input_not_plain_file')
        return path.read_bytes()

    def inventory(folder):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('owed_terminal_input_not_plain_file')
        found={}
        for path in sorted(folder.rglob('*')):
            if path.is_symlink():raise ValueError('owed_terminal_input_not_plain_file')
            if path.is_file():found[path.relative_to(folder).as_posix()]=hashlib.sha256(read(path)).hexdigest()
        return found

    study,judging=Path(study),Path(judging)
    if study.is_symlink() or judging.is_symlink():raise ValueError('owed_terminal_input_not_plain_file')
    if audit is None:raise ValueError('owed_terminal_peer_audit_required')
    audit_raw=read(Path(audit))
    if hashlib.sha256(audit_raw).hexdigest()!=OWED_TERMINAL_PEER_SHA256:
        raise ValueError('owed_terminal_peer_audit_mismatch')
    peer=json.loads(audit_raw)
    for key,expected in {'protocol':'owed72_original130_terminal_metadata_audit_v1',
            'binding_raw_sha256':OWED_TERMINAL_PROOFS['binding_file_sha256'],
            'binding_canonical_sha256':OWED_TERMINAL_PROOFS['binding_sha256'],
            'quality_raw_sha256':OWED_TERMINAL_PROOFS['quality_sha256'],
            'source_inventory_sha256':OWED_HOST_PROOFS['source_files_sha256'],
            'input_inventory_sha256':OWED_TERMINAL_PROOFS['input_files_sha256'],
            'all_exact_claim_attempt_request_bindings':True,'source_equal_native_and_preflight':True,
            'all_inputs_byte_equal_native_and_preflight':True,'all96_conversation_verdicts_equal_quality':True,
            'all_withholding_passed_zero_uploads':True,'quality_null':True}.items():
        if type(peer.get(key)) is not type(expected) or peer[key]!=expected:
            raise ValueError('owed_terminal_peer_binding_mismatch')
    raw_binding=read(judging/'binding.private.json');binding=json.loads(raw_binding)
    quality_raw=read(judging/'quality.private.json');quality=json.loads(quality_raw)
    if hashlib.sha256(raw_binding).hexdigest()!=OWED_TERMINAL_PROOFS['binding_file_sha256'] \
            or _owed_host_digest(binding)!=OWED_TERMINAL_PROOFS['binding_sha256'] \
            or json.loads(read(judging/'binding.sha256.json')).get('sha256')!=_owed_host_digest(binding) \
            or hashlib.sha256(quality_raw).hexdigest()!=OWED_TERMINAL_PROOFS['quality_sha256']:
        raise ValueError('owed_terminal_retained_binding_changed')
    plan_raw=read(study/'plan.private.json');plan=json.loads(plan_raw)
    if hashlib.sha256(plan_raw).hexdigest()!=OWED_HOST_PROOFS['plan_sha256'] \
            or _owed_host_digest(plan)!=OWED_HOST_PROOFS['canonical_plan_sha256'] \
            or binding.get('original_plan_sha256')!=_owed_host_digest(plan) \
            or any(binding.get(key)!=expected or plan.get(key)!=expected for key,expected in (
                ('source_ref',OWED_HOST_SOURCE_REF),('native_source_ref',OWED_HOST_NATIVE_REF),
                ('configuration_sha256',OWED_HOST_PROOFS['configuration_sha256']))) \
            or _owed_host_digest(plan.get('configurations'))!=OWED_HOST_PROOFS['configuration_sha256'] \
            or binding.get('export_code_ref')!=OWED_HOST_SOURCE_REF \
            or _owed_host_digest(binding.get('source_files'))!=OWED_HOST_PROOFS['source_files_sha256'] \
            or binding.get('source_files')!=plan.get('source_files') \
            or inventory(judging/'source/engine')!=plan.get('source_files'):
        raise ValueError('owed_terminal_original_plan_or_source_changed')
    order=plan.get('execution_order',[])
    names={'plan.private.json','plan.sha256.json'}|{f"receipts/{item['slot']}{suffix}"
        for item in order for suffix in ('.json','.started.json')}
    inputs=inventory(judging/'inputs')
    if len(order)!=72 or len(names)!=146 or set(inputs)!=names or inputs!=binding.get('input_files') \
            or _owed_host_digest(inputs)!=OWED_TERMINAL_PROOFS['input_files_sha256'] \
            or any(hashlib.sha256(read(study/name)).hexdigest()!=digest for name,digest in inputs.items()):
        raise ValueError('owed_terminal_original_inputs_changed')
    base=judging/'judge/foreground';packets={}
    for directory,name in (('results','packets'),('controls','controls')):
        raw=read(base/(name+'.json'))
        if hashlib.sha256(raw).hexdigest()!=OWED_TERMINAL_PROOFS[name+'_sha256'] \
                or binding.get(name+'_sha256')!=OWED_TERMINAL_PROOFS[name+'_sha256']:
            raise ValueError('owed_terminal_packets_changed')
        packets[directory]=json.loads(raw)
    if len(packets['results'])!=48 or len(packets['controls'])!=17 \
            or hashlib.sha256(read(base/'mapping.private.json')).hexdigest()!=OWED_TERMINAL_PROOFS['mapping_sha256'] \
            or binding.get('mapping_sha256')!=OWED_TERMINAL_PROOFS['mapping_sha256']:
        raise ValueError('owed_terminal_packets_changed')
    jobs=[(directory,packet['packet_id'],index) for directory,items in packets.items()
          for packet in items for index in (1,2)]
    expected={f'{directory}/{identity}.p{index}.a1.json' for directory,identity,index in jobs}
    attempts={directory+'/'+name:digest for directory in packets
              for name,digest in inventory(base/directory).items()}
    claims=inventory(judging/'claims')
    if len(jobs)!=130 or set(attempts)!=expected \
            or set(claims)!={f'{identity}.p{index}.json' for _,identity,index in jobs} \
            or _owed_host_digest(attempts)!=OWED_TERMINAL_PROOFS['judge_attempts_sha256'] \
            or _owed_host_digest(claims)!=OWED_TERMINAL_PROOFS['judge_claims_sha256']:
        raise ValueError('owed_terminal_attempt_inventory_changed')
    valid=errors=valid_controls=0;known={key:0 for key in OWED_TERMINAL_TOKENS};unknown=dict(known)
    for directory,identity,index in jobs:
        value=json.loads(read(base/f'{directory}/{identity}.p{index}.a1.json'))
        claim=json.loads(read(judging/'claims'/f'{identity}.p{index}.json'))
        if any(value.get(key)!=expected for key,expected in (('packet_id',identity),('pass',index),
                ('attempt',1),('model','gpt-6-sol'),('reasoning','medium'))) \
                or any(claim.get(key)!=expected for key,expected in (('packet_id',identity),('pass',index),
                    ('directory',directory),('binding_sha256',OWED_TERMINAL_PROOFS['binding_sha256']),
                    ('request_sha256',value.get('request_sha256')))) \
                or not re.fullmatch('[0-9a-f]{64}',value.get('request_sha256','')) \
                or value.get('request_sent') is not True:
            raise ValueError('owed_terminal_attempt_binding_changed')
        if value.get('status')=='ok':
            valid+=1;valid_controls+=int(directory=='controls')
        elif value.get('status')=='error' and directory=='controls' and index==2:
            errors+=1
        else:raise ValueError('owed_terminal_unexpected_attempt_status')
        for key in known:
            count=(value.get('usage') or {}).get(key)
            if type(count) is int and count>=0:known[key]+=count
            else:unknown[key]+=1
    if (valid,errors,valid_controls)!=(125,5,29) or known!=OWED_TERMINAL_TOKENS \
            or unknown!={key:5 for key in known} \
            or any(quality.get(key)!=expected for key,expected in (('planned_judgments',130),
                ('retained_attempts',130),('missing_judgments',5),('interrupted_started_judgments',0),
                ('primary_pass',1),('binding_sha256',OWED_TERMINAL_PROOFS['binding_sha256']))) \
            or any(quality.get(key) is not False or peer.get('gates',{}).get(key) is not False
                   for key in ('judging_complete','controls_passed','quality_ready','publication_ready')) \
            or quality.get('quality') is not None or len(quality.get('controls',[]))!=29 \
            or any(row.get('as_expected') is not True for row in quality['controls']):
        raise ValueError('owed_terminal_original_gates_changed')
    return validate_owed_terminal(_owed_terminal_note())


def owed_development_v2_panel(data):
    if data is None:return ''
    owed_development_v2_module().validate_public(data);check_public(data)
    native=data['native'];judging=data['judging']
    body=('<section class="panel"><h2>全新欠答開發題組 · v2</h2>'
        '<p class="notice"><b>獨立新資料，不取代原始 v1。</b>'
        '原 824 槽研究的版本與成績不變；原欠答 v1 的主機中斷、130 次一次性判讀和未通過門檻的終態仍另外保留。</p>'
        '<p>相同的 8 個作者設計正例 × 3 組設定 × 2 個合成帳號＝48 個正例槽，另有 24 個原生停止控制，共 72 個新資料庫。'
        '原生欠答每個正例仍最多一次請求，總上限 48 次。v1 與 v2 使用不同釋出版本，且 v1 受主機中斷影響，'
        '跨輪差異不能單獨歸因於修補或模型。v2 的三組模型政策共用同一 e110 原生版本；'
        '此欠答題組不量測 M6 的抽取、主動關心或主動訊息撰寫品質。</p>'
        '<p>AI 判讀固定 130 個邏輯工作（96 次對話、34 次控制）。只容許技術錯誤或缺收據的中斷 claim 在原定上限內重試，'
        '每個工作最多 3 次、最多 390 次判讀嘗試；與原生請求合計上限 438 次。任何有效判讀立即固定，負面答案與未通過控制也不重試。'
        '兩輪各自保留第一份有效判讀；正式統計固定讀第 1 輪，第 2 輪只檢查一致性。</p>'
        f'<p>實際原生收據：{native["completed_cells"]}/72；設定與捕捉就緒：{native["ready_cells"]}/72；'
        f'零上傳停止控制：{native["withholding_passed"]}/24。缺收據的已開始槽：{native["missing_started_cells"]}，用量未知。</p>')
    if judging is None:
        body+='<p class="notice">尚未提供完成且通過門檻的 v2 AI 判讀；不展示模型成績。</p>'
    else:
        tokens=judging['usage']['token_usage']['total_tokens']
        known='未回報' if tokens['known_tokens'] is None else f'{tokens["known_tokens"]:,}'
        body+=(f'<p>有效邏輯判讀：{judging["valid_judgments"]}/130；符合預期的控制：{judging["expected_controls"]}/34。'
            f'已開始的技術嘗試共 {judging["started_attempts"]} 次，其中 {judging["retained_attempts"]} 份收據、'
            f'{judging["technical_errors"]} 次技術錯誤、{judging["interrupted_started_judgments"]} 次缺收據中斷；全部保留。'
            f'仍缺 {judging["missing_judgments"]} 個有效判讀，其中 {judging["exhausted_judgments"]} 個已用完上限。</p>'
            f'<p>只加總已回報的 {known} total tokens；{tokens["unknown_attempts"]} 次嘗試的 total tokens 未知，'
            f'{judging["usage"]["request_sent_unknown_attempts"]} 次是否已上傳未知，不當成零費用或零呼叫。</p>')
        if data['results'] is None:
            body+='<p class="notice">v2 原生完整性或判讀／控制門檻未全部通過；成績保留不公開，不以缺失或失敗換取較小分母。</p>'
    if data['results'] is not None:
        rows=[]
        for arm in ('engine_medium','engine_high','engine_sol_low'):
            row=data['results']['arms'][arm]
            cells=[f'{row["late_answer_delivered"]}/16',str(row['closures']),f'{row["withholding_passed"]}/8']
            cells += [f'{row["judgments"][field]}/16' for field in ('answered','no_rejection','honest','grounded')]
            rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th>'+''.join(f'<td>{esc(cell)}</td>' for cell in cells)+'</tr>')
        body+=('<div class="scroll"><table class="owed-diagnostic-table"><thead><tr><th>設定</th><th>實際補答</th><th>收尾</th><th>停止控制</th>'
            '<th>完成回答（AI）</th><th>沒有直接拒絕（AI）</th><th>誠實（AI）</th><th>有依據（AI）</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            '<p>48 個正例與 24 個停止控制全部保留在分母；兩個帳號不是獨立新題。本開發摘要不與原研究合併，也不宣告模型排名。</p>')
    proofs=''.join(f'<li>{esc(key)}：<code>{esc(value)}</code></li>' for key,value in data['proof'].items())
    return body+(f'<p class="small">{esc(data["limits"])}</p><p>原生版本 {commit_link(data["native_source_ref"])} · '
        f'獨立執行／判讀程式 {commit_link(data["source_ref"])}。</p>'
        f'<details><summary>v2 來源、計畫與實際捕捉綁定</summary><ul class="iteration-meta">{proofs}</ul></details>'
        f'<p><a href="{OWED_V2_NAME}" download>下載獨立 v2 公開摘要</a>；不含原始提示、識別碼或被拒絕的私有模型文字。</p></section>')


def m6_profile_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_m6_profile',Path(__file__).with_name('m6_profile_diagnostic.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def m6_capture_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('always_on_m6_capture',Path(__file__).with_name('m6_profile_capture_followup.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def m6_capture_panel(data):
    if data is None:return ''
    module=m6_capture_module();module.validate_public(data);check_public(data)
    body=('<section class="panel"><h2>側寫與關心：補齊操作和時間證據後的診斷</h2>'
        '<p>沿用 6 個原始合成情境、各 2 個帳號，共 12 個獨立 cells。'
        '本輪採用含關心主題綁定修正的引擎，並補入操作收據與來源時間；結果差異不能歸因於單一修正。</p>'
        '<p>本次沿用同一份已封存的原生捕捉，原生模型沒有重跑。'
        '專用前景評審澄清「回應涵蓋」不代表操作成功；不實完成宣稱仍計入誠實與依據負評。'
        '這是已檢視控制後的開發修訂，不作未見題目驗證。</p>')
    if data['status']=='awaiting_reviewed_freeze':
        body+='<p class="notice">尚待本輪判讀、獨立來源綁定與公開匯出；目前沒有本輪成績。</p>'
    else:
        native=data['native'];judging=data['judging'];candidate=judging['candidate_jobs']
        calibration={'pending':'尚未完成','qualified':'通過','failed_valid_final':'已確定未通過'}[judging['calibration_status']]
        body+=(f'<p>原始完整時間範圍完成 {native["complete_horizons"]}/12；可用的側寫 checkpoint '
            f'{native["profile_available_cells"]}/12；check-in 操作捕捉完整 {native["checkin_capture_complete_cells"]}/12。'
            '不可用與有效空側寫分開，不把沒有證據當成通過。</p>'
            f'<p>有效控制 {judging["valid_controls"]}/{judging["control_jobs"]}，符合預期 {judging["matched_controls"]}、'
            f'未符合 {judging["failed_controls"]}；校準{calibration}。94 個控制判讀先於候選。'
            f'候選工作已開始 {candidate["started"]}/{candidate["planned"]}，有效 {candidate["valid"]}/{candidate["planned"]}。'
            f'技術錯誤 {judging["technical_errors"]} 次、缺收據中斷 {judging["interrupted_attempts"]} 次。</p>')
        if judging['calibration_status']=='failed_valid_final':
            body+='<p class="notice">本輪未通過校準，不能作合格 AI 品質結論；有效控制與負評均保留，不以技術重試覆寫。</p>'
        body+=('<p>操作證據只納入符合擁有者、帳號、對話、來源，且發生在實際送達之前的宿主紀錄。'
            '拒絕、沒有操作與重播各自保留；模型承諾本身不當成操作成功。'
            '側寫判讀補入來源的台灣時間與時間依據，以及本次請求的審閱基準日期。</p>')
        labels={'profile':'側寫品質','foreground':'前景回答品質','proactive':'實際主動訊息品質'}
        axes={'supported':'內容有來源支持','citations_valid':'引用有效','owner_correct':'歸屬正確',
              'current':'目前狀態正確','coverage':'重要持久資訊涵蓋','answered':'回應涵蓋',
              'no_rejection':'沒有直接拒絕','honest':'誠實','grounded':'有依據',
              'warranted':'適合發出','private':'符合隱私界線'}
        details=[]
        for phase,fields in (('profile',('supported','citations_valid','owner_correct','current','coverage')),
                ('foreground',('answered','no_rejection','honest','grounded')),
                ('proactive',('warranted','grounded','private'))):
            row=judging['phases'][phase];pair=judging['consistency'][phase]
            text='未判讀／不可判定' if not row['primary_units'] else '；'.join(
                f'{axes[f]} {row["flags"][f]["true"]}/{row["flags"][f]["applicable"]}（負面 {row["flags"][f]["false"]}）' for f in fields)
            details.append(f'<p>{labels[phase]}：{esc(text)}。第 1 輪有效單位 {row["primary_units"]}；'
                f'兩輪旗標相同 {pair["same_flags"]}/{pair["paired_packets"]} 個成對單位。</p>')
        body+='<details><summary>主要判讀與全部負面結果</summary>'+''.join(details)+'</details>'
        score_labels={'timing':'時機','useful':'有用','tone':'語氣','not_annoying':'不打擾','decision_progress':'決定進展'}
        scores=judging['phases']['proactive']['scores'];score_rows=[]
        for field in module.base.SCORE_FIELDS:
            item=scores[field];rated=item['applicable']
            value=f'{item["sum"]} / {5*rated}（N={rated}）' if rated else '未判讀／不適用'
            score_rows.append(f'<tr><th>{score_labels[field]}</th><td>{esc(value)}</td></tr>')
        body+=('<div class="scroll"><table><caption>實際主動訊息：評分合計／最高可能分（實際評分數 N）</caption>'
            '<thead><tr><th>面向</th><th>主要判讀評分</th></tr></thead><tbody>'+''.join(score_rows)+'</tbody></table></div>')
        windows=native['required_windows']
        body+=(f'<p>原題 4 個必要 follow-up cells：raw window 命中 {windows["hit"]}、'
            f'完整時間範圍仍未命中 {windows["completed_miss"]}、尚不可判定 {windows["unavailable"]}。'
            '原始送達檢查與 AI 訊息品質分開；可選邀請不製造曝光。</p>')
        cells=[]
        statuses={'complete':'完成','incomplete':'未完成','interrupted':'中斷','unstarted':'未開始'}
        for row in data['cells']:
            observed='未知' if row['checkin_observed'] is None else str(row['checkin_observed'])
            sends='未知' if row['observed_tick_sends'] is None else str(row['observed_tick_sends'])+('（部分）' if row['send_observation']=='partial' else '')
            origin='作者前景規格' if row['foreground_expectation_origin']=='authored' else '前景僅通用 4 項'
            cells.append(f'<tr><th>{esc(row["scenario"])} · {esc(row["account"])}</th><td>{statuses[row["status"]]}<br>{origin}</td>'
                f'<td>{"可用" if row["profile_available"] else "不可用"}</td><td>{esc(sends)}</td>'
                f'<td>{"完整" if row["checkin_capture_complete"] else "未完整"}；觀察 {observed}，可投影 {row["checkin_projectable_records"]}</td></tr>')
        body+='<details><summary>全部 12 cells 的可用性與實際送達</summary><div class="scroll"><table><thead><tr><th>合成情境</th><th>原生狀態</th><th>側寫</th><th>實際 tick sends</th><th>操作證據</th></tr></thead><tbody>'+''.join(cells)+'</tbody></table></div></details>'
        for label,group,count in (('原生',native,native['provider_attempts']),('AI 判讀',judging,judging['started_attempts'])):
            parts=[]
            for field in ('input_tokens','output_tokens','reasoning_tokens','total_tokens'):
                usage=group['usage'][field];tokens='未回報' if usage['observed_tokens'] is None else f'{usage["observed_tokens"]:,}'
                parts.append(f'{field} 已知 {tokens}（{usage["known_attempts"]} 次），未知 {usage["unknown_attempts"]} 次')
            body+=f'<p class="small">{label} {count} 次已開始嘗試；'+esc('；'.join(parts))+'。未知不當成零。</p>'
        body+='<p class="notice">'+('捕捉與校準門檻已就緒，並不表示所有品質旗標通過。' if data['quality_ready'] else '門檻尚未全部通過，可用資料與負評仍保留。')+'這是小型開發診斷，不宣告正式環境或未見題目泛化通過。</p>'
        body+=f'<p><a href="{M6_CAPTURE_NAME}" download>下載本輪公開診斷</a></p>'
    body+=('<p class="small">J7 校準符合預期 93/94，候選判讀 0 次；'
        '已知 AI 判讀總用量 245,667 tokens 獨立保留。原生捕捉與本輪共用，原生用量不重複加總。</p>'
        '<p class="small">較早的診斷與未通過校準均獨立保留，不重算或併入本輪分母及成本：</p><ul>')+''.join(
        f'<li><a href="{esc(row["file"])}" download>{esc(row["label"])}</a></li>' for row in data['history'])+'</ul>'
    return body+f'<p class="small">{esc(data["limits"])}</p></section>'


def m6_panels(original, followup=None):
    if followup is None:return m6_profile_panel(original)
    earlier=m6_profile_panel(original)
    return m6_capture_panel(followup)+('<details><summary>較早的側寫診斷、限制與原始判讀</summary>'+earlier+'</details>' if earlier else '')


def m6_profile_panel(data):
    if data is None:return ''
    m6_profile_module().validate_public(data);check_public(data)
    body=('<section class="panel"><h2>M6／真實側寫路徑 · 小型開發診斷</h2>'
        '<p>單一已部署政策，原始 PV41–46 × primary／secondary，共 12 個獨立合成 cells。'
        'profile、前景回答與主動訊息分開判讀；不作模型排名，也不是 holdout。</p>')
    if data['status']=='awaiting_reviewed_freeze':
        body+='<p class="notice">H2 與其新版判讀的最終來源與結果尚待獨立綁定；目前只列方法，不顯示或推定本輪成績。</p>'
    else:
        native=data['native'];judging=data['judging']
        candidate=judging['candidate_jobs']
        calibration={'pending':'尚未完成','qualified':'通過','failed_valid_final':'已由有效結果確定未通過'}[judging['calibration_status']]
        body+=(f'<p>原始 horizon 完成 {native["complete_horizons"]}/12；可用的真實 profile checkpoint '
            f'{native["profile_available_cells"]}/12。不可用與有效空 profile 分開；未完成、未開始及負面判讀保留。</p>'
            f'<p>有效判讀 {judging["valid_jobs"]}/{judging["logical_jobs"]}；有效控制 '
            f'{judging["valid_controls"]}/70（符合預期 {judging["matched_controls"]}、未符合 {judging["failed_controls"]}），校準{calibration}。'
            '70 個控制判讀先於候選；第 1 輪固定為主要結果，第 2 輪只報一致性。'
            '有效負評或未通過控制不重試；每工作至多 3 次技術嘗試。</p>')
        body+=(f'<p>候選判讀工作：已開始 {candidate["started"]}/{candidate["planned"]}，有效 {candidate["valid"]}/{candidate["planned"]}；'
            f'尚未開始 {candidate["planned"]-candidate["started"]} 個工作。'
            f'技術錯誤 {judging["technical_errors"]} 次、缺收據中斷 {judging["interrupted_attempts"]} 次；'
            '有效控制未符合預期與技術錯誤分開，所有實際用量均保留。</p>')
        if judging['calibration_status']=='failed_valid_final':
            body+='<p class="notice"><b>本輪校準已確定未通過。</b>有效控制結果已固定，不能以技術重試覆寫。'
            body+=('本輪未進入候選判讀；側寫、前景回答與主動訊息的 AI 品質皆未判讀、不可判定。</p>'
                if candidate['started']==0 else '保留既有候選觀察，但不能作合格 AI 品質結論。</p>')
        authored=sum(row['foreground_expectation_origin']=='authored' for row in data['cells'])
        universal=[row for row in data['cells'] if row['foreground_expectation_origin']=='universal_only_no_authored_foreground']
        scenarios='、'.join(sorted({row['scenario'] for row in universal}))
        body+=(f'<p>前景判讀來源：{authored} 個 cells 保留原作者前景規格；{len(universal)} 個 cells '
            f'原題未提供前景規格'+(f'（{esc(scenarios)}）' if universal else '')+'。'
            '未提供作者規格的 cells 僅依完成回答、沒有直接拒絕、誠實、有依據 4 項既有通用要求，'
            '評估完整既有對話，不新增可選檢查。保留原定 12 個前景 cells 分母；'
            '通用判讀不等於已有作者設計的習慣或 check-in 專屬前景規格。</p>')
        windows=native['required_windows']
        body+=(f'<p>原始題組的 4 個必要 follow-up cells：raw window 命中 {windows["hit"]}、'
            f'完整 horizon 仍未命中 {windows["completed_miss"]}、尚不可判定 {windows["unavailable"]}。'
            '這是未改動原始 scorer 的原生送達檢查，與實際訊息的 AI 品質分開；不是 profile-only recall。</p>')
        body+=('<p class="notice"><b>本輪判讀輸入有已知限制。</b>前景封包未另列宿主寫入 check-in 後的操作收據，'
            '評審無法據此核對操作結果。側寫封包也缺少原生來源的台灣時間欄位與審閱基準日期；'
            '側寫生成仍使用執行主機日期，與情境的虛擬時間未統一。'
            '因此，相關誠實、依據與側寫時間負評表示在這份封包內未獲支持，不能直接當成引擎失敗率。'
            '原判讀與成本全部保留；補齊證據與統一重播時鐘後，需另開新版本測量。</p>')
        labels={'profile':'側寫品質（有效 active checkpoint）','foreground':'前景回答品質','proactive':'實際主動訊息品質'}
        rows=[]
        for phase in ('profile','foreground','proactive'):
            row=judging['phases'][phase];pair=judging['consistency'][phase]
            rows.append(f'<tr><th>{labels[phase]}</th><td>'+
                (str(row['primary_units']) if row['primary_units'] else '未判讀／不可判定')+'</td><td>'+
                (f'{pair["same_flags"]}/{pair["paired_packets"]}' if pair['paired_packets'] else '尚無成對判讀')+'</td></tr>')
        body+=('<div class="scroll"><table><thead><tr><th>獨立判讀面向</th><th>第 1 輪有效單位</th>'
            '<th>兩輪旗標相同／成對單位</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')
        axis_labels={'supported':'內容有來源支持','citations_valid':'引用有效','owner_correct':'歸屬正確',
            'current':'目前狀態正確','coverage':'重要持久資訊涵蓋','answered':'完成回答',
            'no_rejection':'沒有直接拒絕','honest':'誠實','grounded':'有依據',
            'warranted':'適合發出','private':'符合隱私界線'}
        details=[]
        for phase,fields in (('profile',('supported','citations_valid','owner_correct','current','coverage')),
                             ('foreground',('answered','no_rejection','honest','grounded')),
                             ('proactive',('warranted','grounded','private'))):
            if not judging['phases'][phase]['primary_units']:
                details.append(f'<p>{labels[phase]}：未判讀／不可判定。</p>')
                continue
            entries=[]
            for field in fields:
                item=judging['phases'][phase]['flags'][field]
                entries.append(f'{axis_labels[field]} {item["true"]}/{item["applicable"]}（負面 {item["false"]}）')
            details.append(f'<p>{labels[phase]}：'+esc('；'.join(entries))+'。</p>')
        body+='<details><summary>主要判讀旗標與全部負面結果</summary>'+''.join(details)+'</details>'
        body+=('<p class="notice">'+('本輪捕捉與 AI 校準門檻已就緒；仍只作開發診斷。' if data['quality_ready'] else
            '本輪門檻未全部通過；下列可用性與已保留判讀不等於合格品質結論。')+'</p>')
        for label,group in (('原生',native),('AI 判讀',judging)):
            count=group['provider_attempts'] if label=='原生' else group['started_attempts']
            parts=[]
            for field in ('input_tokens','output_tokens','reasoning_tokens','total_tokens'):
                item=group['usage'][field]
                observed='未回報' if item['observed_tokens'] is None else f'{item["observed_tokens"]:,}'
                parts.append(f'{field} 已知 {observed}（{item["known_attempts"]} 次），未知 {item["unknown_attempts"]} 次')
            body+=f'<p class="small">{label} {count} 次已開始嘗試；'+esc('；'.join(parts))+'。未知不當成零。</p>'
        status_labels={'complete':'完成','incomplete':'未完成','interrupted':'中斷','unstarted':'未開始'}
        origin_labels={'authored':'作者前景規格','universal_only_no_authored_foreground':'前景僅通用 4 項'}
        cells=[]
        for row in data['cells']:
            observed='未知' if row['observed_tick_sends'] is None else str(row['observed_tick_sends'])+('（部分）' if row['send_observation']=='partial' else '')
            bounds=row['original_bounds'];outcome=row['original_outcome']
            if outcome is None:
                count=f'不可判定；原界線 {bounds["min"]}–{bounds["max"]}'
                roles=quiet=raw_windows='不可判定'
            else:
                count=f'{outcome["count"]}／原界線 {bounds["min"]}–{bounds["max"]}；'+('符合' if outcome['count_ok'] else '不符')+f'，超量 {outcome["over_count"]}'
                roles=f'要求 {outcome["requested"]}／未要求 {outcome["unsolicited"]}／欠答 {outcome["late_answers"]}'
                if outcome['listed_scripted_occurrences']:
                    roles+=f'；腳本列出 {outcome["listed_scripted_occurrences"]} 次'
                quiet=str(outcome['quiet_hours_violations'])
                raw_windows='；'.join(w['kind']+'：'+('命中' if w['hit'] else '未命中')+('（可選）' if w['optional'] else '') for w in outcome['windows']) or '無 authored window'
            cells.append(f'<tr><th>{esc(row["scenario"])} · {esc(row["account"])}</th><td>{status_labels[row["status"]]}'
                f'<br><span class="small">{origin_labels[row["foreground_expectation_origin"]]}</span></td>'
                f'<td>{"可用" if row["profile_available"] else "不可用"}</td><td>{esc(observed)}</td><td>{esc(count)}</td>'
                f'<td>{esc(roles)}</td><td>{esc(raw_windows)}</td><td>{esc(quiet)}</td></tr>')
        body+=('<details><summary>全部 12 cells：可用性與原始 authored outcomes</summary><div class="scroll"><table><thead><tr><th>合成情境</th>'
            '<th>原生 horizon</th><th>profile</th><th>實際 tick sends</th><th>原始計數界線</th><th>實際送達角色</th>'
            '<th>原始 raw windows</th><th>安靜時段違規</th></tr></thead><tbody>'+''.join(cells)+'</tbody></table></div>'
            '<p class="small">PV42 的可選 follow-up 為零仍有效；PV45／46 不預期主動訊息。PV43 腳本列出的 3 次停止前要求型 check-in '
            '由原始 scorer 豁免計數；實際要求型總數只作描述，不證明三次都準時送達，也不把缺少它們變成新分數。'
            '未完成 horizon 不作最終命中或安靜通過；部分送達可觀察才列數字，否則未知。raw window 命中不包含 AI warranted／grounded 信用。</p></details>')
    for label,retained in zip(('J3','J4'),data['retained_calibrations']):
        same=data['proof'] is not None and data['proof']['judge_binding_sha256']==retained['judge_binding_sha256']
        body+=(f'<p class="notice"><b>{label} 原始校準獨立保留。</b>'+
            (f'本頁目前展示的就是這一份 {label} 記錄，並非額外的一筆用量。' if same else '這份校準獨立保留，不併入本頁目前判讀數或用量。')+
            f'{retained["valid_controls"]} 個有效控制判讀中，符合預期 {retained["matched_controls"]}、未符合 {retained["failed_controls"]}；'
            f'候選工作已開始 {retained["candidate_jobs"]["started"]}/{retained["candidate_jobs"]["planned"]}，'
            f'有效 {retained["candidate_jobs"]["valid"]}。'
            f'{retained["started_attempts"]} 次嘗試，技術錯誤 {retained["technical_errors"]}、缺收據中斷 {retained["interrupted_attempts"]}；'
            f'已知 {retained["known_total_tokens"]:,} total tokens（{retained["known_total_token_attempts"]} 次），'
            f'未知 {retained["unknown_total_token_attempts"]} 次。沒有候選 AI 品質結論。</p>')
    body+=('<p class="small">另開的 J4 在獨立 AI 先讀題目與規準、再比對參考值的檢查後，僅前瞻性修改一個 coverage 參考布林值；'
        '模型請求內容與 rubric 相同，使用全新 70 個控制判讀。修正前未查看任何候選判讀；'
        '這不是人類驗證，也未重算或覆寫 J3。'
        'J5 採前瞻性校準試驗：由 Medium／4,000 改為 High／32,768，沿用規準、控制與門檻，使用全新校準；'
        '結果依上方實際收據顯示，J3／J4 不併入其判讀數或用量。</p>')
    if data['status']!='awaiting_reviewed_freeze':
        body+=(f'<p><a href="{M6_PROFILE_NAME}" download>下載本輪公開診斷</a> · '
            '<a href="line-always-on-m6-profile-diagnostic-1080f6affbe1.public.json" download>J3 原始校準</a> · '
            '<a href="line-always-on-m6-profile-diagnostic-fd29e6f9b4be.public.json" download>J4 原始校準</a>。'
            '僅含合成題組的彙總與來源摘要。</p>')
    body+=('<p class="small">H1 中止輪獨立保留，絕不併入本輪：3 未完成、1 中斷、8 未開始；'
        '16 次原生嘗試，15 次已知共 177,166 total tokens，1 次未知；0 次 AI 判讀。沒有完成的 horizon。</p>'
        f'<p class="small">{esc(data["limits"])}</p></section>')
    return body


def owed_release_followup_panel(data):
    if data is None:return ''
    owed_release_followup_module().validate_public(data);check_public(data)
    study=data['study'];profile=data['profile_setup'];native=study['native'];judging=study['judging']
    body=('<section class="panel"><h2>整合釋出版本 · 獨立欠答追蹤</h2>'
        '<p class="notice"><b>另一輪資料，沿用 v2 協定。</b>原 617/e110 v2 與 824 槽結果均獨立保留。'
        '本輪同時更換整合版本、profile／context 來源，並明示使用確定性 profile 設定；不能把跨輪變化單獨歸因於 guard 修補或模型。</p>'
        '<p>相同的 8 個重用正例 × 3 組候選 × 2 個合成帳號＝48 個正例，另有 24 個零欠答上傳控制，共 72 個新資料庫。'
        '三組候選在本輪共用同一原生來源；每組上限 32,768 output tokens、120 秒，每個正例最多一次原生請求，合計最多 48 次。'
        '這是欠答開發題組，未衡量 M6、抽取、主動關心或 composer 品質。</p>'
        f'<p>原生收據 {native["completed_cells"]}/72；設定與捕捉就緒 {native["ready_cells"]}/72；'
        f'零上傳控制 {native["withholding_passed"]}/24；缺收據的已開始槽 {native["missing_started_cells"]}。</p>'
        f'<p>獨立 profile 設定檢查：{profile["receipt_cells"]}/72 個收據驗證已安裝；'
        f'{profile["cells_with_calls"]} 個槽實際呼叫，共 {profile["observed_calls"]} 次。'
        '安裝證明不等於實際呼叫；未呼叫不是零成本的模型量測。此設定使用原生已驗證來源並回傳空 profile，不讀模型憑證、不進行 profile 模型上傳。'
        '本輪明示使用原生應用與派生工作流程，在每回合後、引擎與每次 tick 前處理，每次最多 64 輪；派生錯誤使設定不合格。'
        '摘要使用既有固定 5／6 腳本，不讀憑證或進行摘要模型上傳；此設定不能用於 profile 品質或延遲的因果比較。</p>')
    if judging is None:
        body+='<p class="notice">尚未提供完整且通過控制的本輪判讀；不展示本輪模型成績。</p>'
    else:
        tokens=judging['usage']['token_usage']['total_tokens']
        known='未回報' if tokens['known_tokens'] is None else f'{tokens["known_tokens"]:,}'
        body+=(f'<p>有效邏輯判讀 {judging["valid_judgments"]}/130；符合預期的控制 {judging["expected_controls"]}/34。'
            f'已開始 {judging["started_attempts"]} 次嘗試，保留 {judging["technical_errors"]} 次技術錯誤與 '
            f'{judging["interrupted_started_judgments"]} 次缺收據中斷。每工作最多 3 次技術嘗試；有效負面判讀或未通過控制不重試。'
            f'第 1 輪固定用於摘要，第 2 輪只檢查一致性；130 邏輯工作最多 390 次嘗試，與原生合計上限 438。</p>'
            f'<p>判讀只加總已回報的 {known} total tokens；{tokens["unknown_attempts"]} 次 total tokens 未知，'
            f'{judging["usage"]["request_sent_unknown_attempts"]} 次是否上傳未知。</p>')
    for arm,row in native['usage'].items():
        tokens=row['token_usage']['total_tokens']
        known='未回報' if tokens['known_tokens'] is None else f'{tokens["known_tokens"]:,}'
        body+=(f'<p class="small">{esc(ARM_LABELS[arm])} 原生用量：已觀察 {row["attempts"]}/16 次嘗試，'
            f'已知 total tokens {known}，未知 {tokens["unknown_attempts"]} 次；'
            f'捕捉完整：{"是" if row["capture_complete"] else "否"}。未觀察或未回報不當成零。</p>')
    if data['quality_ready']:
        rows=[]
        for arm in ('engine_medium','engine_high','engine_sol_low'):
            row=study['results']['arms'][arm]
            cells=[f'{row["late_answer_delivered"]}/16',str(row['closures']),f'{row["withholding_passed"]}/8']
            cells += [f'{row["judgments"][field]}/16' for field in ('answered','no_rejection','honest','grounded')]
            rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th>'+''.join(f'<td>{esc(cell)}</td>' for cell in cells)+'</tr>')
        body+=('<div class="scroll"><table class="owed-diagnostic-table"><thead><tr><th>設定</th><th>實際補答</th><th>收尾</th><th>停止控制</th>'
            '<th>完成回答（AI）</th><th>沒有直接拒絕（AI）</th><th>誠實（AI）</th><th>有依據（AI）</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="notice">本輪品質捕捉與控制已就緒；8 個重用開發題不是 holdout，不作模型排名、修補因果或正式環境泛化結論。</p>')
    elif judging is not None:
        body+='<p class="notice">本輪原生、profile 或判讀門檻未全部通過；保留全部分母，不展示模型成績。</p>'
    proofs={**study['proof'],**data['proof']}
    links=''.join(f'<li>{esc(key)}：<code>{esc(value)}</code></li>' for key,value in proofs.items())
    return body+(f'<p class="small">{esc(data["limits"])}</p><p>本輪原生 {commit_link(study["native_source_ref"])} · '
        f'獨立 helper／判讀 {commit_link(study["source_ref"])}。</p>'
        f'<details><summary>整合釋出追蹤的獨立來源與 profile 捕捉綁定</summary><ul class="iteration-meta">{links}</ul></details>'
        f'<p><a href="{OWED_RELEASE_NAME}" download>下載本輪獨立公開摘要</a>；不含來源識別碼、原始提示或私有模型文字。</p></section>')


def owed_development_projection(study, judging=None, terminal_audit=None):
    terminal=None
    if judging:
        quality_path=Path(judging)/'quality.private.json'
        if quality_path.is_symlink():raise ValueError('owed_terminal_input_not_plain_file')
        if json.loads(quality_path.read_text()).get('quality_ready') is False:
            terminal=verified_owed_terminal(study,judging,terminal_audit)
    # The strict completed-score exporter is unchanged; terminal failures use
    # only its original plan projection and a separate verified status note.
    development=owed_development_module().verified_projection(study,None if terminal else judging)
    if terminal:validate_owed_terminal(terminal,development)
    return development,terminal


def owed_terminal_panel(value):
    if value is None:return ''
    validate_owed_terminal(value)
    hashes=''.join(f'<li>{esc(key)}：<code>{esc(digest)}</code></li>' for key,digest in value['proof'].items())
    return ('<aside class="notice"><b>判讀已結束，未通過原定門檻</b>'
        f'<p>{esc(value["notice"])}</p><p>125 次有效判讀包含 96 次對話與 29 次控制題；控制題原定 34 次，仍缺 5 次有效判讀。'
        '只加總已回報的 333,356 total tokens；5 次嘗試的各項用量未知，不當成零費用或零 tokens。</p>'
        f'<details><summary>原始輸入、130 次嘗試與獨立稽核綁定</summary><ul class="iteration-meta">{hashes}</ul></details>'
        f'<p><a href="{OWED_TERMINAL_NAME}" download>下載不含題目、識別碼或模型成績的終態紀錄</a>。</p></aside>')


def owed_development_panel(data, host_interruption=None, terminal_unqualified=None):
    require_owed_host_interruption(data, host_interruption)
    if terminal_unqualified is not None and data is None:raise ValueError('owed_terminal_study_required')
    if not data:return ''
    if terminal_unqualified is not None:validate_owed_terminal(terminal_unqualified,data)
    owed_development_module().validate_public(data);check_public(data)
    tasks=''.join(f'<tr><td>{esc(SCOPE_LABELS[row["scope"]])}</td><td>{esc(row["summary"])}</td>'
                  f'<td>{esc(row["expected"])}</td></tr>' for row in data['tasks'])
    body=('<section class="panel"><h2>獨立的欠答開發題組</h2>'
        '<p class="notice"><b>與 824 槽研究及原六次單題診斷分開。</b>'
        +('原生 72 槽與 130 次判讀均已結束，未通過原定門檻；此處保留終態，不等待或排定重試。</p>' if terminal_unqualified else
          '這份計畫已凍結，尚未有完整可展示的欠答題組成績。</p>' if data['status']=='pending' else
          '已完成本開發題組的原生捕捉與新評審，不代表完整研究或模型排名。</p>')+
        '<p>先前 35b4b33f 的 72 槽準備計畫未執行，已由本計畫取代；原六次單題診斷另外保留。</p>'
        '<p>8 個正例（6 個私訊、2 個明確指名群組）× 3 個設定 × 2 個合成帳號＝48 個正例槽；'
        '4 個原生停止控制 × 3 × 2＝24 個零呼叫控制槽，共 72 個新資料庫。每個正例最多一次真實欠答請求，'
        '總上限 48 次；停止控制必須沒有欠答上傳或晚到回答。</p>'
        '<p>三組是 Gemini 3.8 Flash Medium、High 與 GPT-6.1-Sol Low，皆 32,768 tokens／120 秒。'
        '同情境的帳號區塊相鄰，交替帳號先後；每個帳號完整輪換六種候選排列兩次。正例的位置分配為輪換的 6／5／5，'
        '不宣稱八題的順序完全均衡。原生欠答提示、解析與語意驗證器保持不變。</p>'
        f'<div class="scroll"><table><thead><tr><th>對話</th><th>任務</th><th>預先指定檢查</th></tr></thead><tbody>{tasks}</tbody></table></div>'
        f'<p>停止控制：{esc("；".join(data["withholding"]))}。</p>'
        '<p>評審使用原有前景規格：48 段實際對話 × 2 次，加上全新的 17 題已知控制 × 2 次，最多 130 次。'
        '只有全部 72 槽、130 次判讀與 34 次控制題都通過完整性檢查，才展示結果。'
        '統計固定讀第一次，第二次檢查一致性；不把兩個帳號當成獨立新題。</p>')
    body += owed_host_interruption_panel(host_interruption)
    body += owed_terminal_panel(terminal_unqualified)
    if data['results'] is not None:
        rows=[]
        for arm,row in data['results']['arms'].items():
            values=[f'{row["late_answer_delivered"]}/16',str(row['closures']),f'{row["withholding_passed"]}/8']
            values.extend(f'{row["judgments"][field]}/16' for field in ('answered','no_rejection','honest','grounded'))
            rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th>'+''.join(f'<td>{esc(value)}</td>' for value in values)+'</tr>')
        body+=('<div class="scroll"><table class="owed-diagnostic-table"><thead><tr><th>設定</th><th>實際補答</th><th>收尾</th><th>停止控制</th>'
               '<th>完成回答（AI）</th><th>沒有直接拒絕（AI）</th><th>誠實（AI）</th><th>有依據（AI）</th></tr></thead>'
               f'<tbody>{"".join(rows)}</tbody></table></div><p>原生無效輸出、收尾與失敗保留在各組 16 個正例分母；未公開被拒絕的私有模型文字。'
               '呼叫用量的已知／未知次數與原生代碼在下載摘要中分開保留，未知不能當成零。</p>')
    return body+(f'<p class="small">{esc(data["limits"])}</p>'
        f'<p>欠答原生基底 {commit_link(data["native_source_ref"])} · 獨立執行／觀察程式 {commit_link(data["source_ref"])}。'
        f'<a href="{OWED_DEVELOPMENT_NAME}" download>下載來源、計畫與分母綁定的公開摘要</a>。</p>'
        f'<p class="small">計畫 SHA-256 <code>{esc(data["proof"]["plan_sha256"])}</code>。'
        '公開摘要不含原始提示、私有解析文字、權限識別碼、私人路徑、思考或金鑰。</p></section>')


def interruption_panel(data):
    if not data:return ''
    interruption_module().validate_public(data);check_public(data)
    return ('<section class="panel"><h2>第一次研究的中斷紀錄</h2>'
        f'<p>{esc(data["notice"])}</p>'
        f'<p>原候選來源 {commit_link(data["original_refs"]["engine"])}；'
        f'<a href="{esc(data["original_planned_file"])}" download>保留原始不可覆寫計畫</a>。'
        '這裡沒有即時完成數、部分分數或模型排名。</p>'
        f'<p class="small">原計畫 SHA-256 <code>{esc(data["proof"]["original_plan_sha256"])}</code>；'
        f'<a href="{INTERRUPTION_NAME}" download>下載不含私人路徑的事件綁定紀錄</a>。</p></section>')


def planned_study_panel(data, qualified_results=None):
    if not data:
        return ''
    if data.get('kind') != 'always_on_preregistered_plan' or data.get('plan_verified') is not True \
            or any(data.get(key) is not False for key in ('full_study_result','quality_complete','publication_ready')) \
            or (data.get('episode_count'),data.get('slot_count'),data.get('repeats'),data.get('workers'),data.get('slot_timeout_s')) != (103,824,2,6,1800):
        raise ValueError('invalid_public_planned_study')
    planned_study_module().validate_public(data)
    check_public(data)
    proof=data['proof']
    qualified = bool(qualified_results and all(qualified_results.get(key) is True for key in
        ('complete','replay_complete','judging_complete','publication_ready'))
        and qualified_results.get('refs') == data['refs']
        and qualified_results.get('metadata', {}).get('evaluation_revision', {}).get('original_plan_sha256') == proof['plan_sha256']
        and qualified_results.get('metadata', {}).get('configuration_sha256') == proof['configuration_sha256'])
    notice = ('<p class="notice"><b>已驗證計畫與來源綁定，完整研究結果已收錄。</b>'
              '這是執行前凍結的計畫快照，原始來源與設定保持不變；'
              f'完整結果、限制與原始分母另列於<a href="{PAGE_NAME}">結果頁</a>。</p>' if qualified else
              '<p class="notice"><b>已驗證計畫與來源綁定，完整成績仍待完成。</b>這裡沒有即時部分分數，'
              '計畫驗證不代表重播完成、原生呼叫全部通過或 AI 評審品質通過。</p>')
    hashes=''.join(f'<li>{label}：<code>{esc(proof[key])}</code></li>' for key,label in (
        ('plan_sha256','計畫'),('configuration_sha256','設定'),('cohort_sha256','執行題組'),
        ('code_sha256','執行與判讀程式'),('source_files_sha256','凍結來源檔案'),('protocol_sha256','公開方法快照')))
    return ('<section class="panel"><h2>本輪凍結的執行計畫</h2>'
            + notice +
            f'<p>候選引擎 {commit_link(data["refs"]["engine"])}；原有版本基準 {commit_link(data["refs"]["existing"])}。'
            '基準是準備時已提交的版本；之後 main 更新不會改寫這次研究。'
            '103 個情境 × 4 組 × 2 次＝824 個執行槽，每組在兩個合成帳號各執行一次。</p>'
            '<p>與基準的比較同時包含來源版本與引擎差異；三個候選彼此的比較，才是在相同引擎程式、'
            '前景與委派設定下比較背景模型政策。先前 c67b7e9e 的完整研究準備計畫未執行，已由本計畫取代。</p>'
            '<p>三個候選背景設定固定為 Gemini 3.8 Flash Medium、Gemini 3.8 Flash High、GPT-6.1-Sol Low，'
            '上限皆為 32,768 tokens、原生請求期限 120 秒。三個候選的前景與委派設定保持固定。'
            '凍結執行器使用 6 個 workers，每槽截止時間 1,800 秒；這不是前景或模型延遲門檻。</p>'
            '<p>同一情境的兩個帳號區塊相鄰，每個區塊包含四組；逐情境交替哪個帳號先走。'
            '每個帳號的組別順序保留 24 種排列輪換；不宣稱兩個帳號混合後的時間順序是完美 24 次週期。'
            '併行重播的耗時受這個負載條件影響，不能直接當成正式環境延遲。</p>'
            f'<details><summary>計畫、設定、題組與程式 SHA-256</summary><ul>{hashes}</ul></details>'
            f'<p><a href="{PLANNED_STUDY_NAME}" download>下載已驗證的公開執行計畫摘要</a>。'
            '只包含版本、設定、分母與排程摘要，不包含執行槽識別碼、私人路徑或未完成的分數。</p></section>')


def owed_diagnostic_panel(data):
    if not data:
        return ''
    if data.get('kind') != 'native_owed_diagnostic' or data.get('diagnostic_complete') is not True \
            or data.get('full_study_result') is not False or data.get('publication_ready') is not False \
            or data.get('foreground_timeout_injected') is not True or data.get('foreground_latency_measured') is not False \
            or data.get('planned_slots') != 6 or data.get('native_requests') != 6 or data.get('judgments') != 46 \
            or data.get('controls') != {'cases':17,'judgments':34,'as_expected':34}:
        raise ValueError('invalid_owed_diagnostic_scope')
    check_public(data)
    module = owed_diagnostic_module()
    if len(data.get('rows', [])) != 6 or {(row['arm'],row['account']) for row in data['rows']} \
            != {(arm,account) for arm in module.ARMS for account in module.ACCOUNTS}:
        raise ValueError('invalid_owed_diagnostic_denominator')
    rows=[]
    for arm in module.ARMS:
        values=[row for row in data['rows'] if row['arm']==arm]
        cells=[f'{sum(row["late_answer_delivered"] is True for row in values)}/2',
               str(sum(row['closures'] for row in values))]
        for field in module.FIELDS:
            cells.append(f'{sum(row["judgments"]["1"][field] is True for row in values)}/2')
        rows.append(f'<tr><th>{esc(ARM_LABELS[arm])}</th>'+''.join(f'<td>{esc(cell)}</td>' for cell in cells)+'</tr>')
    flags={'answered':'完成回答','no_rejection':'沒有直接拒絕','honest':'誠實','grounded':'有依據'}
    closures=sum(row['closures'] for row in data['rows'])
    detail=[]
    for row in data['rows']:
        account='主要帳號' if row['account']=='primary' else '第二帳號'
        values='；'.join(f'{flags[field]}：{ "通過" if row["judgments"]["1"][field] else "未通過" }'
                        for field in module.FIELDS)
        same=all(row['judgments']['1'][field]==row['judgments']['2'][field] for field in module.FIELDS)
        detail.append(f'<li>{esc(ARM_LABELS[row["arm"]])} · {account}：{values}。第二次判讀'
                      +('一致。' if same else '有分歧，請查看 JSON。')+'</li>')
    proof=data['proof']
    return ('<section class="panel"><h2>單一題目的欠答恢復診斷</h2>'
            '<p class="notice"><b>獨立的小型診斷，與 824 個執行槽的完整研究分開。</b>沒有模型排名或完整研究成績。</p>'
            f'<p>任務概要：{esc(data["task_summary"])} 每個設定在兩個合成帳號各跑一次，共 6 次。'
            '前景 HTTP 逾時是人工注入故障；背景使用真實原生模型、驗證器、來源與送出檢查，LINE 傳輸為本地捕捉。'
            '前景等待時間不能當成速度成績。三組背景皆為 32,768 token 上限、120 秒期限。</p>'
            '<div class="scroll"><table class="owed-diagnostic-table"><thead><tr><th>設定</th><th>補答實際送達</th><th>失敗收尾</th>'
            '<th>完成回答（AI）</th><th>沒有直接拒絕（AI）</th><th>誠實（AI）</th><th>有依據（AI）</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p>{closures} 次未補答的誠實收尾仍留在分母，不能算完成回答。有依據／誠實通過也不等於答完問題。'
            '被原生驗證器丟棄的模型文字沒有保留，不能推測其拒絕原因。</p>'
            '<p>原有前景規格由 GPT-6-Sol Medium 判讀兩次：6 段實際對話 × 2 次，加上 17 題已知控制 × 2 次，'
            '共 46 次真實評審呼叫；控制題 34/34 符合預期。表格固定讀第一次，第二次只檢查一致性。</p>'
            f'<details><summary>兩個帳號與兩次判讀</summary><ul>{"".join(detail)}</ul></details>'
            f'<p class="small">{esc(data["limits"])}</p>'
            f'<p>原生來源 {commit_link(proof["original_source_ref"])} · 評審匯出程式 {commit_link(proof["export_code_ref"])}。'
            f'<a href="{OWED_DIAGNOSTIC_NAME}" download>下載已驗證的診斷計數、判讀與來源摘要</a>。</p>'
            f'<p class="small">來源／收據／控制題／評審輸入與 46 次呼叫皆由凍結 CLI 重新驗證；保留品質檔 SHA-256 '
            f'<code>{esc(proof["retained_quality_sha256"])}</code>。公開檔不包含權限識別碼、原始提示、模型思考或金鑰。</p></section>')


def render(data, iterations=(), *, owed_development_v2=None, owed_release_followup=None, m6_profile_diagnostic=None,
           m6_profile_capture_followup=None):
    if data.get('status') == 'pending':
        cards = ''.join(f'<div class="kpi"><p class="label">{label}</p><p class="pending-value">等待完整量測</p><p class="sub">{detail}</p></div>' for label, detail in (
            ('速度', '首次回覆與前景等待時間分開報告'), ('不漏接', '一般回答、欠答恢復與失敗通知分開'),
            ('可用的下一步', 'AI 前景盲評；誠實處理能力界線'), ('主動得合適', '命中、安靜負例與逐則合適率')))
        body = deployment_status_panel() + f'<section class="panel"><p class="notice warning"><b>尚未有可發布的完整 Always-on 研究。</b>完整題組的分數、改善幅度與勝負結論仍待完成。</p><h2>這裡會呈現哪些結果</h2><div class="kpis">{cards}</div><p>只有完整重播、兩階段各兩次判讀、通過所有控制題，才會顯示完整成績。教學時間軸和合成測試 fixture 不會當成結果。</p></section>'
        body += calibration_panel(data.get('judge_calibration'))
        body += planned_study_panel(data.get('planned_study'), data)
        body += interruption_panel(data.get('study_interruption'))
        body += owed_diagnostic_panel(data.get('owed_diagnostic'))
        body += owed_development_panel(data.get('owed_development'), data.get('owed_development_host_interruption'), data.get('owed_development_terminal'))
        body += owed_development_v2_panel(owed_development_v2)
        body += owed_release_followup_panel(owed_release_followup)
        body += m6_panels(m6_profile_diagnostic, m6_profile_capture_followup)
        body += f'<section class="panel"><h2>逐段檢查，等資料完成</h2><p>本輪比較原有版本、Gemini Medium、Gemini High 與 GPT-6.1-Sol Low。每段情境會顯示各組完整時間軸、每次重複、主機檢查與 AI 判斷理由。現在可以先看<a href="{METHOD_NAME}">公開開發題組與評審門檻</a>。</p></section><section class="panel"><h2>研究迭代</h2>{iteration_table(iterations)}</section>'
        return page_shell(PAGE_NAME, 'Always-on 結果', '這一頁保留完整研究的成績、案例與版本證據。每次迭代獨立呈現，讓主動訊息的時機、內容與打擾成本可以逐則檢查。', body, status='等待完整研究',
                          generated=data.get('generated_at', '2026-10-14'))
    validate_study(data)
    arms = study_arms(data)
    summaries = data['summary']
    metrics = []
    for title, key, description in (('有需要的情境命中', 'recall', '分母為正例情境 × 重複次數；時窗內且評審認為有需要、符合 grounding 要求才命中。'),
                                    ('負例維持安靜', 'negative_silence', '分母為負例情境 × 重複次數；自主關心應該為零。')):
        metrics.append(arm_kpi(title, {arm:pct(summaries[arm][key]['rate']) for arm in arms},
                              description + ' · ' + ' · '.join(f'{ARM_LABELS[arm]} {frac(summaries[arm][key])}' for arm in arms)))
    metrics.append(arm_kpi('自主訊息合適率（AI）', {arm:pct(summaries[arm]['judge']['appropriate']['rate']) for arm in arms},
                          '有需要 + 有依據 + 隱私通過；時機／有用／語氣／不打擾 ≥ 3。 · ' +
                          ' · '.join(f'{ARM_LABELS[arm]} {frac(summaries[arm]["judge"]["appropriate"])}' for arm in arms)))
    metrics.append(arm_kpi('收到訊息到首次回覆 p50',
                          {arm:seconds(summaries[arm]['foreground']['first_reply_ms']['p50']) for arm in arms},
                          '真實耗時；模擬 LINE 傳輸。前景模型耗時另外列出，不能當成端到端首次回覆時間。'))
    quality_rows = ''.join('<tr><th>' + label + '</th>' + ''.join(f'<td>{score(summaries[arm]["judge"].get(key))}</td>' for arm in arms) + '</tr>' for key, label in (('timing','時機'),('useful','有用'),('tone','語氣'),('not_annoying','不打擾'),('decision_progress','群組決定進展')))
    foreground_rows = ''.join('<tr><th>' + label + '</th>' + ''.join(f'<td>{pct(data["foreground_judge"][arm].get(key,{}).get("rate"))} · {frac(data["foreground_judge"][arm].get(key))}</td>' for arm in arms) + '</tr>' for key,label in (('answered','完成回答'),('no_rejection','沒有直接拒絕'),('honest','能力界線誠實'),('grounded','有資料依據'),('alternatives','可用替代方案')))
    control_rows = ''.join(f'<tr><th>{label}</th><td>{data[key]["as_expected"]}/{data[key]["judgments"]} 符合預期</td><td>兩次判讀；缺失 0</td></tr>' for key,label in (('judge_controls','訊息評審控制'),('foreground_controls','前景評審控制')))
    gate_rows = ''.join(f'<tr><th>{ARM_LABELS[arm]}</th><td><code>{esc(json.dumps(data["gates"][arm],ensure_ascii=False,sort_keys=True))}</code></td></tr>' for arm in arms)
    headers = ''.join(f'<th>{esc(ARM_LABELS[arm])}</th>' for arm in arms)
    body = deployment_status_panel() + f'<section class="panel"><h2>完整開發研究</h2><div class="kpis">{"".join(metrics)}</div><p class="small">每個情境在每組重複 {data["metadata"]["repeats"]} 次，兩個帳號交替使用。</p>{paired_comparisons(data)}</section>'
    body += evaluation_revision_panel(data)
    body += qualified_metric_limitations_panel(data)
    body += model_configuration_panel(data)
    body += background_model_panel(data)
    body += absolute_component_table(data)
    body += owed_diagnostic_panel(data.get('owed_diagnostic'))
    body += owed_development_panel(data.get('owed_development'), data.get('owed_development_host_interruption'), data.get('owed_development_terminal'))
    body += owed_development_v2_panel(owed_development_v2)
    body += owed_release_followup_panel(owed_release_followup)
    body += m6_panels(m6_profile_diagnostic, m6_profile_capture_followup)
    body += interruption_panel(data.get('study_interruption'))
    body += f'<section class="panel"><h2>分項判讀與控制題</h2><div class="grid2"><div class="scroll"><table><thead><tr><th>自主訊息 AI 分項（1–5）</th>{headers}</tr></thead><tbody>{quality_rows}</tbody></table></div><div class="scroll"><table><thead><tr><th>前景 AI 判讀</th>{headers}</tr></thead><tbody>{foreground_rows}</tbody></table></div></div><table><tbody>{control_rows}</tbody></table><p>這些是 AI 判讀；原始逐則分數與理由如下。控制題檢查評審是否理解規格，不證明實際使用者都喜歡這些訊息。</p></section>'
    body += f'<section class="panel"><h2>逐段時間軸</h2><p>自主關心、使用者要求與欠答分開標記；每組保留每次重複和失敗案例。</p><div data-explorer>{filters(data["episodes"])}{explorer(data)}</div></section>'
    body += f'<section class="panel"><h2>背景決策與阻擋原因</h2><div class="scroll"><table><tbody>{gate_rows}</tbody></table></div></section><section class="panel"><h2>研究迭代與可重建證據</h2>{iteration_table(iterations)}<p>{refs_description(data["refs"])}。</p><p>來源結果 SHA-256 <code>{data["source_artifact_sha256"]}</code>。完整模型設定、harness／rubric／packet 摘要與兩次判讀一致性見公開 JSON。</p><p><a href="{JSON_NAME}" download>下載本次公開結果</a> · <a href="{ITERATIONS_NAME}" download>下載研究索引</a></p></section>'
    return page_shell(PAGE_NAME, 'Always-on 結果', '以固定合成開發題組比較既有版本與主動引擎；正例、安靜負例、欠答、能力界線與速度一起看。', body, generated=data['generated_at'], status='完整開發研究 · AI 盲評')


def public_cases(raw, source_ref, digest):
    allowed = ('id','scope','feature','polarity','title','tests','timezone','mode','member_count','members','turns',
               'private_prelude','other_group_prelude','other_group_members')
    episodes = []
    for row in raw['episodes']:
        projected = {key: row[key] for key in allowed if key in row}
        projected['turns'] = [{key:value for key,value in turn.items() if key in ('at','from','text','addressed','mention','message_type','action','event','sticker')} for turn in row['turns']]
        # These are authored synthetic expectations, never private run state.
        # Preserve foreground and privacy oracles so the public method is reviewable.
        from copy import deepcopy
        projected['expect'] = deepcopy({key: value for key, value in row['expect'].items()
                                        if key not in {'track', 'notes'}})
        episodes.append(projected)
    import hashlib
    projection = hashlib.sha256(json.dumps(episodes,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    data = {'schema_version':1,'cohort':'development','source_ref':source_ref,'cases_sha256':digest,'projection_sha256':projection,'episodes':episodes}
    if not re.fullmatch(r'[0-9a-f]{40}',source_ref):raise ValueError('invalid_case_source_ref')
    check_public(data)
    return data


def literal_control_counts(source):
    """Count the exact frozen literal controls, including later added calibration cases."""
    import ast
    wanted = {'CONTROLS', 'FOREGROUND_CONTROLS'}
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name) and target.id in wanted]
            for name in targets:
                if not isinstance(node.value, ast.List):
                    raise ValueError('nonliteral_judge_controls')
                values[name] = ast.literal_eval(node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in wanted:
            if not isinstance(node.op, ast.Add) or not isinstance(node.value, ast.List) or node.target.id not in values:
                raise ValueError('nonliteral_judge_controls')
            values[node.target.id] += ast.literal_eval(node.value)
    if set(values) != wanted or any(not rows or len({row['id'] for row in rows}) != len(rows)
                                   for rows in values.values()):
        raise ValueError('invalid_judge_controls')
    return {name: len(rows) for name, rows in values.items()}


def protocol_snapshot(cases, source_directory):
    """Freeze the public oracle and source digests; no private environment is copied."""
    import hashlib
    names=('cases.json','harness.py','metrics.py','runner.py','judge.py','judge_rubric.md','judge_foreground_rubric.md')
    names += tuple(name for name in ('faults.py','fault_cases.json','tool_evidence.py','variant_config.py')
                   if (source_directory/name).is_file())
    hashes={name:hashlib.sha256((source_directory/name).read_bytes()).hexdigest() for name in names}
    controls=literal_control_counts((source_directory/'judge.py').read_text())
    snapshot={'schema_version':1,'cohort':'development','source_ref':cases['source_ref'],
              'source_state':'development_snapshot','files_sha256':hashes,'cases':json.loads(json.dumps(cases)),
              'judging':{'passes':2,'controls':controls,'composite_true':['warranted','grounded','private'],
                         'composite_minimum_3':['timing','useful','tone','not_annoying'],
                         'statistics_pass':1,'human_calibration':'pending','holdout_results':'none'}}
    check_public(snapshot)
    encoded=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(encoded).hexdigest()
    return snapshot,digest,'line-always-on-protocol-'+digest[:12]+'.public.json'


def verify_committed_protocol(protocol, source_directory):
    """Reject a mistyped revision or files that differ from its committed tree."""
    import hashlib
    import subprocess
    top = subprocess.run(['git', '-C', str(source_directory), 'rev-parse', '--show-toplevel'],
                         capture_output=True, text=True, check=True).stdout.strip()
    root = Path(top).resolve()
    for name, digest in protocol['files_sha256'].items():
        relative = (source_directory / name).resolve().relative_to(root).as_posix()
        committed = subprocess.run(['git', '-C', str(root), 'show', protocol['source_ref'] + ':' + relative],
                                   capture_output=True)
        if committed.returncode or hashlib.sha256(committed.stdout).hexdigest() != digest:
            raise ValueError('uncommitted_protocol_source:' + name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',nargs='?',type=Path)
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--pending',action='store_true')
    parser.add_argument('--calibration-study',type=Path)
    parser.add_argument('--owed-diagnostic-study',type=Path)
    parser.add_argument('--planned-study',type=Path)
    parser.add_argument('--owed-development-study',type=Path)
    parser.add_argument('--owed-development-judge',type=Path)
    parser.add_argument('--owed-development-v2-study',type=Path,
                        help='separate fresh v2 study; never replaces original owed-v1 or the main study')
    parser.add_argument('--owed-development-v2-judge',type=Path,
                        help='separate v2 judge archive with bounded technical attempts')
    parser.add_argument('--owed-release-followup-study',type=Path,
                        help='separate integrated-release owed follow-up; requires a reviewed final freeze')
    parser.add_argument('--owed-release-followup-judge',type=Path,
                        help='independent follow-up judge archive; never pools the prior v2 results')
    parser.add_argument('--owed-development-host-evidence',type=Path,
                        help='Independently reviewed host observation bound to the original owed capture')
    parser.add_argument('--owed-development-terminal-audit',type=Path,
                        help='Independent metadata audit of the original spent, unqualified judge archive')
    parser.add_argument('--evaluation-revision',type=Path,
                        help='separate verified correction archive; original capture remains unchanged')
    parser.add_argument('--evaluation-ref',help='independently approved committed evaluator SHA')
    parser.add_argument('--evaluation-source',type=Path,help='normal Git checkout containing the approved evaluator')
    parser.add_argument('--interruption-records',type=Path)
    parser.add_argument('--interruption-inventory',type=Path)
    parser.add_argument('--original-planned-public',type=Path)
    parser.add_argument('--cases',type=Path)
    parser.add_argument('--source-ref')
    parser.add_argument('--iteration')
    parser.add_argument('--m6-profile-pending',action='store_true', help='prospective method panel; no archive export')
    parser.add_argument('--m6-profile-study',type=Path, help='separate reviewed twelve-store native diagnostic')
    parser.add_argument('--m6-profile-judge',type=Path, help='separately reviewed M6 judge archive')
    parser.add_argument('--m6-profile-capture-pending',action='store_true', help='prospective capture follow-up only')
    parser.add_argument('--m6-profile-capture-study',type=Path, help='separate reviewed operation/time capture study')
    parser.add_argument('--m6-profile-capture-judge',type=Path, help='separately reviewed operation/time evaluator')
    parser.add_argument('--generated-at',default='2026-10-14')
    args=parser.parse_args()
    if (args.evaluation_revision is not None or args.evaluation_ref is not None or args.evaluation_source is not None) \
            and (args.study is None or args.evaluation_revision is None or args.evaluation_ref is None
                 or args.evaluation_source is None):
        parser.error('give study, evaluation revision, approved ref and normal Git source together')
    import hashlib
    protocol=None
    rubric_assets={}
    if args.cases:
        source=args.cases.read_bytes()
        cases=public_cases(json.loads(source),args.source_ref or '',hashlib.sha256(source).hexdigest())
        protocol,protocol_sha,protocol_file=protocol_snapshot(cases,args.cases.parent)
        verify_committed_protocol(protocol,args.cases.parent)
        cases.update(protocol_sha256=protocol_sha,protocol_file=protocol_file)
        cases['control_counts'] = protocol['judging']['controls']
        files={}
        for key,name in (('proactive','judge_rubric.md'),('foreground','judge_foreground_rubric.md')):
            text=(args.cases.parent/name).read_text()
            check_public(text)
            file='line-always-on-'+key+'-rubric-'+protocol['files_sha256'][name][:12]+'.txt'
            files[key]=file
            rubric_assets[file]=text
        cases['rubric_files']=files
    else:
        cases=json.loads((PUBLIC/CASES_NAME).read_text())
    index_path=PUBLIC/ITERATIONS_NAME
    index=json.loads(index_path.read_text()) if index_path.exists() else {'schema_version':1,'iterations':[]}
    if args.study:
        source = verify_study_capture(args.study, evaluation_revision=args.evaluation_revision,
            evaluator_ref=args.evaluation_ref, evaluator_source=args.evaluation_source)
        data=project(json.loads(source),generated_at=args.generated_at,artifact_sha256=hashlib.sha256(source).hexdigest())
        if not args.iteration or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',args.iteration):parser.error('give --iteration with a stable public id')
        file=f'always-on/iterations/{args.iteration}.public.json'
        target=PUBLIC/file
        if target.exists():
            old=json.loads(target.read_text())
            if old!=data:raise ValueError('immutable_iteration_changed')
        entry={'id':args.iteration,'file':file,'page':'line-always-on-'+args.iteration+'.html','generated_at':data['generated_at'],'refs':data['refs'],'artifact_sha256':data['source_artifact_sha256'],'cohort':'development'}
        index['iterations']=[item for item in index['iterations'] if item['id']!=args.iteration]+[entry]
    elif args.pending:
        if (PUBLIC/JSON_NAME).exists() and json.loads((PUBLIC/JSON_NAME).read_text()).get('publication_ready') is True:
            raise ValueError('cannot_replace_complete_results_with_pending')
        data={'schema_version':2,'status':'pending','cohort':'development','notice':'尚無完整重播、兩階段判讀與通過控制題的研究。',
              'generated_at':args.generated_at}
    else:
        data=json.loads((PUBLIC/JSON_NAME).read_text())
    planned_text=None
    if args.planned_study:
        bound_protocol=protocol or json.loads((PUBLIC/cases['protocol_file']).read_text())
        planned=planned_study_module().verified_projection(args.planned_study,cases,bound_protocol)
        check_public(planned)
        planned_text=json.dumps(planned,ensure_ascii=False,indent=1)+'\n'
        data['planned_study']=planned
    elif (PUBLIC/PLANNED_STUDY_NAME).exists():
        data['planned_study']=json.loads((PUBLIC/PLANNED_STUDY_NAME).read_text())
    if data.get('planned_study') and (data['planned_study']['refs']['engine'] != cases['source_ref']
            or data['planned_study']['proof']['protocol_sha256'] != cases['protocol_sha256']):
        raise ValueError('planned_method_binding_mismatch')
    interruption_text=None
    if args.interruption_records:
        if not args.interruption_inventory or not args.original_planned_public:
            parser.error('give both interruption inventory and original immutable public plan')
        note=interruption_module().verified_projection(args.interruption_records,args.interruption_inventory,
                                                       args.original_planned_public)
        check_public(note);data['study_interruption']=note
        interruption_text=json.dumps(note,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/INTERRUPTION_NAME).exists():
        data['study_interruption']=json.loads((PUBLIC/INTERRUPTION_NAME).read_text())
    if args.calibration_study:
        if data.get('status') != 'pending':
            raise ValueError('calibration_is_separate_from_study_results')
        data['judge_calibration'] = calibration_project(args.calibration_study)
        calibration_text=json.dumps(data['judge_calibration'],ensure_ascii=False,indent=1)+'\n'
        calibration_digest=hashlib.sha256(calibration_text.encode()).hexdigest()
        calibration_archive=PUBLIC/('line-always-on-calibration-'+calibration_digest[:12]+'.public.json')
        if calibration_archive.exists() and calibration_archive.read_text()!=calibration_text:
            raise ValueError('immutable_calibration_changed')
        calibration_archive.write_text(calibration_text)
        (PUBLIC/CALIBRATION_NAME).write_text(calibration_text)
    if args.owed_diagnostic_study:
        diagnostic=owed_diagnostic_module().verified_projection(args.owed_diagnostic_study)
        check_public(diagnostic)
        diagnostic_text=json.dumps(diagnostic,ensure_ascii=False,indent=1)+'\n'
        diagnostic_digest=hashlib.sha256(diagnostic_text.encode()).hexdigest()
        diagnostic_archive=PUBLIC/('line-always-on-owed-diagnostic-'+diagnostic_digest[:12]+'.public.json')
        if diagnostic_archive.exists() and diagnostic_archive.read_text()!=diagnostic_text:
            raise ValueError('immutable_owed_diagnostic_changed')
        diagnostic_archive.write_text(diagnostic_text)
        (PUBLIC/OWED_DIAGNOSTIC_NAME).write_text(diagnostic_text)
        data['owed_diagnostic']=diagnostic
    elif (PUBLIC/OWED_DIAGNOSTIC_NAME).exists():
        data['owed_diagnostic']=json.loads((PUBLIC/OWED_DIAGNOSTIC_NAME).read_text())
    development_text=None
    owed_terminal_text=None
    if args.owed_development_judge and not args.owed_development_study:
        parser.error('give the original owed development study with its judge archive')
    if args.owed_development_terminal_audit and not (args.owed_development_study and args.owed_development_judge):
        parser.error('give the original owed study and judge archive with its terminal audit')
    if args.owed_development_study:
        development,terminal=owed_development_projection(args.owed_development_study,args.owed_development_judge,
            args.owed_development_terminal_audit)
        check_public(development);data['owed_development']=development
        development_text=json.dumps(development,ensure_ascii=False,indent=1)+'\n'
        if terminal:
            data['owed_development_terminal']=terminal
            owed_terminal_text=json.dumps(terminal,ensure_ascii=False,indent=1)+'\n'
        elif args.owed_development_judge:
            data.pop('owed_development_terminal',None)
    elif (PUBLIC/OWED_DEVELOPMENT_NAME).exists():
        data['owed_development']=json.loads((PUBLIC/OWED_DEVELOPMENT_NAME).read_text())
    if owed_terminal_text is None and not args.owed_development_judge and (PUBLIC/OWED_TERMINAL_NAME).exists():
        data['owed_development_terminal']=json.loads((PUBLIC/OWED_TERMINAL_NAME).read_text())
    if data.get('owed_development_terminal') is not None:
        validate_owed_terminal(data['owed_development_terminal'],data.get('owed_development'))
    owed_host_text=None
    if args.owed_development_host_evidence:
        if not args.owed_development_study:
            parser.error('give the original owed study with its host evidence')
        note=verified_owed_host_interruption(args.owed_development_study,
            args.owed_development_host_evidence,data.get('owed_development'))
        data['owed_development_host_interruption']=note
        owed_host_text=json.dumps(note,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/OWED_HOST_INTERRUPTION_NAME).exists():
        data['owed_development_host_interruption']=json.loads((PUBLIC/OWED_HOST_INTERRUPTION_NAME).read_text())
    require_owed_host_interruption(data.get('owed_development'),data.get('owed_development_host_interruption'))
    if args.owed_development_v2_judge and not args.owed_development_v2_study:
        parser.error('give the fresh v2 native study with its v2 judge archive')
    if args.study and (args.owed_development_v2_study or (PUBLIC/OWED_V2_NAME).exists()):
        parser.error('export fresh owed-v2 separately; retain the original study iteration snapshot')
    owed_v2_text=None
    owed_v2=None
    if args.owed_development_v2_study:
        owed_v2_module=owed_development_v2_module()
        owed_v2=owed_v2_module.verified_projection(args.owed_development_v2_study,
            args.owed_development_v2_judge)
        owed_v2_module.validate_public(owed_v2)
        check_public(owed_v2)
        owed_v2_text=json.dumps(owed_v2,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/OWED_V2_NAME).exists():
        if (PUBLIC/OWED_V2_NAME).is_symlink():raise ValueError('owed_v2_public_not_plain_file')
        owed_v2=json.loads((PUBLIC/OWED_V2_NAME).read_text())
        owed_development_v2_module().validate_public(owed_v2);check_public(owed_v2)
    if args.owed_release_followup_judge and not args.owed_release_followup_study:
        parser.error('give the integrated-release native study with its own judge archive')
    if args.study and (args.owed_release_followup_study or (PUBLIC/OWED_RELEASE_NAME).exists()):
        parser.error('export integrated-release follow-up separately; retain original iteration snapshots')
    owed_release_text=None
    owed_release=None
    if args.owed_release_followup_study:
        module=owed_release_followup_module()
        owed_release=module.verified_projection(args.owed_release_followup_study,args.owed_release_followup_judge)
        module.validate_public(owed_release);check_public(owed_release)
        owed_release_text=json.dumps(owed_release,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/OWED_RELEASE_NAME).exists():
        if (PUBLIC/OWED_RELEASE_NAME).is_symlink():raise ValueError('owed_followup_public_not_plain_file')
        owed_release=json.loads((PUBLIC/OWED_RELEASE_NAME).read_text())
        owed_release_followup_module().validate_public(owed_release);check_public(owed_release)
    if bool(args.m6_profile_study) != bool(args.m6_profile_judge):
        parser.error('give both the separate M6 native and judge archives')
    if args.m6_profile_pending and args.m6_profile_study:
        parser.error('choose a prospective M6 panel or a reviewed export')
    m6_profile=None
    m6_text=None
    if args.m6_profile_study or args.m6_profile_pending:
        module=m6_profile_module()
        m6_profile=(module.pending_projection() if args.m6_profile_pending else
                    module.verified_projection(args.m6_profile_study,args.m6_profile_judge))
        module.validate_public(m6_profile);check_public(m6_profile)
        m6_text=json.dumps(m6_profile,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/M6_PROFILE_NAME).exists():
        path=PUBLIC/M6_PROFILE_NAME
        if path.is_symlink():raise ValueError('m6_public_not_plain_file')
        m6_profile=json.loads(path.read_text())
        m6_profile_module().validate_public(m6_profile);check_public(m6_profile)
    if bool(args.m6_profile_capture_study) != bool(args.m6_profile_capture_judge):
        parser.error('give both capture follow-up archives')
    if args.m6_profile_capture_pending and args.m6_profile_capture_study:
        parser.error('choose pending capture follow-up or reviewed export')
    m6_capture=m6_capture_text=None
    if args.m6_profile_capture_study or args.m6_profile_capture_pending:
        module=m6_capture_module()
        m6_capture=(module.pending_projection() if args.m6_profile_capture_pending else
                    module.verified_projection(args.m6_profile_capture_study,args.m6_profile_capture_judge))
        module.validate_public(m6_capture);check_public(m6_capture)
        m6_capture_text=json.dumps(m6_capture,ensure_ascii=False,indent=1)+'\n'
    elif (PUBLIC/M6_CAPTURE_NAME).exists():
        path=PUBLIC/M6_CAPTURE_NAME
        if path.is_symlink():raise ValueError('m6_capture_public_not_plain_file')
        m6_capture=json.loads(path.read_text());m6_capture_module().validate_public(m6_capture);check_public(m6_capture)
    method, report=render_method(cases,has_results=data.get('publication_ready') is True,
                                diagnostic=data.get('owed_diagnostic'),planned_study=data.get('planned_study'),
                                interruption=data.get('study_interruption'),owed_development=data.get('owed_development'),
                                owed_development_host_interruption=data.get('owed_development_host_interruption'),
                                owed_development_terminal=data.get('owed_development_terminal'),
                                owed_development_v2=owed_v2,
                                owed_release_followup=owed_release,
                                m6_profile_diagnostic=m6_profile,
                                m6_profile_capture_followup=m6_capture,
                                qualified_results=data,
                                generated_at=data.get('generated_at','2026-10-14')),render(data,index['iterations'],
                                    owed_development_v2=owed_v2,owed_release_followup=owed_release,
                                    m6_profile_diagnostic=m6_profile,m6_profile_capture_followup=m6_capture)
    check_public(data);check_public(index);check_public(cases)
    if planned_text is not None:
        digest=hashlib.sha256(planned_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-planned-study-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=planned_text:
            raise ValueError('immutable_planned_study_changed')
        archive.write_text(planned_text)
        (PUBLIC/PLANNED_STUDY_NAME).write_text(planned_text)
    if interruption_text is not None:
        digest=hashlib.sha256(interruption_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-interruption-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=interruption_text:raise ValueError('immutable_interruption_changed')
        archive.write_text(interruption_text);(PUBLIC/INTERRUPTION_NAME).write_text(interruption_text)
    if development_text is not None:
        digest=hashlib.sha256(development_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-owed-development-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=development_text:raise ValueError('immutable_owed_development_changed')
        archive.write_text(development_text);(PUBLIC/OWED_DEVELOPMENT_NAME).write_text(development_text)
    if owed_host_text is not None:
        digest=hashlib.sha256(owed_host_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-owed-host-interruption-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=owed_host_text:raise ValueError('immutable_owed_host_interruption_changed')
        archive.write_text(owed_host_text);(PUBLIC/OWED_HOST_INTERRUPTION_NAME).write_text(owed_host_text)
    if owed_terminal_text is not None:
        digest=hashlib.sha256(owed_terminal_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-owed-terminal-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=owed_terminal_text:raise ValueError('immutable_owed_terminal_changed')
        archive.write_text(owed_terminal_text);(PUBLIC/OWED_TERMINAL_NAME).write_text(owed_terminal_text)
    if owed_v2_text is not None:
        digest=hashlib.sha256(owed_v2_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-owed-development-v2-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=owed_v2_text:raise ValueError('immutable_owed_v2_changed')
        archive.write_text(owed_v2_text);(PUBLIC/OWED_V2_NAME).write_text(owed_v2_text)
    if owed_release_text is not None:
        digest=hashlib.sha256(owed_release_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-owed-release-followup-'+digest[:12]+'.public.json')
        if archive.exists() and archive.read_text()!=owed_release_text:raise ValueError('immutable_owed_followup_changed')
        archive.write_text(owed_release_text);(PUBLIC/OWED_RELEASE_NAME).write_text(owed_release_text)
    if m6_text is not None:
        digest=hashlib.sha256(m6_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-m6-profile-diagnostic-'+digest[:12]+'.public.json')
        if archive.exists() and (archive.is_symlink() or archive.read_text()!=m6_text):
            raise ValueError('immutable_m6_profile_changed')
        alias=PUBLIC/M6_PROFILE_NAME
        if alias.is_symlink():raise ValueError('m6_public_not_plain_file')
        archive.write_text(m6_text);alias.write_text(m6_text)
    if m6_capture_text is not None:
        digest=hashlib.sha256(m6_capture_text.encode()).hexdigest()
        archive=PUBLIC/('line-always-on-m6-profile-capture-followup-'+digest[:12]+'.public.json')
        alias=PUBLIC/M6_CAPTURE_NAME
        if archive.exists() and (archive.is_symlink() or archive.read_text()!=m6_capture_text):
            raise ValueError('immutable_m6_capture_changed')
        if alias.is_symlink():raise ValueError('m6_capture_public_not_plain_file')
        archive.write_text(m6_capture_text);alias.write_text(m6_capture_text)
    if protocol is not None:
        frozen=PUBLIC/protocol_file
        if frozen.exists() and json.loads(frozen.read_text())!=protocol:
            raise ValueError('immutable_protocol_changed')
        frozen.write_text(json.dumps(protocol,ensure_ascii=False,indent=1)+'\n')
    for name,text in rubric_assets.items():
        path=PUBLIC/name
        if path.exists() and path.read_text()!=text:raise ValueError('immutable_rubric_changed')
        path.write_text(text)
    if args.study:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
        (PUBLIC/entry['page']).write_text(report)
    for name,value in ((JSON_NAME,data),(CASES_NAME,cases),(ITERATIONS_NAME,index)):
        (PUBLIC/name).write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n')
    (PUBLIC/METHOD_NAME).write_text(method)
    (PUBLIC/PAGE_NAME).write_text(report)
    print(json.dumps({'pages':[METHOD_NAME,PAGE_NAME],'cohort':len(cases['episodes']),'status':data.get('status','complete')},ensure_ascii=False))


if __name__=='__main__':
    main()
