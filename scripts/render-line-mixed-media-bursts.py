#!/usr/bin/env python3
"""Render the frozen synthetic mixed-media burst study; never rewrite old results.

The page reads only the public results JSON written by the benchmark's
``summary`` command (or the clearly marked placeholder that precedes it).
Layout follows the shared LINE v3 report format: the build's navigation
normalizer adds the common tab bar and ``report-layout.css``.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1]
PAGE = "mixed-media-bursts.html"
RESULTS = "mixed-media-bursts-results.public.json"
REPOSITORY = "https://github.com/jefflai108/streaming_taiwanese"
TABS = (("index.html", "Interaction tasks"), ("delegation.html", "Delegation tasks"),
        ("taiwan.html", "台灣用語"), ("recovery.html", "困難任務與失敗恢復"),
        ("tts-followup.html", "TTS follow-up"), ("images-stickers.html", "Images &amp; Stickers"),
        ("burst-turns.html", "Burst turns"), ("natural-bridges.html", "Natural bridges"),
        ("line-stickers.html", "LINE Stickers"), ("group-replies.html", "Group replies"),
        (PAGE, "Mixed-media bursts"),
        ("line-always-on-method.html", "Always-on 方法"), ("line-always-on.html", "Always-on 結果"), ("memory-models.html", "Memory 記憶"))
LABELS = {"baseline": "原有處理", "mixed": "混合媒體分段"}
DETAIL = {"baseline": "圖片與文字各自成為獨立回合；V3 讓後到的文字不必等前一則圖片讀完。",
          "mixed": "私訊裡的一張圖片／PDF 可和前後幾秒內的文字併成同一個分段回合，一次回答（貼圖與第二張圖仍各自回覆）；"
                   "提到「這家」「這張」等指向附件的文字，會多等 6 秒讓隨後的圖片併入。"
                   "文字回答開始前，若同一聊天室較早的圖片或 PDF 還在讀取，這則文字會在佇列中等它寫入"
                   "（最多 20 秒，群組也是）；圖片、PDF 與語音本身不等待。"}
COLORS = {"baseline": "#66766c", "mixed": "#1f7a6c"}
CHECKS = {"fixtures_cited": "回答引用截圖裡的資訊", "time_kept": "保留 6:15 的時間",
          "single_answer": "只回答一次", "nearer_named": "最後回答選對較近的店",
          "caption_grounded": "回答文字的那次呼叫看得到截圖",
          "caption_answer_cites": "回答文字的那次呼叫引用截圖資訊",
          "fixtures_named": "回答說出店名（僅供參考，不計入通過）",
          "caption_answer_named": "回答文字的那次呼叫說出店名（僅供參考，不計入通過）"}
OVERVIEW_CHECKS = ("caption_grounded", "caption_answer_cites", "fixtures_cited", "time_kept", "single_answer")
KIND_LABEL = {"text": "文字", "image": "截圖", "sticker": "貼圖"}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def seconds(value):
    return f"{value / 1000:.2f} s" if number(value) else "—"


def median_seconds(values):
    values = [value for value in values if number(value)]
    return f"{seconds(statistics.median(values))} · n={len(values)}" if values else "— · n=0"


def fixture_src(data, key):
    spec = data.get("fixtures", {}).get(key, {})
    name = Path(spec.get("file", "")).name
    return "fixtures/" + name if name else ""


def event_line(data, event):
    members = {member["key"]: member["name"] for member in data.get("group_members", [])}
    who = f'<span class="who">{esc(members.get(event.get("actor"), event.get("actor")))}</span>' if event.get("actor") else ""
    if event["kind"] == "image":
        spec = data.get("fixtures", {}).get(event.get("fixture"), {})
        body = (f'<a class="thumb" href="{esc(fixture_src(data, event["fixture"]))}">'
                f'<img src="{esc(fixture_src(data, event["fixture"]))}" alt="合成截圖：{esc(spec.get("name", ""))}" '
                f'width="72" height="128" loading="lazy"></a><span>📷 截圖 · {esc(spec.get("name", ""))}</span>')
    elif event["kind"] == "sticker":
        body = "<span>🧸 LINE 貼圖（「好耶」）</span>"
    else:
        tag = '<span class="tag">@麻吉</span> ' if event.get("addressed") else ""
        body = f"<span>💬 {tag}{esc(event['text'])}</span>"
    return f'<li><time>+{event["offset_s"]:g}s</time>{who}{body}</li>'


def timeline(case, arms):
    """One shared scale: dashed inputs, quiet-reader and foreground spans, answer dots."""
    values = [event["offset_s"] * 1000 for event in case["events"]]
    for row in case["results"]:
        values += [call.get("finished_ms", call.get("started_ms", 0)) for call in row.get("model_calls", [])]
        values += [call.get("finished_ms", call.get("started_ms", 0)) for call in row.get("reader_calls", [])]
        values += [message["elapsed_ms"] for message in row.get("messages", [])]
    end = max([value for value in values if number(value)] + [1000]) * 1.05
    width, left, right = 920, 120, 20
    scale = (width - left - right) / end
    lanes = [(arm, row) for arm in arms for row in sorted(
        (row for row in case["results"] if row.get("arm") == arm), key=lambda row: row.get("sample", 1))]
    height = 50 + max(1, len(lanes)) * 40
    parts = [f'<svg class="timeline" viewBox="0 0 {width} {height}" role="img" '
             'aria-label="各版本的輸入、圖片觀察、模型呼叫與回答時間軸">',
             '<title>虛線：輸入抵達；淺色帶：群組圖片觀察；深色帶：前景模型呼叫；圓點：捕捉到的回答。</title>']
    for tick in range(6):
        value = end * tick / 5
        x = left + value * scale
        parts.append(f'<path d="M{x:.1f},22V{height - 18}" stroke="#dbe5dc"/>'
                     f'<text x="{x:.1f}" y="15" text-anchor="middle">{value / 1000:.1f}s</text>')
    for event in case["events"]:
        x = left + event["offset_s"] * 1000 * scale
        label = KIND_LABEL[event["kind"]] + ("：" + event["text"] if event.get("text") else "")
        parts.append(f'<path d="M{x:.1f},22V{height - 18}" stroke="#8195ac" stroke-dasharray="3 4">'
                     f'<title>+{event["offset_s"]:g}s {esc(label)}</title></path>')
    for index, (arm, row) in enumerate(lanes):
        y, color = 42 + index * 40, COLORS[arm]
        parts.append(f'<text x="4" y="{y + 4}">{esc(LABELS[arm])} #{row.get("sample", 1)}</text>')
        for call in row.get("reader_calls", []):
            x = left + call["started_ms"] * scale
            span = max(2, (call.get("finished_ms", call["started_ms"]) - call["started_ms"]) * scale)
            parts.append(f'<rect x="{x:.1f}" y="{y - 17}" width="{span:.1f}" height="8" rx="2" fill="{color}" opacity=".25">'
                         f'<title>群組圖片觀察 {seconds(call["started_ms"])} → {seconds(call.get("finished_ms"))}</title></rect>')
        for call in row.get("model_calls", []):
            x = left + call["started_ms"] * scale
            span = max(2, (call.get("finished_ms", call["started_ms"]) - call["started_ms"]) * scale)
            parts.append(f'<rect x="{x:.1f}" y="{y - 7}" width="{span:.1f}" height="16" rx="3" fill="{color}" opacity=".55">'
                         f'<title>前景（{esc(call.get("message_type", ""))}）{seconds(call["started_ms"])} → '
                         f'{seconds(call.get("finished_ms"))}</title></rect>')
        for message in row.get("messages", []):
            x = left + message["elapsed_ms"] * scale
            parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="5.5" fill="{color}"><title>回答 {seconds(message["elapsed_ms"])} · '
                         f'{len(message.get("texts", []))} 個泡泡</title></circle>')
    return "".join(parts) + "</svg>"


def probe_list(rows):
    """Each check's pass count over this arm's samples (unknown is never a pass)."""
    names = list(dict.fromkeys(name for row in rows for name in ((row.get("score") or {}).get("checks") or {})))
    if not names:
        return '<p class="muted">此題沒有自動檢查項目。</p>'
    items = []
    for name in names:
        values = [((row.get("score") or {}).get("checks") or {}).get(name) for row in rows]
        passed, total = sum(value is True for value in values), len(values)
        mark = "✓" if passed == total else "✗" if passed == 0 else "◐"
        css = "pass" if passed == total else "fail" if passed == 0 else "mixed"
        items.append(f'<li class="{css}">{mark} {passed}/{total} {esc(CHECKS.get(name, name))}</li>')
    return f'<ul class="probes">{"".join(items)}</ul>'


def call_outcome(call):
    if call.get("stale_cancelled"):
        return "已中止：新訊息加入，改由更新後的呼叫回答"
    if call.get("error"):
        return "錯誤：" + str(call["error"])
    return {"direct": "直接回答", "delegate": "交給背景工作"}.get(call.get("action"), call.get("action") or "—")


def evidence_table(row):
    calls = row.get("model_calls", [])
    if not calls:
        return ""
    body = "".join(
        f'<tr><td>{index + 1}</td><td>{esc(call.get("message_type", ""))}</td><td>{esc(call.get("current_text", ""))}</td>'
        f'<td>{"是" if call.get("image_attached") else "否"}</td>'
        f'<td>{call.get("recent_image_observations", 0) + call.get("recent_group_image_observations", 0)}</td>'
        f'<td>{esc("、".join(call.get("fixture_tokens_in_context", [])) or "—")}</td>'
        f'<td>{esc(call_outcome(call))}</td>'
        f'<td>{seconds(call.get("started_ms"))}</td></tr>' for index, call in enumerate(calls))
    return ('<details><summary>模型實際看得到什麼</summary><div class="scroll"><table class="wide"><thead><tr><th>次</th><th>類型</th>'
            '<th>本輪文字</th><th>附圖</th><th>上下文中的圖片觀察</th><th>上下文出現的店名</th><th>結果</th><th>開始</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></details>')


def sample_body(row):
    metrics = row.get("metrics", {})
    sends = []
    for message in row.get("messages", []):
        if message.get("duplicate"):
            continue
        bubbles = "".join(f'<div class="bubble">{esc(text)}</div>' for text in message.get("texts", []))
        sends.append(f'<div class="send"><p class="stamp">{seconds(message["elapsed_ms"])} · {esc(message["channel"])}</p>{bubbles}</div>')
    if not sends:
        sends.append('<p class="muted">沒有捕捉到回答。</p>')
    errors = list(row.get("errors", []))
    for outcome in row.get("host_deliveries", []):
        errors += [str(outcome[key]) for key in ("failure_code", "error") if outcome.get(key)]
    error = f'<p class="error">{esc(", ".join(dict.fromkeys(errors)))}</p>' if errors else ""
    aborted = metrics.get("stale_cancelled_calls") or 0
    return (f'<p class="status">{esc(row.get("status", "unknown"))} · {metrics.get("answer_batches", "—")} 次回答 · '
            f'{metrics.get("model_calls", "—")} 次前景呼叫'
            + (f'（其中 {aborted} 次因新訊息加入而中止）' if aborted else "") + '</p>'
            f'<dl><dt>最後輸入 → 最後回答</dt><dd>{seconds(metrics.get("last_input_to_last_answer_ms"))}</dd>'
            f'<dt>首次 / 最後回答</dt><dd>{seconds(metrics.get("first_answer_ms"))} / {seconds(metrics.get("last_answer_ms"))}</dd></dl>'
            + error + "".join(sends) + evidence_table(row))


def arm_column(arm, rows):
    """All samples of one arm: aggregated probes, then every sample's transcript."""
    if not rows or all(row.get("status") == "pending" for row in rows):
        return (f'<section class="arm" style="--color:{COLORS[arm]}"><h3>{esc(LABELS[arm])}</h3>'
                '<p class="muted">尚未量測。</p></section>')
    rows = sorted(rows, key=lambda row: row.get("sample", 1))
    passed = sum((row.get("score") or {}).get("passed") is True for row in rows)
    scored = sum((row.get("score") or {}).get("passed") is not None for row in rows)
    samples = "".join(
        f'<details{" open" if index == 0 else ""}><summary>樣本 #{row.get("sample", 1)}'
        f'{" · 通過" if (row.get("score") or {}).get("passed") is True else " · 未通過" if (row.get("score") or {}).get("passed") is False else ""}'
        f'</summary>{sample_body(row)}</details>' for index, row in enumerate(rows))
    return (f'<section class="arm" style="--color:{COLORS[arm]}"><h3>{esc(LABELS[arm])}</h3>'
            f'<p class="status">全部檢查通過：{passed}/{scored} 個樣本</p>' + probe_list(rows) + samples + "</section>")


