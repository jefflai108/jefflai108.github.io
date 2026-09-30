#!/usr/bin/env python3
"""Render the three sanitized, already measured media probes; no model calls."""
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public/line-v3"
TABS = (("index.html", "Interaction tasks"), ("delegation.html", "Delegation tasks"),
        ("taiwan.html", "台灣用語"), ("recovery.html", "困難任務與失敗恢復"),
        ("tts-followup.html", "TTS follow-up"), ("images-stickers.html", "Images & Stickers"),
        ("burst-turns.html", "Burst turns"))


def esc(value):
    return html.escape(str(value), quote=True)


def pretty(value):
    return esc(json.dumps(value, ensure_ascii=False, indent=2))


def queue_section(data):
    assert data['provider'] == data['line_transport'] == 'simulated'
    assert data['accepted_later_replies'] == data['attempted_later_replies'] == 6
    assert re.fullmatch(r'[0-9a-f]{40}', data['source_ref'])
    labels = {'text': '文字', 'sticker': '貼圖', 'image': '圖片'}
    rows, timing = [], []
    for account in data['accounts']:
        assert account['earlier_ordinary_provider_held'] and account['earlier_delegation_held']
        assert account['accepted_history_count'] == 10
        cells = []
        for item in account['later_deliveries']:
            assert item['accepted_while_both_earlier_waits_held']
            cells.append(f'<td>{labels[item["kind"]]}：已接受回覆</td>')
            timing.append(f'<li>{esc(account["channel"])} · {labels[item["kind"]]}：'
                          f'{item["simulated_line_acceptance_s"]:.3f} s</li>')
        rows.append(f'<tr><th scope="row">{esc(account["channel"])}</th>' + ''.join(cells) + '</tr>')
    return ('<section class="panel" id="queue-isolation"><p class="eyebrow">獨立驗證 · 模擬供應商與 LINE</p>'
        '<h2>Queue isolation：前一輪還在等，後一輪能回答嗎？</h2>'
        '<p>兩個帳號各先建立 10 筆已接受的合成歷史，再同時卡住一個較早的一般模型請求與一個委派工作。'
        '接著送進新的文字、貼圖與圖片，檢查它們能否先完成回覆。</p>'
        '<p><span class="badge success">6 / 6 已接受較晚回覆</span> 各帳號的三個回覆都獲接受時，該帳號較早的兩項等待仍未放行。</p>'
        '<div class="scroll" tabindex="0" role="region" aria-label="兩帳號的三種後續輸入結果"><table>'
        '<thead><tr><th>帳號</th><th>文字</th><th>貼圖</th><th>圖片</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table></div>'
        '<p>透過實際發布快照的載入器執行。這裡驗證的是模擬 LINE 已接受回覆，不只是模型開始處理；沒有跨帳號傳送或前景錯誤。</p>'
        '<p class="notice">此區的供應商與 LINE 都是模擬，和上方三個真實 Gemini 呼叫分開。它能驗證前後回合不互相卡住的路徑，不能當作模型速度或正式服務 SLA。</p>'
        '<details><summary>離線接受時間與限制</summary><ul>' + ''.join(timing) + '</ul>'
        '<p class="small muted">時間包含合成資料、SQL 追蹤及檔案稽核成本；不是手機端延遲，也不拿來和上方模型呼叫比較。</p></details>'
        '<p class="small">凍結程式碼 <code>' + esc(data['source_ref']) + '</code> · '
        '<a href="queue-isolation-results.public.json" download>下載去除本機資訊的驗證結果</a></p></section>')


