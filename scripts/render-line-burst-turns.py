#!/usr/bin/env python3
"""Render the separately frozen synthetic burst study; never rewrite old results."""
from __future__ import annotations
import argparse
import html
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PR = "https://github.com/jefflai108/streaming_taiwanese/pull/453"
REVIEWED_SOURCE = "5da04a4b43073ea7329de066d25fd77837ead2e5"
MANUAL_NOTES = {
    "B001": "原有逐則處理傳了 4 批、7 個文字泡泡。四個實驗版都合成一批；但 A 的卡片本身雖不到 30 字，仍加上多餘的字數解說，且「二十五個字」的說法與卡片不符。合併輸出不代表內容沒有瑕疵。",
    "B002": "五版皆只做一次前景呼叫。實際前景進入為 0.296–0.441 秒，模型請求送出為 0.523–0.699 秒，都早於 1.25 秒的穩定窗；可選接話仍須和主回答一起閱讀。",
    "B003": "五秒後的補充已超過四秒收集上限與兩秒輸入間隔，因此各版保留兩個回合。B 首次傳送在 5.600 秒，晚於第二則抵達的 5.010 秒，第一個接話仍詢問冷凍或現包水餃。有限收集窗不保證所有較晚輸入都能改寫前一個答案。",
    "B004": "原有逐則處理在更正與「只要一句」已抵達後，仍先送出阿明祝福和問題，接著再送兩版小芳祝福。四個實驗版都丟棄舊名字草稿，只送一則小芳祝福、沒有接話。B、C 自行加入「吃不胖」玩笑，屬於額外的語氣選擇。",
    "B005": "四個實驗版皆在一個主回答中保留七色與平面三角形 180 度兩題，沒有接話；原有逐則處理分兩批，第二批重複七色。五版都是兩次模型呼叫，這題沒有省下呼叫；各版完成時間也沒有一致較快。",
    "B006": "四個實驗版各送一個文字泡泡、沒有接話、問題或對錯分析。原有逐則處理在禁止提問已抵達後，仍於 3.733 秒提問、6.639 秒提出梳理分析，最後共 4 批、6 個泡泡。部分實驗回答對「講兩句」而言仍偏長，C 還加上工作比較；組合版最後傳送 13.432 秒，比原有的 12.562 秒慢。",
}
TABS = (("index.html", "Interaction tasks"), ("delegation.html", "Delegation tasks"),
        ("taiwan.html", "台灣用語"), ("recovery.html", "困難任務與失敗恢復"),
        ("tts-followup.html", "TTS follow-up"), ("images-stickers.html", "Images &amp; Stickers"),
        ("burst-turns.html", "Burst turns"))
LABELS = {"baseline": "原有逐則處理", "a": "A · 固定穩定窗", "b": "B · 版本更新",
          "c": "C · 語意承接", "composite": "A + B + C"}
COLORS = {"baseline": "#66766c", "a": "#2965a2", "b": "#bf641c", "c": "#9461b5", "composite": "#227a65"}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def seconds(value):
    return f"{value / 1000:.3f} s" if number(value) else "—"


def stats(rows, key):
    values = [row.get("metrics", {}).get(key) for row in rows
              if key != "last_input_to_last_send_ms" or row.get("observations_complete") is not False]
    values = sorted(value for value in values if number(value))
    if not values:
        return "— · n=0"
    return f"{seconds(statistics.median(values))} / {seconds(values[math.ceil(.95 * len(values)) - 1])} · n={len(values)}"


def observed_count(row, key):
    value = row.get("metrics", {}).get(key)
    return value if type(value) is int and value >= 0 else None


def count_total(rows, key):
    values = [observed_count(row, key) for row in rows]
    known = [value for value in values if value is not None]
    unknown = sum(value is None or row.get("observations_complete") is False
                  for row, value in zip(rows, values))
    if not known:
        return f"未知 · {unknown} 題"
    total = str(sum(known))
    return f"≥ {total} · 未知 {unknown} 題" if unknown else total


def episode_count(row, key):
    value = observed_count(row, key)
    if value is None:
        return "未知"
    return f"≥ {value}" if row.get("observations_complete") is False else str(value)


