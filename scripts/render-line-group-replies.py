#!/usr/bin/env python3
"""Render the frozen hermetic V3 group-reply study; never rewrite old results.

Input is ``group-replies-results.public.json`` from
``serve/line_agent_v2/evals/line_architecture/run_group_reply.py`` in
jefflai108/streaming_taiwanese. The page compares the baseline (main before the
change) with the candidate on one question: does Machi answer exactly the
group messages it should?
"""
from __future__ import annotations
import argparse
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/jefflai108/streaming_taiwanese"
SOURCE_PR = REPO + "/pull/571"
PAGE = "group-replies.html"
RESULTS = "group-replies-results.public.json"
CATEGORIES = (
    ("addressed", "原本就會回應", "標註、@All、語音與標註後的回覆：改版不應改變。"),
    ("reply", "回覆麻吉的訊息（本次修正）", "成員用 LINE 的「回覆」引用麻吉先前的訊息，沒有標註。"),
    ("quiet", "應保持安靜", "群組閒聊與不是對麻吉說的回覆，只當聊天背景。"),
)
ARMS = (("baseline", "原有"), ("candidate", "改版"))
# Reader-facing titles; the measurement records keep their harness wording.
TITLES = {
    "A1": "@麻吉 標註", "A2": "@All 標註", "A3": "標註並回覆麻吉的回答", "A4": "語音訊息（沒有標註）",
    "R1": "回覆麻吉的回答", "R2": "連續回覆：回覆麻吉對上一則回覆的回答", "R3": "回覆麻吉的接話問題",
    "R4": "回覆麻吉送的貼圖", "R5": "用貼圖回覆麻吉", "R6": "回覆麻吉的入群介紹",
    "R7": "有人收回別的訊息後，回覆麻吉", "R8": "有成員退群後，回覆麻吉", "R9": "回覆麻吉對語音訊息的回答",
    "R10": "回覆稍後推送的接話", "R11": "回覆麻吉送出的提醒", "R12": "麻吉問所在城市，用回覆告訴它",
    "Q1": "沒有標註的閒聊", "Q2": "回覆其他成員的訊息", "Q3": "回覆麻吉，但標註了其他成員",
    "Q4": "回覆找不到來源的訊息", "Q5": "沒有回覆任何訊息的貼圖",
    "Q6": "麻吉離群又被邀回後，回覆離群前的訊息", "Q7": "回覆麻吉轉錄的成員語音逐字稿",
}
NOTES = {
    "R5": "貼圖上的字要求設定提醒；貼圖本身不會授權任何動作。",
    "R7": "收回訊息只移除之後回答可被引用的內容，不會讓麻吉忘記那是它的訊息。",
    "R10": "V3 約一半的接話由語音佇列稍後推送。",
    "R12": "也確認回答記下了成員的時區。",
    "Q6": "麻吉離開群組時，會忘記它在該群說過的話。",
    "Q7": "逐字稿是說話成員的話；回覆它是在回應那位成員。",
}
POLICIES = {1: "標註", 2: "背景", 3: "語音", 4: "回覆麻吉"}
EXTRAS = {
    "effect_tasks": lambda values: "未建立任何任務" if values and all(v == 0 for v in values) else f"任務 {values}",
    "timezone_recorded": lambda values: "已記下時區" if values and all(values) else "未記下時區",
    "follow_up_sent": lambda values: "接話泡泡已送出" if values and all(values) else "接話未送出",
    "follow_up_pushed": lambda values: "延後接話已推送" if values and all(values) else "延後接話未推送",
    "sticker_sent": lambda values: "麻吉貼圖已送出" if values and all(values) else "貼圖未送出",
}


def esc(value):
    return html.escape(str(value), quote=True)


def pct(hits, runs):
    return f"{100 * hits / runs:.1f}%" if runs else "—"


def ms(value):
    return f"{value:.1f} ms" if type(value) in (int, float) and math.isfinite(value) else "—"


def short(commit):
    return commit[:8]


