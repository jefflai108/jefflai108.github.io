#!/usr/bin/env python3
"""Render the separately frozen interaction TTS study from sanitized receipts."""
from collections import Counter
import html
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public/line-v3'
ARM = 'v3_hermes_gemini'
DIMS = {'task_completion': '任務完成', 'grounding': '依據', 'usefulness': '實用性',
        'clarity': '清晰度', 'character': '麻吉性格', 'instruction_following': '遵循指示', 'taiwan_usage': '台灣用語'}
REASONS = {'selected': '符合條件，已選用語音', 'no_follow_up': '模型選擇不接話',
           'not_verified_mandarin': '非國語或語言驗證未通過', 'not_direct_interaction': '委派／任務控制，禁止 TTS',
           'not_interaction': '安靜觀察，沒有回覆', 'response_not_ok': '回覆失敗或降級',
           'probability_not_selected': '未抽中語音'}


def e(value):
    return html.escape(str(value), quote=True)


def seconds(value):
    return '—' if type(value) not in (int, float) else f'{value / 1000:.2f} 秒'


def stats(values):
    values = sorted(v for v in values if type(v) in (int, float) and math.isfinite(v))
    return f'{seconds(statistics.median(values))} / {seconds(values[math.ceil(len(values)*.95)-1])} · n={len(values)}' if values else '— · n=0'


def counts(values):
    return '、'.join(f'{e(k)} {v}' for k, v in sorted(Counter(values).items())) or '—'


def cohort(case):
    if case['id'].startswith('E'):
        return 'E'
    if case['id'].startswith('S'):
        return 'S'
    return 'G-observation' if case['benchmark_lane'] == 'group_observation' else 'G-reply'