def timeline(case, policies):
    """Same scale for all arms; rectangles show actual foreground call spans."""
    values = [event["offset_s"] * 1000 for event in case["events"]]
    for row in case["results"]:
        values.extend(call.get("finished_ms", call["started_ms"]) for call in row.get("model_calls", []))
        values.extend(msg["elapsed_ms"] for msg in row.get("messages", []))
    end = max(values + [1000]) * 1.04
    width, left, right = 920, 145, 24
    scale = (width - left - right) / end
    height = 60 + len(policies) * 45
    svg = [f'<svg class="timeline" viewBox="0 0 {width} {height}" role="img" aria-label="各版本模型推論與實際捕捉傳送的時間軸">',
           '<title>藍灰色直線：預定輸入時間；色塊：前景呼叫；圓點：捕捉到的傳送。實際輸入抵達時間另列。</title>']
    for tick in range(6):
        time_ms = end * tick / 5
        x = left + time_ms * scale
        svg.append(f'<path d="M{x:.2f},25V{height-25}" stroke="#dbe5dc"/><text x="{x:.2f}" y="17" text-anchor="middle">{time_ms/1000:.1f}s</text>')
    for event in case["events"]:
        x = left + event["offset_s"] * 1000 * scale
        svg.append(f'<path d="M{x:.2f},25V{height-25}" stroke="#8195ac" stroke-dasharray="3 4"><title>輸入 {event["offset_s"]}s：{esc(event["text"])}</title></path>')
    rows = {row["policy"]: row for row in case["results"]}
    for index, policy in enumerate(policies):
        y, row = 40 + index * 45, rows.get(policy, {})
        svg.append(f'<text x="5" y="{y+4}">{esc(LABELS[policy])}</text>')
        for call in row.get("model_calls", []):
            x = left + call["started_ms"] * scale
            length = max(2, (call.get("finished_ms", call["started_ms"]) - call["started_ms"]) * scale)
            svg.append(f'<rect x="{x:.2f}" y="{y-10}" width="{length:.2f}" height="20" rx="3" fill="{COLORS[policy]}" opacity=".45"><title>前景：{seconds(call["started_ms"])} → {seconds(call.get("finished_ms"))}</title></rect>')
        for msg in row.get("messages", []):
            x = left + msg["elapsed_ms"] * scale
            svg.append(f'<circle cx="{x:.2f}" cy="{y}" r="5" fill="{COLORS[policy]}"><title>捕捉傳送 {seconds(msg["elapsed_ms"])} · {len(msg.get("texts", []))} 個文字泡泡</title></circle>')
    return "".join(svg) + "</svg>"


def arm(row):
    policy = row["policy"]
    metrics = row.get("metrics", {})
    bubbles = []
    for message in row.get("messages", []):
        if message.get("duplicate"):
            continue
        texts = "".join(f'<div class="bubble">{esc(text)}</div>' for text in message.get("texts", []))
        bubbles.append(f'<div class="send"><p class="stamp">{seconds(message["elapsed_ms"])} · {esc(message["channel"])} · {len(message.get("texts", []))} 泡泡</p>{texts}</div>')
    if not bubbles:
        text = "未保留完整的文字傳送紀錄。" if row.get("observations_complete") is False \
            or observed_count(row, "text_bubbles") is None else "沒有捕捉到文字傳送。"
        bubbles.append(f'<p class="muted">{text}</p>')
    calls = "".join(f'<tr><td>{index+1}</td><td>{seconds(call["started_ms"])}</td><td>{seconds(call.get("finished_ms"))}</td><td>{esc(call.get("action", "unknown"))}</td></tr>'
                    for index, call in enumerate(row.get("model_calls", [])))
    inputs = "".join(f'<tr><td>{item["index"]+1}</td><td>{seconds(item["planned_ms"])}</td><td>{seconds(item["arrived_ms"])}</td><td>{esc(item.get("final_status", "unknown"))}</td></tr>'
                     for item in row.get("inputs", []))
    failures = list(row.get("errors", []))
    for outcome in row.get("host_deliveries", []):
        failures.extend(str(outcome[key]) for key in ("failure_code", "error") if outcome.get(key))
    errors = f'<p class="error">{esc(", ".join(dict.fromkeys(failures)))}</p>' if failures else ""
    incomplete = '<p class="muted">紀錄不完整；次數為已觀測下限，未觀測部分未知。</p>' \
        if row.get("observations_complete") is False else ""
    return (f'<section class="arm" style="--color:{COLORS[policy]}"><h3>{esc(LABELS[policy])}</h3>'
        f'<p class="status">{esc(row["status"])} · {episode_count(row, "model_calls")} 次前景 · '
        f'{episode_count(row, "transport_batches")} 批 / {episode_count(row, "text_bubbles")} 文字泡泡</p>'
        f'<dl><dt>首個前景啟動</dt><dd>{seconds(metrics.get("first_foreground_start_ms"))}</dd>'
        f'<dt>首個模型請求送出</dt><dd>{seconds(metrics.get("first_model_start_ms"))}</dd>'
        f'<dt>首次 / 最後傳送</dt><dd>{seconds(metrics.get("first_send_ms"))} / {seconds(metrics.get("last_send_ms"))}</dd>'
        f'<dt>最後輸入 → 最後傳送</dt><dd>{seconds(metrics.get("last_input_to_last_send_ms"))}</dd></dl>'
        + errors + incomplete + "".join(bubbles)
        + '<details><summary>前景呼叫時間</summary><table><thead><tr><th>次</th><th>開始</th><th>完成</th><th>路由</th></tr></thead><tbody>'
        + calls + '</tbody></table></details><details><summary>實際輸入時間與處理狀態</summary><table><thead><tr><th>則</th><th>預定</th><th>抵達</th><th>最終狀態</th></tr></thead><tbody>'
        + inputs + '</tbody></table></details></section>')