def validate(data):
    if data.get("schema") != "line-v3.group-replies.v1":
        raise ValueError("unsupported_group_reply_results")
    arms = data.get("arms", {})
    if set(arms) != {name for name, _label in ARMS}:
        raise ValueError("unsupported_group_reply_arms")
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("invalid_group_reply_cases")
    for name, _label in ARMS:
        missing = [case_id for case_id in ids if case_id not in arms[name]["per_case"]]
        if missing:
            raise ValueError("missing_group_reply_case:" + ",".join(missing))
        if any(code != 0 for code in arms[name]["pytest_returncodes"]):
            raise ValueError("harness_errors_in_results")
    return data


def mark(row, expected):
    runs, answered = row["runs"], row["answered"]
    verb = "回應" if expected == "answer" else "安靜"
    good = row["correct"] == runs
    text = f"{answered}/{runs} 次回應" if expected == "answer" else (
        f"{runs - answered}/{runs} 次安靜" if answered == 0 else f"{answered}/{runs} 次誤回")
    return (f'<span class="verdict {"ok" if good else "bad"}" title="預期{verb}">'
            f'{"✓" if good else "✗"}</span> {esc(text)}')


def details(case, row):
    notes = []
    quoted = row.get("quoted_context") or []
    if quoted:
        notes.append("模型收到被回覆的麻吉原句" if all(quoted) else f"引用內容 {sum(quoted)}/{len(quoted)}")
    for key, render in EXTRAS.items():
        if key in row.get("extras", {}):
            notes.append(render(row["extras"][key]))
    policies = [value for value in row.get("sealed_policy", []) if value is not None]
    if policies:
        notes.append("入站分類：" + "/".join(POLICIES.get(value, str(value)) for value in policies))
    return "；".join(notes)


def kpi(label, value, before, delta, note):
    return (f'<div class="kpi"><p class="label">{esc(label)}</p><div class="values"><span class="value">{esc(value)}</span>'
            f'<span class="arrow">←</span><span class="from">{esc(before)}</span></div>'
            f'<p class="delta">{esc(delta)}</p><p class="small">{esc(note)}</p></div>')