def render(data, queue):
    assert data["schema_version"] == 1 and data["sample_count"] == len(data["cases"]) == 3
    assert data["synthetic_only"] and data["real_line_calls"] == 0
    assert re.fullmatch(r"[0-9a-f]{40}", data["source_ref"])
    nav = ''.join(f'<a href="{path}"' + (' aria-current="page"' if path == 'images-stickers.html' else '')
                  + f'>{esc(label)}</a>' for path, label in TABS)
    rows, cards = [], []
    for case in data["cases"]:
        result, source = case["result"], case["input"]
        assert result["action"] == "direct" and result["foreground_http_calls"] == 1
        assert result["accepted_tasks"] == result["delegation_executions"] == 0
        rows.append(f'<tr><th scope="row"><a href="#{esc(case["id"])}">{esc(case["title"])}</a></th>'
            f'<td>{result["whole_turn_s"]:.3f} s</td><td>{result["provider_http_s"]:.3f} s</td>'
            f'<td>{result["turn_to_request_s"]:.3f} s</td><td>direct · 1 · 0</td></tr>')
        if source["message_type"] == "image":
            image = source["image"]
            assert image["path"] == "fixtures/media-understanding-chart-document.jpg"
            assert re.fullmatch(r"[0-9a-f]{64}", image["sha256"])
            fixture = (f'<figure><a href="{image["path"]}"><img src="{image["path"]}" width="1200" height="880" '
                'alt="合成季度圖表：Alpha 為 10、15、20；Beta 為 8、8、6。備註要求檢視 Q3 成長，上線日期待定。"></a>'
                '<figcaption>實際送入模型的正規化 JPEG，沒有重畫、放大美化或替換字體。點圖可看原始尺寸。</figcaption></figure>'
                '<p>本輪只有一張圖，沒有另外輸入文字；比較數據與摘要備註的要求就在圖片底部。</p>'
                f'<details><summary>輸入檔案與 SHA-256</summary><p>{image["width"]} × {image["height"]} · '
                f'{image["bytes"]:,} bytes · image/jpeg</p><code class="hash">{image["sha256"]}</code></details>')
            observation = '<details><summary>模型保留的圖片觀察與 OCR</summary><pre>' \
                + pretty(result["image_observation"]) + '</pre></details>'
        else:
            known = case["kind"] == "known_sticker"
            fixture = ('<div class="metadata-card"><span class="badge">中介資料輸入 · 無貼圖像素</span>'
                f'<h4>{"有已審閱的目錄描述" if known else "沒有目錄描述或關鍵字"}</h4>'
                f'<pre>{pretty(source["sticker_metadata"])}</pre></div>'
                '<p>沒有下載或提供貼圖圖片、動畫、聲音；沒有另外輸入文字。畫面不放示意貼圖，避免誤認成模型看過的內容。</p>')
            observation = ''
        notes = ''.join(f'<li>{esc(note)}</li>' for note in case["semantic_review"]["notes"])
        cards.append(f'<article class="case" id="{esc(case["id"])}"><div class="case-heading"><div>'
            f'<p class="eyebrow">{esc(case["id"])} · {esc(case["channel"])} · 單次取樣</p>'
            f'<h2>{esc(case["title"])}</h2></div><span class="badge success">direct · 當輪回答</span></div>'
            '<div class="columns"><section><h3>模型收到的輸入</h3>' + fixture + '</section>'
            '<section><h3>實際模型回覆</h3><p class="small muted">文字逐字保留；由模擬 LINE 傳輸捕捉。</p>'
            f'<div class="reply">{esc(result["reply"])}</div>'
            f'<p class="metrics"><strong>{result["whole_turn_s"]:.3f} s</strong> 整輪 · '
            f'{result["provider_http_s"]:.3f} s 供應商 HTTP</p>'
            '<p class="small">1 次原生 Gemini HTTP 200 · 0 個背景任務 · 0 次委派執行</p>'
            + observation + '</section></div><div class="review"><h3>逐題閱讀紀錄</h3><ul>' + notes
            + '</ul><p class="small muted">開發代理依合成輸入逐項閱讀；不是獨立人工盲評或品質分數。</p></div></article>')
    return '''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Images &amp; Stickers · LINE v3</title><meta name="robots" content="noindex,follow">
<meta name="description" content="三個原生 Gemini 媒體理解實測：圖表文件、已知貼圖與未知貼圖；輸入、回覆、路由與逐題延遲完整列示。">
<link rel="canonical" href="https://jefflai108.github.io/line-v3/images-stickers.html">
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f3ee;color:#18362d;font:15px/1.7 system-ui,-apple-system,'PingFang TC',sans-serif}header,main,.navwrap{max-width:1280px;margin:auto;padding:20px 30px}header{padding-top:26px;padding-bottom:4px}a{color:#216b64}a:focus-visible,summary:focus-visible{outline:3px solid #258f9e;outline-offset:4px}.navwrap{display:flex;flex-wrap:wrap;gap:10px}.tabs{display:flex;flex-wrap:wrap;gap:4px;padding:5px;background:#e3e9e2;border-radius:12px}.tabs a{padding:8px 13px;text-decoration:none;color:#52695e;border-radius:8px;font-size:14px}.tabs a[aria-current=page]{background:#fff;color:#163f32;font-weight:700}h1{font-size:clamp(30px,4vw,46px);line-height:1.16;letter-spacing:-.03em;margin:12px 0 16px}h2{font-size:24px;line-height:1.3;margin:4px 0 16px}h3{font-size:17px;margin:0 0 12px}h4{font-size:16px;margin:12px 0}p{margin:10px 0}.eyebrow,.muted,figcaption{color:#65766e}.eyebrow{font-size:12px;letter-spacing:.03em}.lede{max-width:850px;font-size:18px}.small,figcaption{font-size:12px}.notice{background:#e8efeb;border:1px solid #cdded3;border-radius:12px;padding:14px 18px}.panel,.case{background:#fff;border:1px solid #d8e1da;border-radius:16px;padding:24px;margin:20px 0}.badges{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.badge{display:inline-block;border-radius:20px;padding:4px 11px;background:#e5ece7;font-size:12px}.success{background:#e5f2e9;color:#225c42}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:12px;text-align:left;border-bottom:1px solid #e3eae4;white-space:nowrap}thead{color:#52695e;background:#f8faf7}.route{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:18px 0}.step{border:1px solid #dce5de;border-radius:10px;padding:15px;background:#f8faf7}.step b{display:block;font-size:15px}.step span{font-size:13px;color:#65766e}.case-heading{display:flex;gap:16px;align-items:center;justify-content:space-between}.columns{display:grid;grid-template-columns:1fr 1fr;gap:28px}.columns>section{min-width:0}figure{margin:0}img{display:block;width:100%;height:auto;border:1px solid #d8e1da;border-radius:10px;background:#fff}figcaption{margin-top:8px}.reply{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f8f3;border:1px solid #dce5de;border-radius:12px;padding:18px}.metrics strong{font-size:23px}.review{border-top:1px solid #e3eae4;margin-top:22px;padding-top:20px}.review ul{padding-left:23px}.review li+li{margin-top:8px}.metadata-card{background:#f8faf7;border:1px solid #dce5de;border-radius:12px;padding:18px}pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0;max-height:460px;overflow:auto}code{font-size:12px;overflow-wrap:anywhere}.hash{display:block}details{margin:14px 0}summary{cursor:pointer;color:#216b64}footer{padding:18px 0;font-size:12px;color:#65766e}.skip{position:absolute;left:-10000px}.skip:focus{left:15px;top:8px;background:#fff;padding:10px;z-index:2}@media(max-width:760px){header,main,.navwrap{padding:16px}.panel,.case{padding:18px}.columns,.route{grid-template-columns:1fr}.tabs a{font-size:12px;padding:7px 9px}.case-heading{align-items:flex-start;flex-direction:column;gap:0}.case-heading>.badge{margin-bottom:18px}.lede{font-size:16px}}
</style></head><body><a class="skip" href="#main">跳至測試結果</a><div class="navwrap"><nav class="tabs" aria-label="比較分頁">''' + nav + '''</nav></div>
<header><p class="eyebrow">HeyMachi / LINE v3 · 2026-09-30 · 原生 Gemini 實測</p><h1>Images &amp; Stickers</h1>
<p class="lede">看圖、讀字、理解貼圖，都在互動這一輪回答。這三個案例實際走了哪條路、花了多久、回答了什麼，都在這裡。</p>
<div class="badges"><span class="badge success">3 / 3 直接回覆</span><span class="badge">3 次原生模型 HTTP</span><span class="badge">0 個背景任務</span></div>
<p class="notice">只使用合成輸入與臨時資料庫；模型呼叫是真的，LINE 傳輸是本機模擬，沒有送給真實帳號。每題只有一次取樣，不計算 P95，也不能據此保證所有圖片都成功或手機幾秒收到。</p>
<p class="small muted">與其他分頁的架構比較分開記錄；本頁沒有硬改模型路由，也沒有另造「強制委派」對照。</p></header>
<main id="main"><section class="panel"><h2>這三輪的時間</h2><div class="scroll" tabindex="0" role="region" aria-label="逐題路由與延遲，可橫向捲動"><table><thead><tr><th>輸入</th><th>整輪處理</th><th>供應商 HTTP</th><th>送出請求前</th><th>路由 · HTTP 次數 · 背景任務</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<p class="small muted">整輪從簽章事件送入宿主，計到處理返回，包含前置處理、驗證與模擬傳送；不包含手機收件。HTTP 是供應商 request 呼叫至返回的計時，不是純模型運算時間。三題內容不同，不用它們計算速度排名。</p></section>
<section class="panel"><h2>理解與操作，分清楚再路由</h2><div class="route"><div class="step"><b>1 · 接收媒體</b><span>圖片以實際像素送入；貼圖用本輪提供的中介資料。</span></div><div class="step"><b>2 · 互動模型理解</b><span>在同一次原生 Gemini 呼叫讀圖、解讀或自然接話。</span></div><div class="step"><b>3 · 當輪直接回答</b><span>本次三題皆選 direct，沒有建立或執行背景任務。</span></div></div>
<p>複雜圖表、文件截圖、OCR、梗圖含義，以及已知或未知貼圖的理解，都屬於互動工作。圖片生成、外部查證等另行要求的工具操作仍可以委派；讀不到輸入時應如實說明，不把缺少圖片當作盲目搜尋的理由。</p>
<p class="small muted">這段說明是路由邊界，不是額外的測試結果。本次只量測以下三個案例。</p></section>''' + ''.join(cards) + queue_section(queue) + '''
<section class="panel"><h2>量測範圍與可下載資料</h2><p>依序執行三題，每題一次，沒有重試或擇優。公開資料保留人工撰寫的輸入、原始回覆、路由、逐題時間和閱讀紀錄；不包含私人聊天、系統提示、憑證或本機路徑。</p>
<p>本次回執記錄原生 Gemini API 呼叫，但未保存精確模型版本；不從其他分頁的設定推定版本。這是路由與答案的冒煙測試，不是獨立品質評鑑、統計延遲基準或正式上線狀態證明。</p>
<p><a href="media-understanding-results.public.json" download>下載公開結果 JSON</a> · <a href="fixtures/media-understanding-chart-document.jpg" download>下載實際圖片輸入</a></p>
<p class="small">凍結程式碼 <code>''' + esc(data['source_ref']) + '''</code></p></section>
<footer>保留既有 Interaction、Delegation、台灣用語、Recovery、TTS 與 Burst 報告各自的測量；本頁不重算或混入它們的分數。</footer></main></body></html>
'''


def install():
    data = json.loads((PUBLIC / "media-understanding-results.public.json").read_text())
    fixture = data["cases"][0]["input"]["image"]
    raw = (PUBLIC / fixture["path"]).read_bytes()
    assert len(raw) == fixture["bytes"] and hashlib.sha256(raw).hexdigest() == fixture["sha256"]
    queue = json.loads((PUBLIC / "queue-isolation-results.public.json").read_text())
    (PUBLIC / "images-stickers.html").write_text(render(data, queue))
    link = '<a href="images-stickers.html">Images &amp; Stickers</a>'
    for name, _ in TABS:
        if name == 'images-stickers.html':
            continue
        path = PUBLIC / name
        page = path.read_text()
        match = re.search(r'<nav class="tabs"[^>]*>.*?</nav>', page, re.S)
        assert match is not None, name
        if 'images-stickers.html' in match.group():
            continue
        nav = match.group().replace('<a href="burst-turns.html"', link + '<a href="burst-turns.html"')
        assert nav != match.group(), name
        path.write_text(page[:match.start()] + nav + page[match.end():])


if __name__ == '__main__':
    install()
