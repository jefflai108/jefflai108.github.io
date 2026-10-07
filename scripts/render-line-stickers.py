#!/usr/bin/env python3
"""Render the LINE Stickers benchmark: existing V3 versus proactive stickers.

``project`` turns a private, frozen study's results.json into the public JSON:
synthetic chats, delivered LINE objects, the host sticker funnel and the AI
judge verdicts. It keeps no paths, credentials, prompts, logs or HTTP data and
refuses to write if any string looks like one. ``render`` builds the page from
that public JSON alone, so the published HTML reproduces byte for byte.

    python3 scripts/render-line-stickers.py STUDY_DIR   # project + render
    python3 scripts/render-line-stickers.py --render    # re-render from public JSON
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
JSON_NAME = "line-stickers-results.public.json"
PAGE_NAME = "line-stickers.html"
SOURCE_REPO = "https://github.com/jefflai108/streaming_taiwanese"
ARMS = ("existing", "proactive")
ARM_LABELS = {"existing": "原有版本", "proactive": "主動貼圖版"}
ARM_COLORS = {"existing": "#8f9a94", "proactive": "#1f7a6c"}
EXPECTATIONS = ("welcome", "neutral", "avoid")
EXPECTATION_LABELS = {"welcome": "適合貼圖", "neutral": "可有可無", "avoid": "應避免"}
CATEGORY_LABELS = {"social": "日常社交", "incoming_sticker": "對方傳貼圖", "practical": "實用問答與代寫",
                   "sensitive": "敏感情境", "opt_out": "說過不要貼圖", "crisis": "危機"}
ISSUE_LABELS = {"meaning_mismatch": "圖意不符", "tone_mismatch": "語氣不搭", "sensitive_context": "敏感情境",
                "contradicts_reply": "與文字矛盾", "ignores_opt_out": "無視拒收", "fabricates_experience": "捏造親身經驗",
                "unclear_foreign_text": "外文不易懂", "too_generic": "太泛用", "repetitive": "重複"}
ART = "https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
TABS = (("index.html", "Interaction tasks"), ("delegation.html", "Delegation tasks"),
        ("taiwan.html", "台灣用語"), ("recovery.html", "困難任務與失敗恢復"),
        ("tts-followup.html", "TTS follow-up"), ("images-stickers.html", "Images &amp; Stickers"),
        ("burst-turns.html", "Burst turns"), ("natural-bridges.html", "Natural bridges"),
        ("line-stickers.html", "LINE Stickers"))
_UNSAFE = re.compile(r"/Users/|/private/|/home/|/var/folders|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{16,}|"
                     r"Bearer\s|-----BEGIN|api[_-]?key", re.I)


# ---------------------------------------------------------------- projection

def _verdict(value):
    keys = ("sticker_sent", "sticker_fit", "fit_reason", "appropriateness", "issues", "appropriateness_reason")
    return {key: value[key] for key in keys}


def sensitive_closing(summary):
    rows = {arm: summary[arm]["response"].get("sensitive_neutral") for arm in ARMS}
    if not all(rows.values()):
        return ""
    return (f"另外，這些敏感對話裡作者標成「可有可無」的收尾回合（例如被朋友背叛後說「謝謝你聽我發洩」）："
            f"原有 {rows['existing']['sticker_turns']}/{rows['existing']['turns']} · 主動 {rows['proactive']['sticker_turns']}/{rows['proactive']['turns']} 送出貼圖；"
            f"改版規則其實希望這類收尾也只用文字，這是尚未完全做到的地方。")


def fit_caption(summary):
    blind = summary["proactive"]["judge"].get("fit_source") == "blind_context_only"
    if blind:
        agree = summary["proactive"]["judge"].get("blind_fit_consistency")
        return ("另一次盲評只給評審這一輪之前的對話與使用者訊息，看不到麻吉怎麼回，再判斷此刻回貼圖適合／可有可無／應避免；"
                f"兩次盲評的判斷一致率 {pct(agree)}。同一份資料若讓評審看到回覆，判斷會受到有沒有送貼圖影響，所以只作參考。")
    return "評審先只看到使用者這一輪為止的對話，判斷此刻回貼圖是否合適（適合／可有可無／應避免），再看麻吉實際怎麼回。"


def round_summary(results, label):
    """Headline numbers of an earlier development round (no turns)."""
    summary, comparison = results["summary"], results["comparison"]
    return {"label": label, "refs": results["metadata"]["refs"],
            "arms": {arm: {"rate": summary[arm]["response"]["rate"],
                           "sticker_turns": summary[arm]["response"]["sticker_turns"],
                           "turns": summary[arm]["response"]["turns"],
                           "appropriateness_mean": summary[arm]["appropriateness"]["mean"],
                           "judged_stickers": summary[arm]["appropriateness"]["judged_stickers"],
                           "inappropriate": summary[arm]["appropriateness"]["inappropriate"],
                           "avoid_stickers": summary[arm]["response"]["by_expectation"]["avoid"]["sticker_turns"],
                           "issues": summary[arm]["appropriateness"]["issues"]} for arm in ARMS},
            "rate_difference": comparison["rate_difference"],
            "appropriateness_difference": comparison["appropriateness_difference"]}


def project(results, *, generated_at, previous=()):
    """Public subset of a completed private study; every string is checked."""
    metadata = results["metadata"]
    judge = metadata.get("judge")
    if not judge:
        raise ValueError("study_not_judged")
    turns = []
    episodes = {}
    for row in results["turns"]:
        if set(row.get("judge", {})) != {str(index) for index in range(1, judge["passes"] + 1)}:
            raise ValueError("turn_not_fully_judged:" + row["slot"])
        delivered = []
        for item in row["delivered"]:
            if item["type"] == "text":
                delivered.append({"type": "text", "text": item["text"]})
            elif item["type"] == "sticker":
                delivered.append({"type": "sticker", "catalog_key": item["catalog_key"],
                                  "package_id": item["package_id"], "sticker_id": item["sticker_id"],
                                  "description": item["description"]})
            else:
                delivered.append({"type": item["type"]})
        funnel = row["funnel"]
        turns.append({"episode_id": row["episode_id"], "arm": row["arm"], "repeat": row["repeat"],
            "account": row["account"], "turn_index": row["turn_index"], "action": row["action"],
            "interaction_status": row["interaction_status"], "sticker_delivered": row["sticker_delivered"],
            "delivered": delivered,
            "funnel": {key: funnel[key] for key in ("eligible", "model_selected", "model_follow_up_kind",
                                                    "parsed_selected", "host_reserved", "host_trailing")},
            "judge": {key: _verdict(value) for key, value in sorted(row["judge"].items())},
            **({"judge_fit": {key: {"sticker_fit": value["sticker_fit"], "fit_reason": value["fit_reason"]}
                              for key, value in sorted(row["judge_fit"].items())}} if row.get("judge_fit") else {}),
            "foreground_elapsed_ms": row["foreground_elapsed_ms"]})
        episode = episodes.setdefault(row["episode_id"], {"id": row["episode_id"], "title": row["title"],
                                                           "category": row["category"], "turns": {}})
        episode["turns"].setdefault(row["turn_index"], {"expectation": row["expectation"], "input": row["input"]})
    ordered = []
    for identity in sorted(episodes):
        episode = episodes[identity]
        ordered.append({**episode, "turns": [episode["turns"][index] for index in sorted(episode["turns"])]})
    controls = results.get("judge_controls") or {"items": []}
    public = {
        "schema_version": 1, "generated_at": generated_at, "cohort": metadata["cohort"],
        "refs": metadata["refs"], "source_repository": SOURCE_REPO,
        "models": {"foreground": metadata["models"]["foreground"],
                   "foreground_thinking": metadata["models"]["foreground_thinking"],
                   "foreground_timeout_s": metadata["models"]["foreground_timeout_s"],
                   "judge": judge["model"], "judge_reasoning": judge["reasoning"]},
        "judge": {**{key: judge[key] for key in ("passes", "rubric_sha256", "judge_sha256", "packets_sha256",
                                                 "attempts")}, "fit_only": judge.get("fit_only")},
        "design": {key: metadata[key] for key in ("repeats", "episode_count", "turn_count", "slot_count")},
        "slot_status": results["slot_status"], "summary": results["summary"],
        "comparison": results["comparison"],
        "controls": [{"id": item["packet_id"], "expect": item["expect"],
                      "judged": [{"pass": row["pass"], "as_expected": row["as_expected"], **_verdict(row["verdict"])}
                                 for row in item["judged"]]} for item in controls["items"]],
        "previous_rounds": list(previous), "episodes": ordered, "turns": turns}
    check_public(public)
    return public


def check_public(value, where="root"):
    if isinstance(value, dict):
        for key, child in value.items():
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


def ratio_text(comparison):
    if comparison.get("rate_ratio") is None:
        return "原有版本沒有可比較的基準"
    return (f"為原本的 {comparison['rate_ratio']:.2f} 倍（相對 {comparison['relative_change'] * 100:+.0f}%"
            f"，95% 信賴區間 {ci(comparison.get('rate_ratio_ci95'), _ratio)} 倍）")


def _ratio(value):
    return f"{value:.2f}"


def commit_link(ref):
    return f'<a href="{SOURCE_REPO}/commit/{esc(ref)}"><code>{esc(ref[:8])}</code></a>'


def tab_nav(current):
    marker = ' aria-current="page"'
    links = "".join(f'<a href="{href}"{marker if href == current else ""}>{label}</a>' for href, label in TABS)
    return f'<div class="navwrap"><nav class="tabs" aria-label="比較分頁">{links}</nav></div>'


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
    """Grouped horizontal bars, one row per category, existing then proactive.

    ``values[arm][index]`` is ``(display_value, numerator, denominator)``.
    """
    left, right, top = 210, 92, 34
    bar, gap, group = 14, 2, 22
    height = top + len(categories) * (2 * bar + gap + group) + 10
    plot = width - left - right
    peak = maximum or max([value[0] for arm in ARMS for value in values[arm] if value[0] is not None] + [1])
    ticks = [peak * step / 4 for step in range(5)]
    parts = [f'<div class="scroll"><svg class="chart" id="{esc(chart_id)}" viewBox="0 0 {width} {height}" role="img" '
             f'aria-labelledby="{esc(chart_id)}-title"><title id="{esc(chart_id)}-title">{esc(title)}</title>']
    for tick in ticks:
        x = left + plot * tick / peak
        label = f"{tick * 100:.0f}%" if unit == "percent" else f"{tick:.0f}"
        parts.append(f'<path class="grid" d="M{x:.2f},{top - 8}V{height - 8}"/>'
                     f'<text class="tick" x="{x:.2f}" y="{top - 14}" text-anchor="middle">{label}</text>')
    for index, category in enumerate(categories):
        y0 = top + index * (2 * bar + gap + group)
        parts.append(f'<text class="cat" x="{left - 12}" y="{y0 + bar + 4}" text-anchor="end">{esc(category)}</text>')
        for offset, arm in enumerate(ARMS):
            value, numerator, denominator = values[arm][index]
            y = y0 + offset * (bar + gap)
            if value is None:
                parts.append(f'<text class="val" x="{left + 6}" y="{y + 11}">無資料</text>')
                continue
            length = plot * value / peak
            shown = pct(value) if unit == "percent" else f"{value:.0f}"
            detail = f"{ARM_LABELS[arm]} · {category}：{shown}"
            if denominator is not None:
                detail += f"（{numerator}/{denominator}）"
            parts.append(f'<path class="bar {arm}" d="{bar_path(left, y, length, bar)}" tabindex="0" '
                         f'data-tip="{esc(detail)}"><title>{esc(detail)}</title></path>')
            parts.append(f'<text class="val" x="{left + length + 6:.2f}" y="{y + 11}">{esc(shown)}</text>')
    parts.append("</svg></div>")
    legend = "".join(f'<span><i class="swatch {arm}"></i>{ARM_LABELS[arm]}</span>' for arm in ARMS)
    rows = "".join(
        f"<tr><th scope=\"row\">{esc(category)}</th>" + "".join(
            f"<td>{esc(pct(values[arm][i][0]) if unit == 'percent' else values[arm][i][0])}"
            + (f" <small>({values[arm][i][1]}/{values[arm][i][2]})</small>" if values[arm][i][2] is not None else "")
            + "</td>" for arm in ARMS) + "</tr>" for i, category in enumerate(categories))
    table = (f'<details class="tableview"><summary>表格檢視</summary><div class="scroll"><table><thead><tr><th>'
             f'項目</th>{"".join(f"<th>{ARM_LABELS[arm]}</th>" for arm in ARMS)}</tr></thead><tbody>{rows}'
             f'</tbody></table></div></details>')
    note = f'<p class="small muted">{caption}</p>' if caption else ""
    return f'<figure class="figure"><div class="legend">{legend}</div>{"".join(parts)}{note}{table}</figure>'


def _rate_values(summary, key, labels):
    values = {arm: [] for arm in ARMS}
    for label in labels:
        for arm in ARMS:
            item = summary[arm]["response"][key][label]
            values[arm].append((item["rate"], item["sticker_turns"], item["turns"]))
    return values


# ------------------------------------------------------------------ sections

def sticker_figure(item, *, small=False):
    description = item.get("description") or "未知貼圖"
    if item.get("catalog_key") is None and item.get("sticker_id") in (None, "999999999"):
        return f'<div class="sticker unknown"><span>未知貼圖</span><small>系統沒有畫面或描述</small></div>'
    src = ART.format(sticker_id=item["sticker_id"])
    key = f'<code>{esc(item["catalog_key"])}</code> · ' if item.get("catalog_key") else ""
    return (f'<figure class="sticker{" small" if small else ""}"><img src="{esc(src)}" alt="{esc(description)}" '
            f'loading="lazy" decoding="async" referrerpolicy="no-referrer"><figcaption>{key}{esc(description)}'
            f'</figcaption></figure>')


def user_cell(turn_input):
    if turn_input["type"] == "text":
        return f'<div class="bubble user">{esc(turn_input["text"])}</div>'
    item = {"catalog_key": turn_input.get("catalog_key"), "sticker_id": turn_input.get("sticker_id"),
            "description": turn_input.get("description")}
    keywords = "、".join(turn_input.get("keywords") or []) or "無"
    return f'<div class="bubble user sticker-in">{sticker_figure(item, small=True)}<small>關鍵字：{esc(keywords)}</small></div>'


FIT_LABELS = {"welcome": "適合貼圖", "neutral": "可有可無", "avoid": "應避免"}


def machi_cell(turn, arm):
    label = ARM_LABELS[arm]
    if turn is None:
        return f'<td class="missing" data-arm="{label}">未量測</td>'
    parts = []
    for item in turn["delivered"]:
        if item["type"] == "text":
            parts.append(f'<div class="bubble machi">{esc(item["text"])}</div>')
        elif item["type"] == "sticker":
            parts.append(sticker_figure(item))
        else:
            parts.append(f'<div class="bubble machi other">（{esc(item["type"])} 訊息）</div>')
    if not parts:
        parts.append('<p class="small muted">沒有捕捉到送出的訊息。</p>')
    verdict = turn["judge"]["1"]
    second = turn["judge"].get("2")
    funnel = turn["funnel"]
    if not funnel["eligible"]:
        host = "這輪不能貼圖（冷卻：不連續、五輪最多兩張）"
    elif not funnel["model_selected"]:
        host = "可貼圖，模型選 null"
    elif not funnel["parsed_selected"]:
        host = f'模型選了 <code>{esc(funnel["model_selected"])}</code>，因接話留白被丟棄'
    elif not funnel["host_reserved"]:
        host = f'模型選了 <code>{esc(funnel["model_selected"])}</code>，宿主未保留'
    else:
        host = f'送出 <code>{esc(funnel["host_reserved"])}</code>' + ("（接在主回答後）" if funnel["host_trailing"] else "")
    if turn["action"] != "direct":
        host += f" · 路由 {esc(turn['action'])}"
    blind = (turn.get("judge_fit") or {}).get("1")
    moment = blind or verdict
    fit_label = "評審（看不到回覆）" if blind else "評審"
    if verdict["sticker_sent"]:
        chip = f'<span class="chip score s{verdict["appropriateness"]}">適切度 {verdict["appropriateness"]}/5</span>'
        reason = verdict["appropriateness_reason"]
    else:
        chip = '<span class="chip none">未送貼圖</span>'
        reason = moment["fit_reason"]
    fit = f'<span class="chip fit {moment["sticker_fit"]}">{fit_label}：{FIT_LABELS[moment["sticker_fit"]]}</span>'
    repeat = ""
    if second is not None:
        again = f'{second["appropriateness"]}/5' if second["appropriateness"] is not None else FIT_LABELS[second["sticker_fit"]]
        repeat = f'<small class="muted">第二次評審：{esc(again)}</small>'
    return (f'<td data-arm="{label}">{"".join(parts)}<div class="meta">{fit}{chip}<p class="reason">{esc(reason)}</p>{repeat}'
            f'<p class="host">{host}</p></div></td>')


def explorer(data):
    turns = {(t["episode_id"], t["repeat"], t["arm"], t["turn_index"]): t for t in data["turns"]}
    repeats = sorted({t["repeat"] for t in data["turns"]})
    accounts = {t["repeat"]: t["account"] for t in data["turns"]}
    blocks = []
    for number, episode in enumerate(data["episodes"]):
        counts = {arm: sum(t["sticker_delivered"] for t in data["turns"]
                           if t["episode_id"] == episode["id"] and t["arm"] == arm) for arm in ARMS}
        total = len(episode["turns"]) * len(repeats)
        buttons = "".join(f'<button type="button" data-show="{r}" aria-pressed="{"true" if r == repeats[0] else "false"}">'
                          f'第 {r} 次 · {"主帳號" if accounts[r] == "primary" else "第二帳號"}</button>' for r in repeats)
        panes = []
        for r in repeats:
            rows = []
            for index, spec in enumerate(episode["turns"]):
                expectation = spec["expectation"]
                cells = "".join(machi_cell(turns.get((episode["id"], r, arm, index)), arm) for arm in ARMS)
                rows.append(f'<tr><th scope="row"><span class="turn">{index + 1}</span>'
                            f'<span class="chip expect {expectation}">作者標註：{EXPECTATION_LABELS[expectation]}</span>'
                            f'{user_cell(spec["input"])}</th>{cells}</tr>')
            panes.append(f'<div class="repeat" data-repeat="{r}"{"" if r == repeats[0] else " hidden"}>'
                         f'<h4 class="repeat-title">第 {r} 次執行 · {"主帳號" if accounts[r] == "primary" else "第二帳號"}</h4>'
                         f'<div class="scroll"><table class="transcript"><thead><tr><th>使用者這一輪</th>'
                         f'<th>{ARM_LABELS["existing"]}</th><th>{ARM_LABELS["proactive"]}</th></tr></thead>'
                         f'<tbody>{"".join(rows)}</tbody></table></div></div>')
        category = CATEGORY_LABELS.get(episode["category"], episode["category"])
        blocks.append(f'<details class="episode" id="{esc(episode["id"])}"{" open" if number == 0 else ""}>'
                      f'<summary><b>{esc(episode["id"])} · {esc(episode["title"])}</b><span class="chip">{esc(category)}</span>'
                      f'<span class="small">貼圖回合：原有 {counts["existing"]}/{total} · 主動 {counts["proactive"]}/{total}</span>'
                      f'</summary><div class="switch" role="group" aria-label="選擇執行次數">{buttons}</div>{"".join(panes)}</details>')
    return "".join(blocks)


def rounds_block(data):
    rounds = data.get("previous_rounds") or []
    if not rounds:
        return ""
    rows = []
    for item in rounds:
        arms = item["arms"]
        issues = "、".join(f"{ISSUE_LABELS.get(key, key)} {value}" for key, value in
                          sorted(arms["proactive"]["issues"].items(), key=lambda pair: -pair[1])[:4]) or "無"
        rows.append(f"<tr><th scope=\"row\">{esc(item['label'])}<small>改版 {commit_link(item['refs']['proactive'])}</small></th>"
                    f"<td>{pct(arms['existing']['rate'])} → {pct(arms['proactive']['rate'])}</td>"
                    f"<td>{score(arms['existing']['appropriateness_mean'])} → {score(arms['proactive']['appropriateness_mean'])}</td>"
                    f"<td>{arms['existing']['inappropriate']} → {arms['proactive']['inappropriate']}</td>"
                    f"<td>{arms['existing']['avoid_stickers']} → {arms['proactive']['avoid_stickers']}</td>"
                    f"<td>{esc(issues)}</td></tr>")
    return ('<h3>開發輪次</h3><p>同一題組先跑過較早的改版；評審在敏感對話（生氣、等檢查報告）與「回應道謝」上找到的問題，'
            '讓規則先判斷整段對話能不能用貼圖、並注意道謝方向，再重跑一次。上方數字都是最後這一輪；較早輪次保留如下，沒有挑選或合併。</p>'
            '<div class="scroll"><table class="num"><thead><tr><th>輪次</th><th>回應率（原有 → 改版）</th><th>適切度</th>'
            '<th>2 分以下</th><th>「應避免」回合送出貼圖</th><th>改版被標註的問題</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def control_table(data):
    rows = []
    for control in data["controls"]:
        expect = control["expect"]
        bound = ("≥ " + str(expect["min"])) if "min" in expect else ("≤ " + str(expect["max"])) if "max" in expect else "—"
        sent = "不送" if expect.get("sent") is False else "送出"
        judged = " / ".join(
            ("✓ " if row["as_expected"] else "✗ ") + FIT_LABELS[row["sticker_fit"]]
            + (f" · {row['appropriateness']}/5" if row["appropriateness"] is not None else "") for row in control["judged"])
        rows.append(f"<tr><th scope=\"row\">{esc(control['id'])}</th><td>{FIT_LABELS[expect['fit']]} · {sent} · 分數 {bound}</td>"
                    f"<td>{esc(judged)}</td></tr>")
    return "".join(rows)


CSS = """
*{box-sizing:border-box}body{margin:0;background:#f3f3ee;color:#193a31;font:15px/1.65 system-ui,-apple-system,'PingFang TC',sans-serif}
header,main,.navwrap{max-width:1450px;margin:auto;padding:24px 28px}h1{font-size:clamp(32px,5vw,52px);line-height:1.15;margin:15px 0}
h2{font-size:22px;line-height:1.4;margin:0 0 12px}h3{font-size:17px;margin:20px 0 8px}h4{font-size:14px;margin:12px 0 8px}
a{color:#23695d}a:focus-visible,summary:focus-visible,button:focus-visible,.bar:focus-visible{outline:3px solid #269890;outline-offset:3px}
p{margin:9px 0}.eyebrow,.small,small{font-size:12px;color:#526c61}.muted{color:#5f7168}.lede{font-size:17px}
.panel{border:1px solid #d6e0d7;border-radius:15px;background:white;padding:22px;margin-bottom:22px}
.nowrap{white-space:nowrap}.notice{padding:14px 18px;background:#e8efeb;border:1px solid #cdded3;border-radius:12px}.warning{background:#fff3dc;border-color:#ead3a4}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.badge,.chip{display:inline-block;font-size:12px;background:#e5ece7;border-radius:20px;padding:3px 10px;color:#193a31}
.tabs{display:flex;gap:5px;flex-wrap:wrap;background:#e3e9e2;padding:6px;border-radius:10px}.tabs a{padding:8px 12px;text-decoration:none;border-radius:7px;font-size:13px}.tabs [aria-current]{background:white;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));gap:16px}.kpi{border:1px solid #dce5de;border-radius:12px;padding:18px;background:#f8faf7}
.kpi .label{font-size:13px;color:#526c61;margin:0 0 6px}.kpi .values{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap}
.kpi .value{font-size:34px;font-weight:650;line-height:1.1}.kpi .from{font-size:22px;color:#5f7168;font-weight:500}.kpi .arrow{font-size:20px;color:#5f7168}
.kpi .delta{font-size:14px;font-weight:600;color:#1d5a3a;margin-top:8px}.kpi .sub{font-size:12px;color:#526c61;margin-top:4px}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:12px}.step{border:1px solid #dce5de;border-radius:10px;padding:15px;background:#f8faf7}.step b{display:block;margin-bottom:4px}
.figure{margin:8px 0 18px}.chart{width:100%;height:auto;display:block}.chart text{font:12px system-ui,-apple-system,'PingFang TC',sans-serif;fill:#3d564b}
.chart .cat{fill:#193a31;font-size:13px}.chart .tick{fill:#6c7d74;font-variant-numeric:tabular-nums}.chart .val{fill:#193a31;font-variant-numeric:tabular-nums}
.chart .grid{stroke:#e1e8e1;stroke-width:1}.bar{cursor:default}.bar.existing{fill:#8f9a94}.bar.proactive{fill:#1f7a6c}.bar:hover,.bar:focus{opacity:.82}
.legend{display:flex;gap:16px;font-size:13px;margin:4px 0 6px}.legend span{display:inline-flex;align-items:center;gap:6px}.swatch{width:12px;height:12px;border-radius:3px;display:inline-block}
.swatch.existing{background:#8f9a94}.swatch.proactive{background:#1f7a6c}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}
.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e8e1;vertical-align:top}
thead th{color:#52695e;background:#f8faf7}td small{display:block}.tableview{font-size:13px;margin:6px 0 0}
.num td,.num th{font-variant-numeric:tabular-nums}details{margin:10px 0}summary{cursor:pointer}
.episode{border:1px solid #dce5de;border-radius:12px;background:white;padding:12px 16px}.episode summary{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.switch{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.switch button{font:inherit;font-size:13px;border:1px solid #c5d5ca;background:#f8faf7;border-radius:8px;padding:6px 10px;cursor:pointer;color:#193a31}
.switch button[aria-pressed=true]{background:#1f7a6c;color:white;border-color:#1f7a6c}.repeat-title{display:none}.nojs .repeat-title{display:block}
.transcript th[scope=row]{width:27%;min-width:220px;background:#fbfcfa}.transcript td{width:36.5%;min-width:280px}.turn{display:inline-block;font-weight:700;margin-right:6px}
.bubble{white-space:pre-wrap;overflow-wrap:anywhere;border-radius:12px;padding:10px 12px;margin:8px 0;border:1px solid #dce5de;background:white}
.bubble.user{background:#eef6ea;border-color:#d4e6cf}.bubble.machi{background:#f7f9f7}.sticker{margin:8px 0}.sticker img{width:110px;height:110px;object-fit:contain;display:block}
.sticker.small img{width:84px;height:84px}.sticker figcaption{font-size:11px;color:#5f7168;max-width:260px}.sticker.unknown{display:inline-flex;flex-direction:column;padding:12px;border:1px dashed #b9c9bd;border-radius:10px;font-size:13px}
.meta{border-top:1px dashed #dbe5dc;margin-top:8px;padding-top:8px}.meta .chip{margin:0 6px 4px 0}.reason{font-size:12px;margin:4px 0;color:#3d564b}.host{font-size:11px;color:#6a7c72;margin:4px 0}
.chip.fit.welcome{background:#ddefe3}.chip.fit.neutral{background:#eceee6}.chip.fit.avoid{background:#f6e3dc}.chip.expect{background:#eef1ec;margin:4px 0 2px}
.chip.score{background:#dceee6}.chip.score.s1,.chip.score.s2{background:#f6ddd5;color:#7a2e22}.chip.score.s3{background:#f4ecd6}.chip.none{background:#eef0ec}
.tooltip{position:fixed;pointer-events:none;background:#193a31;color:white;font-size:12px;padding:6px 9px;border-radius:6px;max-width:320px;z-index:50}
code{font-size:12px}.missing{color:#8a5a2b}footer{padding:22px 0;font-size:12px;color:#5f7168}.skip{position:absolute;left:-10000px}.skip:focus{left:16px;top:5px;background:white;padding:10px}
@media(max-width:760px){header,main,.navwrap{padding:16px}.panel{padding:16px}.grid2{grid-template-columns:1fr}.kpi .value{font-size:28px}#funnel,#scores{min-width:660px}
.transcript,.transcript tbody,.transcript tr,.transcript th[scope=row],.transcript td{display:block;width:auto;min-width:0}
.transcript thead{display:none}.transcript tr{border-bottom:2px solid #dbe5dc;padding-bottom:6px}.transcript td::before{content:attr(data-arm);display:block;font-weight:650;font-size:12px;color:#526c61;margin-top:4px}}
"""

SCRIPT = """
(function(){
  document.querySelectorAll('.episode').forEach(function(episode){
    episode.querySelectorAll('.switch button').forEach(function(button){
      button.addEventListener('click', function(){
        var shown = button.getAttribute('data-show');
        episode.querySelectorAll('.switch button').forEach(function(other){
          other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        });
        episode.querySelectorAll('.repeat').forEach(function(pane){
          pane.hidden = pane.getAttribute('data-repeat') !== shown;
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


def render(data):
    summary, comparison = data["summary"], data["comparison"]
    existing, proactive = summary["existing"], summary["proactive"]
    rate_e, rate_p = existing["response"]["rate"], proactive["response"]["rate"]
    appr_e, appr_p = existing["appropriateness"], proactive["appropriateness"]
    design = data["design"]
    refs = data["refs"]
    judge_e, judge_p = existing["judge"], proactive["judge"]
    controls_total = sum(len(item["judged"]) for item in data["controls"])
    controls_ok = sum(row["as_expected"] for item in data["controls"] for row in item["judged"])
    avoid = {arm: summary[arm]["response"]["by_expectation"]["avoid"] for arm in ARMS}
    judged_avoid = {arm: summary[arm]["judge"]["rate_by_judge_fit"]["avoid"] for arm in ARMS}
    funnel = {arm: summary[arm]["funnel"] for arm in ARMS}

    kpis = f"""
<div class="kpis">
 <div class="kpi"><p class="label">① 貼圖回應率：送出原生貼圖的回合</p>
  <div class="values"><span class="from">{pct(rate_e)}</span><span class="arrow">→</span><span class="value">{pct(rate_p)}</span></div>
  <p class="delta">{pp(comparison['rate_difference'])} · {ratio_text(comparison)}</p>
  <p class="sub">原有 {existing['response']['sticker_turns']}/{existing['response']['turns']} 回合 · 主動 {proactive['response']['sticker_turns']}/{proactive['response']['turns']} 回合 · 95% 信賴區間 {ci(comparison.get('rate_difference_ci95'), _plain_pct)} 個百分點</p></div>
 <div class="kpi"><p class="label">② 貼圖適切度：AI 評審 1–5 分（只評有送出的貼圖）</p>
  <div class="values"><span class="from">{score(appr_e['mean'])}</span><span class="arrow">→</span><span class="value">{score(appr_p['mean'])}</span></div>
  <p class="delta">差距 {_signed_score(comparison['appropriateness_difference'])} 分 · 95% 信賴區間 {ci(comparison.get('appropriateness_difference_ci95'), _signed_score)}</p>
  <p class="sub">4 分以上：原有 {appr_e['appropriate']}/{appr_e['judged_stickers']}（{pct(appr_e['appropriate_rate'])}）· 主動 {appr_p['appropriate']}/{appr_p['judged_stickers']}（{pct(appr_p['appropriate_rate'])}）· 2 分以下：{appr_e['inappropriate']} / {appr_p['inappropriate']} 張</p></div>
 <div class="kpi"><p class="label">不該貼圖的時刻（作者標註「應避免」）</p>
  <div class="values"><span class="from">{avoid['existing']['sticker_turns']}/{avoid['existing']['turns']}</span><span class="arrow">→</span><span class="value">{avoid['proactive']['sticker_turns']}/{avoid['proactive']['turns']}</span></div>
  <p class="delta">評審判定「應避免」的回合送出貼圖：原有 {judged_avoid['existing']['sticker_turns']}/{judged_avoid['existing']['turns']} · 主動 {judged_avoid['proactive']['sticker_turns']}/{judged_avoid['proactive']['turns']}</p>
  <p class="sub">哀傷、健康擔憂、衝突、危機與說過不要貼圖的對話。{sensitive_closing(summary)}</p></div>
</div>"""

    funnel_categories = ["可以貼圖的回合（冷卻未擋）", "模型自己選了貼圖", "解析後保留", "實際送到 LINE"]
    funnel_values = {arm: [] for arm in ARMS}
    for arm in ARMS:
        total = funnel[arm]["turns"]
        for key in ("eligible", "model_selected", "parsed_kept", "delivered"):
            funnel_values[arm].append((funnel[arm][key] / total if total else None, funnel[arm][key], total))
    funnel_chart = hbar_chart("funnel", "貼圖漏斗：佔全部回合的比例", funnel_categories, funnel_values, maximum=1, width=1160,
        caption="每一列都以該版本全部回合為分母。原有版本在接話留白時丟掉模型自己選的貼圖；改版保留並接在主回答後。"
                "改版送出更多貼圖後，下一輪較常被「不連續」冷卻擋下，所以第一列反而比較低。")
    expectation_chart = hbar_chart("by-expectation", "依作者標註分組的貼圖回應率",
        [EXPECTATION_LABELS[label] for label in EXPECTATIONS], _rate_values(summary, "by_expectation", EXPECTATIONS),
        maximum=1, caption="作者在設計題組時先標註每一輪是否適合貼圖；這只是分析分組，不會提供給模型或評審。")
    fit_values = {arm: [] for arm in ARMS}
    for label in EXPECTATIONS:
        for arm in ARMS:
            item = summary[arm]["judge"]["rate_by_judge_fit"][label]
            fit_values[arm].append((item["rate"], item["sticker_turns"], item["turns"]))
    fit_chart = hbar_chart("by-judge-fit", "依 AI 評審判斷分組的貼圖回應率",
        [f"評審：{EXPECTATION_LABELS[label]}" for label in EXPECTATIONS], fit_values, maximum=1,
        caption=fit_caption(summary))
    distribution = {arm: [] for arm in ARMS}
    for level in ("5", "4", "3", "2", "1"):
        for arm in ARMS:
            judged = summary[arm]["appropriateness"]
            count = judged["distribution"][level]
            distribution[arm].append((count / judged["judged_stickers"] if judged["judged_stickers"] else None,
                                      count, judged["judged_stickers"]))
    score_chart = hbar_chart("scores", "貼圖適切度分數分布（佔該版本送出的貼圖）",
        ["5 非常貼切", "4 貼切", "3 勉強", "2 不恰當", "1 非常不恰當"], distribution, maximum=1, width=1160,
        caption="只計算實際送出的貼圖，分母是各版本送出的貼圖數。評審看得到官方貼圖圖檔與目錄描述。")

    categories = sorted({c for arm in ARMS for c in summary[arm]["response"]["by_category"]},
                        key=lambda c: list(CATEGORY_LABELS).index(c) if c in CATEGORY_LABELS else 99)
    category_rows = "".join(
        f"<tr><th scope=\"row\">{esc(CATEGORY_LABELS.get(c, c))}</th>" + "".join(
            f"<td>{pct(summary[arm]['response']['by_category'][c]['rate'])} <small>({summary[arm]['response']['by_category'][c]['sticker_turns']}/{summary[arm]['response']['by_category'][c]['turns']})</small></td>"
            for arm in ARMS) + "</tr>" for c in categories)
    issues = sorted({issue for arm in ARMS for issue in summary[arm]["appropriateness"]["issues"]})
    issue_rows = "".join(f"<tr><th scope=\"row\">{esc(ISSUE_LABELS.get(i, i))}</th>" + "".join(
        f"<td>{summary[arm]['appropriateness']['issues'].get(i, 0)}</td>" for arm in ARMS) + "</tr>" for i in issues) \
        or '<tr><td colspan="3">兩個版本都沒有被標註問題的貼圖。</td></tr>'
    top_rows = "".join(f"<tr><th scope=\"row\">{ARM_LABELS[arm]}</th><td>{summary[arm]['distinct_stickers']} 種</td><td>"
                       + "、".join(f"<code>{esc(key)}</code>×{count}" for key, count in summary[arm]["top_stickers"][:6])
                       + "</td></tr>" for arm in ARMS)
    consistency = {arm: summary[arm]["judge"]["consistency"] for arm in ARMS}
    latency_rows = "".join(f"<tr><th scope=\"row\">{ARM_LABELS[arm]}</th><td>{summary[arm]['foreground_elapsed_ms']['p50'] / 1000:.2f} s</td>"
                           f"<td>{summary[arm]['foreground_elapsed_ms']['p90'] / 1000:.2f} s</td><td>{summary[arm]['foreground_elapsed_ms']['n']}</td></tr>"
                           for arm in ARMS)
    actions = {arm: summary[arm]["actions"] for arm in ARMS}
    sticker_inputs = sum(turn["input"]["type"] == "sticker" for episode in data["episodes"] for turn in episode["turns"])
    slots = sum(data["slot_status"].values())
    measured = sum(count for key, count in data["slot_status"].items() if key.endswith(":measured"))

    body = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>HeyMachi · LINE Stickers</title><meta name="description" content="LINE v3 互動模式原生貼圖：原有版本與主動貼圖版的貼圖回應率與 AI 評審適切度比較。"><link rel="canonical" href="https://jefflai108.github.io/line-v3/line-stickers.html"><style>{CSS}</style></head><body class="nojs"><a class="skip" href="#content">跳到比較結果</a>{tab_nav(PAGE_NAME)}
<header><p class="eyebrow">HeyMachi / LINE v3 · 2026-10-06 · 互動模式原生貼圖 · 真實 Gemini 呼叫 + 盲評 AI 評審</p><h1>LINE Stickers</h1>
<p class="lede">麻吉在互動模式中，用同一次 Gemini 呼叫自己判斷要不要回 LINE 原生貼圖、從 456 張官方貼圖裡挑哪一張。這一頁比較部署前的原有版本與主動貼圖版：① 貼圖回應率、② 貼圖適切度，兩個評估軸都由盲評 AI 評審逐輪判讀。</p>
<div class="badges"><span class="badge">回應率 {pct(rate_p)}（原有 {pct(rate_e)}）</span><span class="badge">{pp(comparison['rate_difference'])}</span><span class="badge">適切度 {score(appr_p['mean'])} / 5（原有 {score(appr_e['mean'])}）</span><span class="badge">評審對照題 {controls_ok}/{controls_total} 符合預期</span><span class="badge">{measured}/{slots} 段對話完成量測</span></div>
<p class="notice">合成對話、臨時資料庫與模擬 LINE 傳輸；Gemini 與評審呼叫都是真的，但沒有傳到任何真實 LINE 帳號。主動貼圖版已在<span class="nowrap"> 2026-10-07（UTC）</span>部署到正式環境；這裡的數字仍是基準測試的結果，不是正式環境的流量。部署的版本另外加了審查後的三項保護：危機回覆一律不附貼圖；中英夾雜的「sticker」與貼圖上打的字也算在談貼圖。它們不會改變這裡任何一個數字：危機那段對話兩個版本都沒送貼圖，另外兩種情況測試裡沒有。</p></header>
<main id="content">
<section class="panel"><h2>結果</h2>{kpis}
<p class="small muted">回應率以實際捕捉到的 LINE 訊息物件計算（不是模型意圖）；AI 評審對每一輪的「有沒有送貼圖」判讀與實際傳輸一致率：原有 {pct(judge_e['wire_agreement'])}、主動 {pct(judge_p['wire_agreement'])}。信賴區間以作者設計的「同一段對話」為單位（連同它的 {design['repeats']} 次重複一起），對兩個版本做配對重抽樣（{comparison.get('draws', 0)} 次）。</p></section>
<section class="panel"><h2>原本為什麼比較少？改了什麼</h2>
<p>原有版本的互動模型其實常常自己選了貼圖，但兩個地方把它丟掉：V3 角色規則寫著「接話留白（rest）時通常不選貼圖」，而宿主只會把貼圖放在主回答與接話之間——沒有接話就沒有位置。道謝、晚安、好啊、回貼圖這些最適合貼圖的時刻，正好最常沒有接話。</p>
<div class="steps"><div class="step"><b>1 · 提示：貼圖與接話分開判斷</b>社交或情緒節拍（打招呼、道謝、好消息、加油、陪對方抱怨、接梗、道別、對方傳貼圖）預設挑一張貼切的圖；中性資訊、需要澄清、敏感情境與說過不要貼圖仍填 null。</div>
<div class="step"><b>2 · 解析：保留模型自己的選擇</b>接話留白不再丟掉模型選好的目錄貼圖；無效輸出、澄清與委派照舊不帶貼圖。</div>
<div class="step"><b>3 · 宿主：沒有接話時接在主回答後</b>沿用既有的「接在後面」位置。使用者本身在談貼圖（拒收、抱怨、詢問、引用）時，仍只有明確要求才會加。冷卻（不連續、五輪最多兩張）、拒收、目錄與五則上限都沒有改。</div></div>
<p class="small muted">原有：{commit_link(refs['existing'])}（量測當時、2026-10-06 的正式環境程式）· 主動貼圖版：{commit_link(refs['proactive'])}。兩個版本由同一個實驗框架執行，各自從自己的原始碼樹載入。仍然只有一次 Gemini 呼叫，沒有額外的選圖模型。</p></section>
<section class="panel"><h2>貼圖漏斗：選了、留下、送出</h2>{funnel_chart}
<div class="scroll"><table class="num"><thead><tr><th>計數</th><th>{ARM_LABELS['existing']}</th><th>{ARM_LABELS['proactive']}</th></tr></thead><tbody>
<tr><th scope="row">全部回合</th><td>{funnel['existing']['turns']}</td><td>{funnel['proactive']['turns']}</td></tr>
<tr><th scope="row">模型選了貼圖、但接話留白</th><td>{funnel['existing']['model_selected_on_rest']}</td><td>{funnel['proactive']['model_selected_on_rest']}</td></tr>
<tr><th scope="row">解析時丟掉</th><td>{funnel['existing']['dropped_at_parse']}</td><td>{funnel['proactive']['dropped_at_parse']}</td></tr>
<tr><th scope="row">宿主沒有保留</th><td>{funnel['existing']['dropped_at_host']}</td><td>{funnel['proactive']['dropped_at_host']}</td></tr>
<tr><th scope="row">接在主回答後送出</th><td>{funnel['existing']['trailing_delivered']}</td><td>{funnel['proactive']['trailing_delivered']}</td></tr>
<tr><th scope="row">路由（direct / 其他）</th><td>{esc(', '.join(f'{k} {v}' for k, v in sorted(actions['existing'].items())))}</td><td>{esc(', '.join(f'{k} {v}' for k, v in sorted(actions['proactive'].items())))}</td></tr>
</tbody></table></div></section>
<section class="panel"><h2>① 貼圖回應率：在哪些時刻變多</h2><div class="grid2"><div>{expectation_chart}</div><div>{fit_chart}</div></div>
<h3>依對話類型</h3><div class="scroll"><table class="num"><thead><tr><th>類型</th><th>{ARM_LABELS['existing']}</th><th>{ARM_LABELS['proactive']}</th></tr></thead><tbody>{category_rows}</tbody></table></div></section>
<section class="panel"><h2>② 貼圖適切度</h2>{score_chart}
<div class="grid2"><div><h3>評審標註的問題（第一次評審）</h3><div class="scroll"><table class="num"><thead><tr><th>問題</th><th>{ARM_LABELS['existing']}</th><th>{ARM_LABELS['proactive']}</th></tr></thead><tbody>{issue_rows}</tbody></table></div></div>
<div><h3>用了哪些貼圖</h3><div class="scroll"><table><thead><tr><th>版本</th><th>不同貼圖</th><th>最常用</th></tr></thead><tbody>{top_rows}</tbody></table></div>
<p class="small muted">第二次獨立評審的平均分數：原有 {score(existing['appropriateness_pass2']['mean'])} · 主動 {score(proactive['appropriateness_pass2']['mean'])}。</p></div></div></section>
<section class="panel"><h2>AI 評審怎麼評</h2>
<p>評審模型 <code>{esc(data['models']['judge'])}</code>（reasoning {esc(data['models']['judge_reasoning'])}），每一輪一份盲評資料：只有這一輪之前實際送達的對話、使用者這一輪的訊息、麻吉這一輪實際送出的 LINE 物件，以及官方貼圖圖檔與目錄描述。看不到版本、模型、時間、宿主狀態或其他回合的分數。</p>
<div class="steps"><div class="step"><b>評估軸一 · 貼圖回應</b><code>sticker_sent</code>：這一輪有沒有送原生貼圖（emoji 不算）。<code>sticker_fit</code>：先只看到使用者這一輪為止，判斷此刻回貼圖「適合／可有可無／應避免」。</div>
<div class="step"><b>評估軸二 · 貼圖適切度</b>只評有送出的貼圖，1–5 分：圖意是否回應這一輪、語氣是否和文字一致、是否用在敏感情境或無視拒收、外文是否好懂；附問題標籤與理由。</div>
<div class="step"><b>可靠度檢查</b>每一輪獨立評兩次：有沒有送貼圖一致 {pct(consistency['proactive']['sticker_sent'])}（主動）／{pct(consistency['existing']['sticker_sent'])}（原有）；時刻判斷一致 {pct(consistency['proactive']['fit'])}／{pct(consistency['existing']['fit'])}；分數相差 1 分以內 {pct(consistency['proactive']['score_within_one'])}／{pct(consistency['existing']['score_within_one'])}。</div></div>
<details><summary>12 題評審對照題（已知合適或不合適的配對）：{controls_ok}/{controls_total} 次判讀符合預期</summary><div class="scroll"><table><thead><tr><th>題號</th><th>預期</th><th>評審（第一次 / 第二次）</th></tr></thead><tbody>{control_table(data)}</tbody></table></div>
<p class="small muted">對照題是作者寫好的固定配對（例如喪親配慶祝圖、晚安配晚安圖），用來確認評審分得出好壞；不是麻吉的量測結果。</p></details>
<p class="small muted">評分規格 SHA-256 <code>{esc(data['judge']['rubric_sha256'][:16])}</code> · 盲評資料 SHA-256 <code>{esc(data['judge']['packets_sha256'][:16])}</code> · 評審呼叫 {data['judge']['attempts']['ok']}/{data['judge']['attempts']['total']} 成功。AI 評審不是人工評分。</p></section>
<section class="panel"><h2>逐輪對照</h2><p>每段對話在全新的資料庫從第一輪開始，同一段對話的兩個版本使用相同的使用者訊息。點選執行次數切換；每一格包含麻吉實際送出的訊息、貼圖圖檔、評審的判斷與宿主紀錄。</p>
{explorer(data)}</section>
<section class="panel"><h2>量測方式與限制</h2>
<ul>
<li>題組：{design['episode_count']} 段合成私訊對話、{design['turn_count']} 輪使用者訊息（其中 {sticker_inputs} 輪是使用者傳 LINE 貼圖）；每段重複 {design['repeats']} 次，主帳號與第二帳號輪替，共 {design['slot_count']} 段量測。作者標註「適合／可有可無／應避免」只用於分析。</li>
<li>路徑：簽章 webhook → 雙帳號內嵌 V3 宿主 → {esc(data['models']['foreground'])}（{esc(data['models']['foreground_thinking'])}，{data['models']['foreground_timeout_s']} 秒視窗）→ 模擬 LINE 傳輸。冷卻、拒收、目錄與五則上限都照正式程式運作；兩個版本的冷卻上限相同（不連續、五輪最多兩張）。</li>
<li>每個版本的每段對話都在獨立的工作程序執行，只載入該版本凍結的原始碼；兩個版本交錯排程，以免供應商在某段時間變慢只影響一邊。</li>
<li>沒有背景執行器：若模型改為委派，該輪只記錄承接文字。範圍是私訊文字與貼圖輸入；沒有測群組、語音、TTS 與委派完成後的回覆。</li>
<li>這是開發用題組，不是正式流量抽樣或保留測試集；模型輸出有隨機性，AI 評審也不等於人工判斷。</li>
<li>程式審查後的兩項修正（只影響分析，不重跑模型）：「此刻適不適合貼圖」改由看不到麻吉回覆的另一次盲評判斷；信賴區間改為以整段對話（含所有重複）為單位重抽樣，區間因此較寬。</li>
</ul>
{rounds_block(data)}
<div class="scroll"><table class="num"><thead><tr><th>前景 Gemini 呼叫（診斷用）</th><th>p50</th><th>p90</th><th>n</th></tr></thead><tbody>{latency_rows}</tbody></table></div>
<p class="small muted">兩個版本每輪都只做一次互動模型呼叫；延遲受供應商當下狀況影響，只作診斷，不是本研究的評估軸。</p>
<p><a href="{JSON_NAME}" download>下載公開結果 JSON</a>（合成對話、送出的訊息、漏斗紀錄與評審判讀；不含提示詞、憑證、記錄檔或本機路徑）。</p></section>
<footer>本頁不重算或混入其他分頁的量測。貼圖圖片直接載入 LINE 官方貼圖伺服器的公開預覽圖。</footer></main>
<script>document.body.classList.remove('nojs');{SCRIPT}</script></body></html>
"""
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("study", nargs="?", type=Path, help="private frozen study directory (with results.json)")
    parser.add_argument("--render", action="store_true", help="re-render the page from the committed public JSON")
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--previous", type=Path, action="append", default=[],
                        help="earlier development round study directories, oldest first")
    args = parser.parse_args()
    target_json, target_page = PUBLIC / JSON_NAME, PUBLIC / PAGE_NAME
    if args.render:
        data = json.loads(target_json.read_text(encoding="utf-8"))
    else:
        if args.study is None:
            parser.error("give a study directory, or --render")
        results = json.loads((args.study / "results.json").read_text(encoding="utf-8"))
        generated = args.generated_at or results["metadata"].get("judge", {}).get("generated_at") or "2026-10-06"
        previous = [round_summary(json.loads((path / "results.json").read_text(encoding="utf-8")),
                                  f"第 {index} 輪") for index, path in enumerate(args.previous, 1)]
        data = project(results, generated_at=generated, previous=previous)
        target_json.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    target_page.write_text(render(data), encoding="utf-8")
    print(json.dumps({"page": str(target_page.relative_to(ROOT)), "json": str(target_json.relative_to(ROOT)),
                      "turns": len(data["turns"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