def overview(data, arms):
    aggregate = data.get("aggregate") or {}
    rows = []
    for arm in arms:
        value = aggregate.get(arm)
        if not value:
            rows.append(f'<tr><th>{esc(LABELS[arm])}</th><td colspan="9" class="muted">尚未量測</td></tr>')
            continue
        checks = value.get("checks", {})
        cells = "".join(f'<td>{checks[name]["passed"]}/{checks[name]["evaluated"]}</td>' if name in checks else "<td>—</td>"
                        for name in OVERVIEW_CHECKS)
        rows.append(f'<tr><th>{esc(LABELS[arm])}</th><td>{value["cases_passed"]}/{value["cases_scored"]}</td>{cells}'
                    f'<td>{value["answer_batches"]}</td>'
                    f'<td>{seconds(value.get("median_last_input_to_last_answer_ms"))}</td>'
                    f'<td>{value["errors"]}</td></tr>')
    return ('<div class="scroll"><table class="num wide"><thead><tr><th>版本</th><th>全部檢查通過</th>'
            '<th>文字那輪看得到截圖</th><th>文字那輪引用截圖資訊</th><th>回答引用截圖資訊</th><th>保留 6:15</th>'
            '<th>只回答一次</th><th>回答總數</th>'
            '<th>最後輸入 → 最後回答（中位數）</th><th>錯誤</th></tr></thead><tbody>' + "".join(rows)
            + '</tbody></table></div>')