def quality(cases):
    rows = []
    for key, title in DIMS.items():
        values = [c.get('quality_five_way', {}).get('dimensions', {}).get(ARM, {}).get(key) for c in cases]
        values = [v for v in values if type(v) in (int, float)]
        rows.append(f'<tr><th scope="row">{title}</th><td>{statistics.mean(values):.2f} / 5</td><td>{len(values)}</td></tr>' if values
                    else f'<tr><th scope="row">{title}</th><td>—</td><td>0</td></tr>')
    return '<table class="quality"><thead><tr><th>文字品質指標</th><th>平均</th><th>有效題數</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def main():
    data = json.loads((PUBLIC / 'tts-followup-results.public.json').read_text())
    cases, meta = data['cases'], data['metadata']
    css = re.search(r'<style>(.*?)</style>', (PUBLIC / 'index.html').read_text(), re.S)[1]
    css += '''\n.steps{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}.step{min-width:0;background:#f8faf7;padding:16px;border:1px solid #dce5de;border-radius:10px}.step h3{font-size:15px}.step .text{margin-bottom:0}.step audio{width:100%;margin:12px 0}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metrics strong{display:block;font-size:28px}.step .empty{color:#65766e}.case h2{font-size:19px}.cohort-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.case .quality{font-size:11px}.case .quality th,.case .quality td{white-space:normal}.summary-table{min-width:690px}.text{font-size:15px}audio:focus-visible{outline:3px solid #258f9e;outline-offset:4px}@media(max-width:900px){.steps,.cohort-grid{grid-template-columns:1fr}.metrics{grid-template-columns:1fr 1fr}}'''
    nav = '<nav class="tabs" aria-label="比較分頁">' + ''.join(f'<a href="{url}"' + (' aria-current="page"' if url == 'tts-followup.html' else '') + f'>{label}</a>'
        for url, label in [('index.html', 'Interaction tasks'), ('delegation.html', 'Delegation tasks'), ('taiwan.html', '台灣用語'), ('recovery.html', '困難任務與失敗恢復'), ('tts-followup.html', 'TTS follow-up')]) + '</nav>'
    parts = [f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HeyMachi · TTS follow-up</title><meta name="robots" content="noindex,nofollow"><link rel="canonical" href="https://jefflai108.github.io/line-v3/tts-followup.html"><style>{css}</style></head><body><a class="skip" href="#main">跳至比較內容</a><div class="navwrap">{nav}</div>',
        '<header><p class="muted">HeyMachi / LINE v3 · 獨立實測</p><h1>接話，換成 Zack 的聲音</h1><p>Eleven v4 Turbo · Zack · v3 (Hermes, gemini-3.8-flash medium)</p>',
        '<p class="notice">本頁強制為所有符合條件的國語接話產生語音。正式服務的提案機率為 10%，本次沒有啟用。主回答仍是文字；無接話、非國語、委派工作與安靜觀察皆不產生音訊。</p>',
        '<p class="small muted">同一批 69 個合成案例重新量測，各題一次，不挑最好結果。前景 Gemini 3.8 Flash 使用 low；標籤中的 medium 是 Hermes 執行腦設定，直接互動不會呼叫 Hermes。語言標註加入原本的同一次推論。</p>',
        f'<p class="small">凍結來源 <code>{e(meta["source_ref"])}</code> · {e(meta["created_utc"][:10])} · <a href="tts-followup-results.public.json" download>下載完整結果 JSON</a> · <a href="tts-followup-line-validation.json" download>LINE 驗證紀錄</a></p></header><main id="main">']
    headline = [c for c in cases if cohort(c) != 'G-observation']
    audio = [c[ARM]['tts'] for c in headline if c[ARM].get('tts', {}).get('status') == 'ok']
    follow = sum(bool(c[ARM].get('follow_up')) for c in headline)
    eligible = sum(c[ARM].get('tts', {}).get('gate', {}).get('eligible', False) for c in headline)
    failures = sum(c[ARM].get('tts', {}).get('status') == 'error' for c in headline)
    parts.append('<section class="panel"><h2>這次產生了多少語音？</h2><div class="metrics">' + ''.join(
        f'<div><strong>{value}</strong>{label}</div>' for value,label in [(len(headline),'回覆情境（另有 8 題安靜觀察）'),(follow,'有接話文字'),(eligible,'符合國語 TTS 條件'),(len(audio),'成功音訊')]) + '</div>'
        f'<p class="small">TTS 失敗 {failures}；若失敗，保留接話文字。國語允許少量英文名稱或術語；模型語言標註＋漢字比例檢查仍可能誤判，不宣稱能完美分辨所有漢語。</p></section>')
    parts.append('<section class="panel"><h2>延遲：LLM → 接話音訊可用</h2><p>各欄為中位數 / p95。p95 使用 nearest rank。整體可用時間＝LLM 回覆時間＋TTS 階段（含檔案寫入、長度探測及完整解碼），是兩段量測的加總。未產生音訊的題目保留文字路徑。</p><div class="scroll" tabindex="0"><table class="quality summary-table"><thead><tr><th>情境</th><th>全部 LLM 嘗試</th><th>LLM 有回覆</th><th>整體可用</th><th>有音訊題的整體可用</th></tr></thead><tbody>')
    names = {'E': 'E · 模型互動（50）', 'S': 'S · 原生貼圖（6）', 'G-reply': 'G · 群組回覆（5）', 'G-observation': 'G · 安靜觀察（8）'}
    for key,title in names.items():
        rows = [c[ARM] for c in cases if cohort(c) == key]
        parts.append(f'<tr><th scope="row">{title}</th>' + ''.join(f'<td>{stats(r.get(metric) for r in rows)}</td>' for metric in ('latency_ms','llm_latency_ms','overall_ready_ms'))
            + f'<td>{stats(r.get("overall_ready_ms") for r in rows if r.get("tts",{}).get("status")=="ok")}</td></tr>')
    parts.append('</tbody></table></div><div class="cohort-grid"><div><h3>成功音訊的新增時間</h3>'
        f'<p>第一個音訊 byte（TTFB）：{stats(r.get("ttfb_ms") for r in audio)}</p><p>完整請求：{stats(r.get("request_ms") for r in audio)}</p><p>檔案可用：{stats(r.get("ready_ms") for r in audio)}</p></div>'
        '<div><h3>量測範圍</h3><p>每段音訊使用新的 HTTPS 連線。TTFB 包含 DNS、TLS 與網路；不是伺服器純處理時間，也不是第一句可聽見的時間。</p><p>整體可用時間不包含上傳、LINE 傳送、手機通知或播放。本次沒有傳送訊息給使用者。</p></div></div></section>')
    parts.append('<section class="panel"><h2>回應品質與行為檢查</h2><p>沿用 Interaction tasks 的七項文字品質指標與證據規則，gpt-6-sol low 匿名單版本評分。排除 8 題安靜觀察；無文字時的風格項目為空值。這不是聲音自然度或口音評分，也不與歷史取樣混算勝率。</p><div class="cohort-grid"><div>' + quality(headline) + '</div><div>')
    for key,title in names.items():
        rows = [c[ARM] for c in cases if cohort(c)==key]
        parts.append(f'<h3>{title}</h3><p class="small">回應狀態：{counts(r["status"] for r in rows)}<br>路由：{counts(r.get("action","unknown") for r in rows)}<br>綜合能力檢查：{counts(r.get("tool_correctness",{}).get("status","not_evaluated") for r in rows)}'
            + (f'<br>群組檢查：{counts(r.get("group_correctness",{}).get("status","not_evaluated") for r in rows)}' if key.startswith('G') else '') + '</p>')
    parts.append('</div></div><details><summary>分情境的七項品質指標</summary><div class="cohort-grid">' + ''.join(f'<div><h3>{names[k]}</h3>{quality([c for c in cases if cohort(c)==k])}</div>' for k in ('E','S','G-reply')) + '</div></details><p class="small muted">能力檢查保留原始 passed / partial / failed 等狀態；模型互動 E 沒有量測原生副作用，partial 不直接等於工具呼叫錯誤。各題保留模型 HTTP、tokens、貼圖與工具回執。</p></section>')
    parts.append('<section class="panel"><h2>LINE 音訊相容性</h2><p>本 PR 增加可選的原生 audio payload，主回答 text 在前、接話 audio 在後。已用捕捉 HTTP 測試 reply 與 push；真實 LINE 驗證端點結果列於下載紀錄。這些驗證不會傳送訊息，也不代表已在手機上試播。</p><p class="small">LINE 要求 HTTPS 的 MP3 / M4A 與毫秒長度。正式接入還需要私人音訊存放、保存期限、持久化抽樣、取消／過期檢查與文字 fallback。本頁只公開合成案例。<a href="https://developers.line.biz/en/reference/messaging-api/nojs/#audio-message">LINE 官方 audio 規格</a></p></section>')
    parts.append('<section class="panel"><div class="controls"><label>搜尋案例<input id="search" type="search" placeholder="案例 ID、問題、回覆"></label><label>情境<select id="cohort"><option value="">全部情境</option>' + ''.join(f'<option value="{k}">{v}</option>' for k,v in names.items()) + '</select></label><label>音訊<select id="audio-filter"><option value="">全部</option><option value="ok">有音訊</option><option value="skipped">未產生音訊</option><option value="error">TTS 失敗</option></select></label><span id="count" role="status" aria-live="polite"></span></div></section>')
    for c in cases:
        r, identity = c[ARM], c['id']
        t = r.get('tts', {})
        reason = REASONS.get(t.get('gate',{}).get('reason'),t.get('error','沒有音訊紀錄'))
        search = ' '.join(str(v) for v in (identity,c.get('user_text',''),r.get('reply',''),r.get('follow_up',''))).lower()
        parts.append(f'<article class="case" id="{e(identity)}" data-cohort="{cohort(c)}" data-audio="{e(t.get("status","error"))}" data-search="{e(search)}"><h2>{e(identity)} · {e(c.get("scenario_title",c.get("category","")))}</h2><p class="question">{e(c.get("user_text",""))}</p>'
            f'<p class="small"><span class="badge">{e(r["status"])}</span> · 路由 {e(r.get("action","unknown"))} · LLM {seconds(r.get("llm_latency_ms"))} · 整體可用 {seconds(r.get("overall_ready_ms"))}</p><div class="steps">')
        for title,text in [('1 · LLM 主回答（文字）',r.get('reply','')),('2 · 接話原文',r.get('follow_up',''))]:
            parts.append(f'<div class="step"><h3>{title}</h3>' + (f'<div class="text">{e(text)}</div>' if text else '<p class="empty">（無）</p>') + '</div>')
        parts.append(f'<div class="step"><h3>3 · 接話語音 · Zack</h3><p class="small">{e(reason)}</p>')
        if t.get('status') == 'ok':
            parts.append(f'<audio controls preload="none" aria-label="{e(identity)} 接話語音"><source src="{e(t["audio_url"])}" type="audio/mpeg">瀏覽器不支援音訊播放。</audio><a class="small" href="{e(t["audio_url"])}" download>下載 MP3</a><p class="small">TTFB {seconds(t.get("ttfb_ms"))}<br>完整請求 {seconds(t.get("request_ms"))}<br>音訊長度 {seconds(t.get("duration_ms"))}</p>')
        elif t.get('status')=='error':
            parts.append(f'<p class="notice warning">TTS 失敗：{e(t.get("error","unknown"))}。接話文字保留。</p>')
        parts.append('</div></div><details><summary>文字品質、證據與模型紀錄</summary>' + quality([c])
            + f'<p>{e(c.get("quality_five_way",{}).get("variant_reasons",{}).get(ARM,"未評分"))}</p><pre>{e(json.dumps({"context":c.get("context"),"expectation":c.get("expectation"),"record":r},ensure_ascii=False,indent=2))}</pre></details></article>')
    parts.append('<p class="footer">本頁為獨立 benchmark；原始各版本结果保持不變。音訊來自 Eleven v4 Turbo，Zack，seed 42，stability 0.5，similarity 0.75；無 audio tags。</p></main><script>const cards=[...document.querySelectorAll(".case")];const search=document.querySelector("#search"),cohort=document.querySelector("#cohort"),audioFilter=document.querySelector("#audio-filter");function filter(){let shown=0;for(const card of cards){card.hidden=!(card.dataset.search.includes(search.value.trim().toLowerCase())&&(!cohort.value||cohort.value===card.dataset.cohort)&&(!audioFilter.value||audioFilter.value===card.dataset.audio));if(!card.hidden)shown++;}document.querySelector("#count").textContent=`${shown} / ${cards.length} 題`;}[search,cohort,audioFilter].forEach(el=>el.addEventListener("input",filter));filter();</script></body></html>')
    (PUBLIC / 'tts-followup.html').write_text(''.join(parts), encoding='utf-8')


if __name__ == '__main__':
    main()