def render(data):
    plan, cases = data["plan"], data["cases"]
    policies = plan["policies"]
    if data.get("schema_version") != 1 or set(policies) - set(LABELS):
        raise ValueError("unsupported_burst_results")
    nav = ''.join(f'<a href="{file}"' + (' aria-current="page"' if file == 'burst-turns.html' else '') + f'>{title}</a>' for file, title in TABS)
    source_pr = f'<a href="{esc(SOURCE_PR)}">程式 PR</a>' if SOURCE_PR else "程式 PR"
    source_commit = SOURCE_PR.rsplit("/pull/", 1)[0] + "/commit/" + plan["source_ref"]
    overview = []
    for policy in policies:
        rows = [row for case in cases for row in case["results"] if row["policy"] == policy]
        overview.append(f'<tr><th>{esc(LABELS[policy])}</th><td>{sum(row["status"] == "ok" for row in rows)}/{len(rows)}</td>'
            f'<td>{stats(rows, "first_model_start_ms")}</td><td>{stats(rows, "first_send_ms")}</td>'
            f'<td>{stats(rows, "last_input_to_last_send_ms")}</td>'
            f'<td>{count_total(rows, "model_calls")}</td>'
            f'<td>{count_total(rows, "text_bubbles")}</td></tr>')
    cards = []
    for case in cases:
        inputs = ''.join(f'<li><time>+{event["offset_s"]:g}s</time> {esc(event["text"])}</li>' for event in case["events"])
        search = esc(case["id"] + ' ' + case["name"] + ' ' + ' '.join(e["text"] for e in case["events"]))
        note = MANUAL_NOTES.get(case["id"]) if plan["source_ref"] == REVIEWED_SOURCE else None
        observation = f'<p class="review"><strong>本次人工閱讀（未評分）：</strong>{esc(note)}</p>' if note else ""
        cards.append(f'<article class="case" data-kind="{esc(case["kind"])}" data-search="{search}"><h2>{esc(case["id"])} · {esc(case["name"])}</h2>'
            f'<ol class="inputs">{inputs}</ol><p class="review"><strong>閱讀重點：</strong>{esc(case["review_goal"])}</p>'
            + observation +
            '<p class="muted">時間軸：虛線是預定輸入，色帶是前景推論，圓點是捕捉到的傳送。各版實際抵達時間可在下方展開查看。</p>'
            '<div class="scroll">' + timeline(case, policies) + '</div>'
            '<div class="arms">' + ''.join(arm(row) for row in case["results"]) + '</div></article>')
    kinds = ''.join(f'<option value="{esc(kind)}">{esc(kind)}</option>' for kind in sorted({case["kind"] for case in cases}))
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Burst turns · LINE v3</title><link rel="canonical" href="https://jefflai108.github.io/line-v3/burst-turns.html">
<style>:root{font-family:system-ui,-apple-system,sans-serif;color:#19352b;background:#f5f7f2;font-synthesis:none}*{box-sizing:border-box}body{margin:0}a{color:#216b64}header,main,.tabs{max-width:1600px;margin:auto;padding:24px}.tabs{display:flex;gap:9px;flex-wrap:wrap;border-bottom:1px solid #dbe5db}.tabs a{text-decoration:none;padding:8px 11px;border-radius:8px;background:#e8eee7;font-size:14px}.tabs [aria-current]{background:#224d3d;color:white}header{padding-top:35px}h1{font-size:clamp(30px,5vw,49px);margin:.2em 0}h2{font-size:22px}h3{font-size:16px}.lead{max-width:950px;line-height:1.7}.notice,.review{background:#eaf0e6;border-left:3px solid #648665;padding:14px;line-height:1.7}.muted,.stamp,footer{color:#63756b}.panel,.case{border:1px solid #d7e2d5;background:#fff;border-radius:14px;padding:23px;margin:0 0 25px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px 9px;border-bottom:1px solid #dce5db;white-space:nowrap}.arms{display:grid;grid-template-columns:repeat(''' + str(len(policies)) + ''',minmax(0,1fr));gap:14px}.arm{border-top:4px solid var(--color);min-width:0;padding-top:8px}.arm h3{color:var(--color)}.status,dl{font-size:12px;line-height:1.6}dl{display:grid;grid-template-columns:1fr;margin-bottom:20px}dt{color:#687a6d}dd{margin:0 0 5px}.bubble{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf3e9;border:1px solid #dce7d8;border-radius:11px;padding:12px;margin:7px 0;font-size:14px;line-height:1.75}.stamp{font-size:11px;margin-bottom:3px}.send{margin-bottom:20px}.inputs{padding-left:23px;line-height:1.8}.inputs time{font-variant-numeric:tabular-nums;color:#356558;display:inline-block;min-width:55px}.timeline{width:100%;min-width:650px;font-size:12px;margin:10px 0 25px}.controls{display:flex;gap:18px;flex-wrap:wrap;margin:20px 0}label{font-size:13px;display:grid;gap:6px}input,select{font:inherit;background:white;border:1px solid #bacdbb;border-radius:7px;padding:10px}details{font-size:12px;overflow:auto;margin-top:12px}summary{cursor:pointer;color:#216b64}code{overflow-wrap:anywhere;font-size:12px}.error{color:#a1372d}.case[hidden]{display:none}footer{padding:20px;font-size:12px}.skip{position:absolute;left:-9999px}.skip:focus{left:10px;top:10px;background:white;padding:10px}@media(max-width:1100px){.arms{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){header,main,.tabs{padding:16px}.panel,.case{padding:16px}.arms{grid-template-columns:1fr}.tabs a{font-size:12px;padding:7px}input{max-width:100%}}</style></head><body><a class="skip" href="#main">跳至量測內容</a><nav class="tabs" aria-label="比較分頁">''' + nav + '''</nav><header><p class="muted">HeyMachi / LINE 架構比較</p><h1>Burst turns</h1><p class="lead">連續幾則訊息算一個對話回合。第一則抵達便啟動模型；這裡比較後續補充抵達時，何時更新草稿、何時發出回答。主回答與接話一起計入完整輸出。</p>
<p class="notice">合成情境、真實 Gemini 前景呼叫、隔離儲存與本機捕捉 LINE 傳輸。沒有傳送真實 LINE 訊息。五版都包含目前前景同次生成的語音標籤欄位；本頁停用音訊合成，沒有 ElevenLabs 呼叫，只量測文字輸出。每題每版一次；沒有自動品質評審或品質分數，下方附人工閱讀觀察，文字請逐題檢視。泡泡較少不等於答案較好，推論開始也不同於用戶看到回答。</p>
<p class="muted">組合版是本次''' + source_pr + '''中的建議預設；該 PR 尚未合併。這份靜態報告的發布與 LINE 服務部署分開；服務尚未套用本次修改。</p>
<p class="muted">時間來自共用開發主機；其他服務可能仍在運作。本次逐題依序執行，期間停下我們的測試與建置。這些是開發環境觀測，不代表正式服務 SLO，也不支持統計顯著性的結論。</p>
<p class="muted">另保留<a href="burst-turns-interrupted-3ae1185e.public.json" download>先前來源版本的兩筆已完成量測</a>：第一次執行開始後發現上游合併衝突，因此在單次量測之間停止，完成合併後重新凍結整組 30 次量測。這兩筆不納入下方比較；其餘 28 筆當時未執行，不算失敗。</p>
<p class="muted">量測版本：''' + esc(plan['revision']) + ' · ' + str(len(cases)) + ''' 題 · ''' + str(len(policies)) + ''' 版本。前景：Gemini 3.8 Flash low，40 秒上限。</p><p>來源：<a href="''' + esc(source_commit) + '''"><code>''' + esc(plan['source_ref']) + '''</code></a> · <a href="burst-turns-results.public.json" download>下載完整公開結果 JSON</a></p></header><main id="main">
<section class="panel"><h2>五種處理方式</h2><p class="lead">原有逐則處理保留每則訊息的回覆。A 在立即推論後設 1.25 秒的最早發布時間，需要時更新一次；B 依訊息版本更新過期草稿，等安靜 1.25 秒或收集上限；C 使用 A 的時序，加上同次推論的語意承接指示；組合版使用 B 的時序與語意指示。收集上限為 4 秒，最多更新 3 次。這些數值是本次實驗設定。</p><p class="muted">基準版保留加入分段政策前的提示文字，僅移除新增的分段政策章節；四個實驗版共用新提示，C 與組合版才啟用語意承接欄位。其他模型設定一致。語意承接使用同一次前景推論，不增加分類模型。</p></section>
<section class="panel"><h2>量測概覽</h2><p class="muted">時間單位為秒，顯示 p50 / nearest-rank p95 與有效 n。小樣本 p95 常為最大值；失敗保留，缺少的時間不填零，不完整紀錄不計入最終傳送延遲。Runtime ok 表示沒有觀測到模型或主機處理失敗，不是答案品質評分。次數的 ≥ 表示已觀測小計的下限；未知題數包含缺漏或不完整紀錄，不能當作零次呼叫或零個泡泡。各情境不同，逐題時間軸是主要比較依據。</p><div class="scroll"><table><thead><tr><th>版本</th><th>Runtime ok</th><th>首個模型送出</th><th>首次傳送</th><th>最後輸入 → 最後傳送</th><th>前景呼叫總數</th><th>文字泡泡總數</th></tr></thead><tbody>''' + ''.join(overview) + '''</tbody></table></div></section>
<div class="controls"><label>找情境<input id="search" type="search" placeholder="題號、訊息或標題"></label><label>情境類型<select id="kind"><option value="all">全部</option>''' + kinds + '''</select></label><p id="count" aria-live="polite"></p></div>''' + ''.join(cards) + '''<footer>原有 Interaction、Delegation、台灣用語、Recovery 與 TTS 報告保留各自凍結的量測；本頁不重算歷史分數。所有回答與錯誤保留，沒有挑選較好的重跑結果。</footer></main><script>
const search=document.getElementById('search'),kind=document.getElementById('kind'),cards=[...document.querySelectorAll('.case')];
function filter(){let n=0;for(const card of cards){const visible=(kind.value==='all'||card.dataset.kind===kind.value)&&card.dataset.search.toLowerCase().includes(search.value.trim().toLowerCase());card.hidden=!visible;if(visible)n++;}document.getElementById('count').textContent=`${n} / ${cards.length} 題`;}
search.addEventListener('input',filter);kind.addEventListener('change',filter);filter();
</script></body></html>'''


def install(results, public):
    raw = Path(results).read_bytes()
    data = json.loads(raw)
    content = render(data)
    public.mkdir(parents=True, exist_ok=True)
    (public / 'burst-turns-results.public.json').write_bytes(raw)
    (public / 'burst-turns.html').write_text(content)
    for name, _title in TABS[:-1]:
        target = public / name
        original = target.read_text()
        match = re.search(r'<nav class="tabs"[^>]*>.*?</nav>', original, re.S)
        if match is None:
            raise ValueError('missing_active_navigation:' + name)
        if 'burst-turns.html' not in match.group():
            revised = match.group()[:-6] + '<a href="burst-turns.html">Burst turns</a></nav>'
            target.write_text(original[:match.start()] + revised + original[match.end():])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--public', type=Path, default=ROOT / 'public/line-v3')
    args = parser.parse_args()
    install(args.results, args.public)