def render(data):
    if data.get("schema_version") != 1:
        raise ValueError("unsupported_mixed_burst_results")
    plan, cases = data["plan"], data["cases"]
    arms = plan["arms"]
    if not arms or set(arms) - set(LABELS):
        raise ValueError("unsupported_mixed_burst_arms")
    placeholder = data.get("placeholder") is True
    nav = "".join(f'<a href="{name}"' + (' aria-current="page"' if name == PAGE else "") + f">{title}</a>"
                  for name, title in TABS)
    source = plan.get("source_ref") or ""
    source_link = (f'<a href="{REPOSITORY}/commit/{esc(source)}"><code>{esc(source[:12])}</code></a>'
                   if len(source) == 40 else esc(source or "尚未凍結"))
    cases_link = (f'<a href="{REPOSITORY}/blob/{esc(source)}/serve/line_agent_v2/evals/line_architecture/'
                  'mixed_burst_cases.json">題目檔</a>' if len(source) == 40 else "題目檔")
    banner = ('<p class="notice warning"><strong>預留資料：</strong>這是頁面結構的預留版本，還沒有任何量測結果。'
              '正式量測完成後，本頁會以同一份公開 JSON 重新產生。</p>') if placeholder else ""
    fixtures = "".join(
        f'<figure><a href="{esc(fixture_src(data, key))}"><img src="{esc(fixture_src(data, key))}" '
        f'alt="合成截圖：{esc(spec["name"])}" width="180" height="320" loading="lazy"></a>'
        f'<figcaption>{esc(spec["name"])} {esc(spec.get("branch", ""))} · {esc(spec.get("distance", ""))}</figcaption></figure>'
        for key, spec in data.get("fixtures", {}).items())
    cards = []
    for case in cases:
        events = "".join(event_line(data, event) for event in case["events"])
        search = esc(" ".join([case["id"], case["name"], case["kind"]]
                              + [event.get("text", "") for event in case["events"]]))
        scope = "群組" if case.get("conversation_scope") == "group" else "私訊"
        columns = "".join(arm_column(arm, [row for row in case.get("results", []) if row.get("arm") == arm])
                          for arm in arms)
        cards.append(f'<article class="case" data-scope="{esc(case.get("conversation_scope", ""))}" data-search="{search}">'
                     f'<h2>{esc(case["id"])} · {esc(case["name"])}</h2><p class="chips"><span class="chip">{scope}</span>'
                     f'<span class="chip">{esc(case["kind"])}</span></p><ol class="inputs">{events}</ol>'
                     f'<p class="review"><strong>閱讀重點：</strong>{esc(case.get("review_goal", ""))}</p>'
                     + ("" if placeholder else f'<div class="scroll">{timeline(case, arms)}</div>')
                     + f'<div class="arms">{columns}</div></article>')
    methods = "".join(f'<div class="step" style="--color:{COLORS[arm]}"><b>{esc(LABELS[arm])}</b>{esc(DETAIL[arm])}</div>'
                      for arm in arms)
    baseline_note = {"separate_ref_with_identical_harness": "原有處理使用 main 的程式碼，與修正版共用同一套量測程式、題目與圖片。",
                     "same_ref_switches_off": "兩版跑同一份程式碼，只切換兩個 runtime 開關；修正版若新增提示文字，兩版都會帶到。"}.get(
                         plan.get("baseline_mode"), "")
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>HeyMachi · Mixed-media bursts</title><meta name="description" content="LINE v3：截圖、貼圖與文字在幾秒內連續傳來時，是否合成一個回合並看得到截圖內容。"><link rel="canonical" href="https://jefflai108.github.io/line-v3/mixed-media-bursts.html"><style>
*{box-sizing:border-box}body{margin:0;background:#f3f3ee;color:#18362d;font:14px/1.65 system-ui,-apple-system,'PingFang TC',sans-serif}
header,main,.navwrap{max-width:1500px;margin:auto;padding:20px 30px}a{color:#23695d}h1{font-size:clamp(28px,4vw,44px);line-height:1.18;margin:12px 0}
h2{font-size:23px;line-height:1.4;margin:0 0 10px}h3{font-size:16px;margin:0 0 6px;color:var(--color)}p{margin:9px 0}
.eyebrow,.small{font-size:12px;color:#526c61}.muted,.stamp,footer{color:#5f7168}.notice{padding:14px 18px;background:#e8efeb;border:1px solid #cdded3;border-radius:12px}
.warning{background:#fff3dc;border-color:#ead3a4}.panel,.case{border:1px solid #d8e1da;border-radius:16px;background:white;padding:22px;margin:0 0 22px}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(320px,100%),1fr));gap:12px}.step{border:1px solid #dce5de;border-top:4px solid var(--color);border-radius:10px;padding:15px;background:#f8faf7}.step b{display:block;margin-bottom:4px;color:var(--color)}
.fixtures{display:flex;gap:18px;flex-wrap:wrap}.fixtures figure{margin:0}.fixtures img{width:180px;height:auto;border:1px solid #d8e1da;border-radius:12px;display:block}.fixtures figcaption{font-size:12px;color:#526c61;margin-top:6px;max-width:220px}
.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e8e1;vertical-align:top}thead th{color:#52695e;background:#f8faf7;white-space:nowrap}.num td{font-variant-numeric:tabular-nums}.wide{min-width:720px}tbody th{white-space:nowrap}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}.chip,.tag{display:inline-block;font-size:12px;background:#e5ece7;border-radius:20px;padding:2px 10px}.tag{background:#dceee6;color:#1d5a3a;padding:0 7px}
.inputs{list-style:none;padding:0;margin:8px 0 14px}.inputs li{display:flex;gap:10px;align-items:center;padding:6px 0;border-bottom:1px dashed #e1e8e1}.inputs time{font-variant-numeric:tabular-nums;color:#356558;min-width:46px}
.who{font-size:12px;background:#eef1ec;border-radius:6px;padding:1px 7px}.thumb img{width:36px;height:64px;object-fit:cover;border-radius:5px;border:1px solid #d8e1da;display:block}
.review{background:#eaf0e6;border-left:3px solid #648665;padding:12px 14px}.timeline{width:100%;min-width:640px;font-size:12px;margin:8px 0 18px}.timeline text{fill:#3d564b}
.arms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.arm{border-top:4px solid var(--color);min-width:0;padding-top:10px}.status{font-size:12px}
.probes{list-style:none;padding:0;margin:6px 0 10px;font-size:13px}.probes .pass{color:#1d5a3a}.probes .fail{color:#a1372d}.probes .mixed{color:#8a5a00}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;font-size:12px;margin:0 0 12px}dt{color:#687a6d}dd{margin:0;font-variant-numeric:tabular-nums}
.bubble{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9f7;border:1px solid #dce5de;border-radius:12px;padding:10px 12px;margin:6px 0}.stamp{font-size:11px;margin:10px 0 2px}
details{font-size:12px;margin-top:10px}summary{cursor:pointer;color:#23695d}.error{color:#a1372d}
.controls{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;margin:20px 0}label{font-size:13px;display:grid;gap:6px}input,select{font:inherit;background:white;border:1px solid #bacdbb;border-radius:7px;padding:9px;max-width:100%}
.case[hidden]{display:none}footer{padding:22px 0;font-size:12px}.skip{position:absolute;left:-10000px}.skip:focus{left:16px;top:5px;background:white;padding:10px}
.tabs{display:flex;gap:5px;flex-wrap:wrap;background:#e3e9e2;padding:6px;border-radius:10px}.tabs a{padding:8px 12px;text-decoration:none;border-radius:7px;font-size:13px}.tabs [aria-current]{background:white;font-weight:700}
@media(max-width:900px){.arms{grid-template-columns:1fr}}@media(max-width:760px){header,main,.navwrap{padding:16px}.panel,.case{padding:16px}.inputs li{flex-wrap:wrap}}
</style></head><body><a class="skip" href="#main">跳到量測內容</a><div class="navwrap"><nav class="tabs" aria-label="比較分頁">''' + nav + '''</nav></div>
<header><p class="eyebrow">HeyMachi / LINE v3 · 混合媒體分段 · 真實 Gemini 呼叫 + 本機捕捉 LINE 傳輸</p><h1>Mixed-media bursts</h1>
<p>使用者先傳一張餐廳截圖，幾秒後打「晚上吃這家 6:15pm」。原有處理把圖片和文字當成兩個獨立請求：文字回合在圖片還沒讀完時就開始作答，「這家」找不到對象；群組裡的截圖只是背景觀察，被標註的文字可能在觀察寫入前就回答了。這裡比較原有處理與修正版在私訊與群組、圖片在前或在後時的表現。</p>
<p class="notice">每題都是全新的隔離資料庫，經過簽章 webhook 與四個並行 worker（和正式環境一樣，V3 的新訊息不必等前一則處理完）。前景是 Gemini 3.8 Flash low，80 秒上限；群組圖片走正式的背景觀察器。兩張截圖是虛構店家，沒有真實地點、品牌或人物。不傳送真實 LINE 訊息、不執行委派工作、不合成語音。每題每版 ''' + str(plan.get("samples_per_case_arm", 1)) + ''' 個樣本，兩版輪流先跑；自動檢查只看「回答文字的那次呼叫」是否看得到截圖、是否引用截圖裡的資訊，以及 6:15 與回答次數，不是品質評分，請逐題閱讀回答。</p>
''' + banner + '''<p class="small">量測版本：''' + esc(plan.get("revision", "")) + ''' · ''' + str(len(cases)) + ''' 題 × ''' + str(len(arms)) + ''' 版 × ''' + str(plan.get("samples_per_case_arm", 1)) + ''' 樣本。''' + esc(baseline_note) + '''</p>
<p class="small">來源：''' + source_link + ''' · <a href="''' + RESULTS + '''" download>下載完整公開結果 JSON</a> · 量測程式：<code>serve/line_agent_v2/evals/line_architecture/mixed_burst_benchmark.py</code></p></header>
<main id="main"><section class="panel"><h2>兩種處理方式</h2><div class="steps">''' + methods + '''</div></section>
<section class="panel"><h2>測試用截圖</h2><p class="muted">以程式繪製的虛構餐廳列表（距離 1.2 公里與 3.5 公里），檔案雜湊固定在題目檔中。</p><div class="fixtures">''' + fixtures + '''</div></section>
<section class="panel"><h2>量測概覽</h2><p class="muted">分數只計入有自動檢查的題目，跨所有樣本計數。「引用截圖資訊」接受''' + cases_link + '''預先登記、只出現在截圖裡的細節（店名、評分、營業時間、電話、距離等）；只看店名的兩項檢查列在各題，僅供參考、不計入通過，因為「這家評分 4.6、開到半夜兩點」這類回答已經讀了截圖卻不一定重複店名。修正版會中止被新訊息淘汰的圖片呼叫並改用更新後的呼叫，這類中止另行標示，不算錯誤。時間是共用開發主機上的觀測（所有樣本的中位數），不是正式服務 SLO；缺少的時間不填零。</p>''' + overview(data, arms) + '''</section>
<div class="controls"><label>找情境<input id="search" type="search" placeholder="題號、訊息或標題"></label><label>聊天室<select id="scope"><option value="all">全部</option><option value="direct">私訊</option><option value="group">群組</option></select></label><p id="count" aria-live="polite"></p></div>''' + "".join(cards) + '''<footer>本頁只讀取凍結的公開結果 JSON；所有回答與錯誤原樣保留，沒有挑選重跑結果。其他分頁保留各自的凍結量測。</footer></main><script>
const search=document.getElementById('search'),scope=document.getElementById('scope'),cards=[...document.querySelectorAll('.case')];
function filter(){let n=0;for(const card of cards){const visible=(scope.value==='all'||card.dataset.scope===scope.value)&&card.dataset.search.toLowerCase().includes(search.value.trim().toLowerCase());card.hidden=!visible;if(visible)n++;}document.getElementById('count').textContent=`${n} / ${cards.length} 題`;}
search.addEventListener('input',filter);scope.addEventListener('change',filter);filter();
</script></body></html>'''


def placeholder(cases):
    """A clearly marked, measurement-free dataset from the frozen case file."""
    fixtures = {key: {name: spec[name] for name in ("token", "name", "branch", "distance", "sha256", "file")}
                for key, spec in cases["fixtures"].items()}
    arms = ["baseline", "mixed"]
    return {"schema_version": 1, "placeholder": True,
            "plan": {"revision": "pending", "arms": arms, "source_ref": "", "baseline_mode": ""},
            "fixtures": fixtures, "group_members": cases.get("group", {}).get("members", []),
            "aggregate": {}, "cases": [{**case, "results": [{"arm": arm, "status": "pending"} for arm in arms]}
                                       for case in cases["cases"]]}


def install(results, public, fixture_dir):
    raw = Path(results).read_bytes()
    data = json.loads(raw)
    content = render(data)
    public.mkdir(parents=True, exist_ok=True)
    (public / RESULTS).write_bytes(raw)
    (public / PAGE).write_text(content)
    target = public / "fixtures"
    target.mkdir(exist_ok=True)
    for key, spec in data.get("fixtures", {}).items():
        name = Path(spec["file"]).name
        source = Path(fixture_dir) / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("fixture_digest_mismatch:" + key)
        shutil.copyfile(source, target / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path)
    parser.add_argument("--placeholder-from-cases", type=Path,
                        help="mixed_burst_cases.json; writes a marked placeholder results file first")
    parser.add_argument("--fixtures", type=Path, required=True, help="directory holding the benchmark fixture JPEGs")
    parser.add_argument("--public", type=Path, default=ROOT / "public/line-v3")
    args = parser.parse_args()
    results = args.results
    if args.placeholder_from_cases is not None:
        results = args.public / RESULTS
        args.public.mkdir(parents=True, exist_ok=True)
        results.write_text(json.dumps(placeholder(json.loads(args.placeholder_from_cases.read_text())),
                                      ensure_ascii=False, indent=2) + "\n")
    if results is None:
        parser.error("--results or --placeholder-from-cases is required")
    install(results, args.public, args.fixtures)