def render(data):
    data = validate(data)
    arms = data["arms"]
    base, cand = arms["baseline"], arms["candidate"]
    refs = data["arms_refs"]

    def rate(arm, category):
        value = arm["answered"][category]
        return value["hits"], value["runs"]

    reply_b, reply_c = rate(base, "reply"), rate(cand, "reply")
    addr_b, addr_c = rate(base, "addressed"), rate(cand, "addressed")
    quiet_b, quiet_c = rate(base, "quiet"), rate(cand, "quiet")
    total_b, total_c = base["correct_total"], cand["correct_total"]
    kpis = "".join((
        kpi("回覆麻吉的訊息後有回應", pct(*reply_c), pct(*reply_b),
            f"+{100 * (reply_c[0] / reply_c[1] - reply_b[0] / reply_b[1]):.1f} 個百分點",
            f"{reply_c[0]}/{reply_c[1]} 次（原有 {reply_b[0]}/{reply_b[1]}）"),
        kpi("標註、@All、語音照常回應", pct(*addr_c), pct(*addr_b), "沒有改變",
            f"{addr_c[0]}/{addr_c[1]} 次（原有 {addr_b[0]}/{addr_b[1]}）"),
        kpi("不該回應卻回應", f"{quiet_c[0]}/{quiet_c[1]}", f"{quiet_b[0]}/{quiet_b[1]}", "沒有誤回",
            "閒聊、回覆成員、轉錄稿等控制組"),
        kpi("整體符合預期", f'{total_c["hits"]}/{total_c["runs"]}', f'{total_b["hits"]}/{total_b["runs"]}',
            f'+{total_c["hits"] - total_b["hits"]} 次', f'{len(data["cases"])} 個情境 × {data["samples"]} 次'),
    ))
    sections = []
    for category, title, blurb in CATEGORIES:
        rows = []
        for case in data["cases"]:
            if case["category"] != category:
                continue
            b, c = base["per_case"][case["id"]], cand["per_case"][case["id"]]
            note = esc(NOTES.get(case["id"], case.get("note") or ""))
            extra = esc(details(case, c))
            rows.append(f'<tr><th scope="row">{esc(case["id"])}</th><td>{esc(TITLES.get(case["id"], case["title"]))}'
                        + (f'<small>{note}</small>' if note else "") + '</td>'
                        f'<td>{"回應" if case["expected"] == "answer" else "安靜"}</td>'
                        f'<td>{mark(b, case["expected"])}</td><td>{mark(c, case["expected"])}</td>'
                        f'<td class="detail">{extra}</td></tr>')
        sections.append(f'<section class="panel"><h2>{esc(title)}</h2><p class="muted">{esc(blurb)}</p>'
                        '<div class="scroll"><table><thead><tr><th>題號</th><th>情境</th><th>預期</th>'
                        '<th>原有</th><th>改版</th><th>改版細節</th></tr></thead><tbody>'
                        + "".join(rows) + '</tbody></table></div></section>')
    timing = (f'<tr><th scope="row">原有</th><td>{ms(base["ingest_ms"]["median"])}</td><td>{ms(base["ingest_ms"]["p90"])}</td>'
              f'<td>{ms(base["ingest_ms"]["max"])}</td><td>{base["ingest_ms"]["n"]}</td></tr>'
              f'<tr><th scope="row">改版</th><td>{ms(cand["ingest_ms"]["median"])}</td><td>{ms(cand["ingest_ms"]["p90"])}</td>'
              f'<td>{ms(cand["ingest_ms"]["max"])}</td><td>{cand["ingest_ms"]["n"]}</td></tr>')
    env = data["environment"]
    load = ", ".join(f"{value:g}" for value in env.get("load_average_at_end", []))
    nav = '<nav class="tabs" aria-label="比較分頁"><a href="group-replies.html" aria-current="page">Group replies</a></nav>'
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Group replies · LINE v3</title><link rel="canonical" href="https://jefflai108.github.io/line-v3/{PAGE}">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f3ee;color:#193a31;font:15px/1.65 system-ui,-apple-system,'PingFang TC',sans-serif}}
header,main,.navwrap{{max-width:1500px;margin:auto;padding:24px 30px}}h1{{font-size:clamp(32px,5vw,52px);line-height:1.15;margin:15px 0}}
h2{{font-size:22px;line-height:1.4;margin:0 0 12px}}a{{color:#23695d}}a:focus-visible{{outline:3px solid #269890;outline-offset:3px}}
p{{margin:9px 0}}.eyebrow,.small,small{{font-size:12px;color:#526c61}}.muted{{color:#5f7168}}.lede{{font-size:17px}}
.panel{{border:1px solid #d6e0d7;border-radius:15px;background:white;padding:22px;margin-bottom:22px}}
.notice{{padding:14px 18px;background:#e8efeb;border:1px solid #cdded3;border-radius:12px}}
.tabs{{display:flex;gap:5px;flex-wrap:wrap;background:#e3e9e2;padding:6px;border-radius:10px}}.tabs a{{padding:8px 12px;text-decoration:none;border-radius:7px;font-size:13px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));gap:16px;margin:18px 0}}.kpi{{border:1px solid #dce5de;border-radius:12px;padding:18px;background:#f8faf7}}
.kpi .label{{font-size:13px;color:#526c61;margin:0 0 6px}}.kpi .values{{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap}}
.kpi .value{{font-size:34px;font-weight:650;line-height:1.1}}.kpi .from{{font-size:22px;color:#5f7168;font-weight:500}}.kpi .arrow{{font-size:20px;color:#5f7168}}
.kpi .delta{{font-size:13px;font-weight:600;color:#1d6f55;margin:8px 0 0}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:880px;font-size:14px;overflow-wrap:normal;word-break:normal}}th,td{{text-align:left;vertical-align:top;padding:11px 10px;border-bottom:1px solid #dce5db}}
thead th{{font-size:12px;color:#526c61;font-weight:600;white-space:nowrap}}tbody th{{white-space:nowrap}}td small{{display:block;margin-top:4px}}
td.detail{{font-size:13px;color:#3f5a4f;min-width:240px}}td:nth-child(2){{min-width:260px}}td:nth-child(n+3):nth-child(-n+5){{white-space:nowrap}}.verdict{{display:inline-block;width:1.4em;font-weight:700}}.verdict.ok{{color:#1d6f55}}.verdict.bad{{color:#a1372d}}
ol.policy{{margin:8px 0 0;padding-left:22px}}code{{font-size:12px;overflow-wrap:anywhere}}footer{{padding:20px 0;font-size:12px;color:#5f7168}}
.skip{{position:absolute;left:-9999px}}.skip:focus{{left:10px;top:10px;background:white;padding:10px}}
@media(max-width:760px){{header,main,.navwrap{{padding:16px}}.panel{{padding:16px}}.kpi .value{{font-size:28px}}}}
</style></head><body><a class="skip" href="#main">跳到比較結果</a><div class="navwrap">{nav}</div>
<header><p class="eyebrow">HeyMachi / LINE v3 · 2026-10-11 · 群組裡回覆麻吉 · 合成群組對話（不呼叫模型）</p><h1>Group replies</h1>
<p class="lede">LINE v3 群組裡，麻吉應該回應這四種訊息：</p>
<ol class="policy"><li>@麻吉</li><li>@All</li><li>語音訊息</li><li>成員用 LINE 的「回覆」功能回覆麻吉先前的任何訊息，即使沒有標註</li></ol>
<p class="lede">其他群組訊息只當作聊天背景、不回覆。改版前，第四種被當成背景、麻吉不會回覆；這一頁比較改版前的原有版本與修正版。</p>
<div class="kpis">{kpis}</div>
<p class="notice">每個情境都走真實的 LINE webhook 簽章驗證、SQLite 儲存、V3 執行流程與 LINE 訊息序列化；模型 HTTP 與 LINE 傳輸是模擬的，每則送出的訊息都拿到 LINE 格式的訊息 ID。沒有呼叫 Gemini、沒有傳到任何真實 LINE 帳號。這裡量的是「麻吉該不該回應」的判斷，不評估回答內容的品質。改版還沒部署到正式環境：合併程式不會部署，正式環境要另外升級。</p>
<p class="small">原有：<a href="{REPO}/commit/{esc(refs["baseline"]["commit"])}"><code>{short(refs["baseline"]["commit"])}</code></a>（main，改版前）· 改版：<a href="{REPO}/commit/{esc(refs["candidate"]["commit"])}"><code>{short(refs["candidate"]["commit"])}</code></a>（<a href="{SOURCE_PR}">PR #571</a>）。兩個版本由同一份量測程式執行，各自從自己的原始碼樹載入。</p>
</header><main id="main">
{"".join(sections)}
<section class="panel"><h2>入站處理時間</h2><p class="muted">從收到簽章 webhook 到排入佇列（含改版新增的「是不是回覆麻吉」查詢）。共用開發主機在量測時負載很高（結束時 load average {esc(load)}），只適合比較兩版的相對差異，不代表正式環境的延遲。</p>
<div class="scroll"><table><thead><tr><th>版本</th><th>中位數</th><th>p90</th><th>最大</th><th>n</th></tr></thead><tbody>{timing}</tbody></table></div></section>
<section class="panel"><h2>怎麼判斷「是麻吉的訊息」</h2><p>每則送出的麻吉訊息都把 LINE 回傳的訊息 ID 以金鑰雜湊記下（只記「是麻吉送的」，不存內容）：回答、接話、延後推送的接話、貼圖、圖片、提醒、入群介紹、錯誤通知與委派結果。成員收回訊息或有人退群時，可以被引用的內容會照隱私規則移除，但「這是麻吉的訊息」仍保留，所以回覆照樣會被回應。清除記憶、麻吉離開群組，或超過每個群組最新 1,000 則的上限，才會忘記。語音轉錄稿是說話成員的話，回覆它是在回應那位成員，不算回覆麻吉。</p>
<p class="small">量測：{esc(data["method"])} 每個版本 {data["samples"]} 次完整執行；Python {esc(env.get("python", ""))} · 產生時間 {esc(data["generated_at"])}。</p>
<p><a href="{RESULTS}" download>下載公開結果 JSON</a>（合成情境的判斷紀錄與時間，不含提示詞、憑證、記錄檔或本機路徑）。</p></section>
<footer>原有分頁保留各自凍結的量測；本頁不重算其他分頁。所有執行結果都保留，沒有挑選重跑。</footer></main></body></html>'''


def install(results, public):
    raw = Path(results).read_bytes()
    content = render(json.loads(raw))
    public.mkdir(parents=True, exist_ok=True)
    (public / RESULTS).write_bytes(raw)
    (public / PAGE).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--public", type=Path, default=ROOT / "public/line-v3")
    args = parser.parse_args()
    install(args.results, args.public)
