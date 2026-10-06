import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// Apply current-only navigation to the build, preserving frozen authored reports.
const directory = path.resolve(process.argv[2] || 'dist/line-v3');
const tabs = [
  ['index.html', 'Interaction tasks'],
  ['delegation.html', 'Delegation tasks'],
  ['taiwan.html', '台灣用語'],
  ['recovery.html', '困難任務與失敗恢復'],
  ['tts-followup.html', 'TTS follow-up'],
  ['images-stickers.html', 'Images &amp; Stickers'],
  ['burst-turns.html', 'Burst turns'],
  ['natural-bridges.html', 'Natural bridges'],
  ['line-stickers.html', 'LINE Stickers'],
];
const version = name => crypto.createHash('sha256').update(fs.readFileSync(path.join(directory,name))).digest('hex').slice(0,12);
const assets = `<link rel="stylesheet" href="navigation.css?v=${version('navigation.css')}"><link rel="stylesheet" href="report-layout.css?v=${version('report-layout.css')}"><script src="navigation.js?v=${version('navigation.js')}" defer></script>`;
const navigation = /<nav\b[^>]*class="tabs"[^>]*>[\s\S]*?<\/nav>/g;
const history = /<nav\b(?=[^>]*class="history")(?=[^>]*aria-label="歷史快照")[^>]*>[\s\S]*?<\/nav>/g;

for (const [name] of tabs) {
  const file = path.join(directory,name);
  let html = fs.readFileSync(file,'utf8');
  if ((html.match(navigation) || []).length !== 1 || !html.includes('</head>')) {
    throw new Error(`Expected one top-level navigation in ${name}.`);
  }
  // Active URLs are the latest published study in each category. Keep archives
  // available to existing references, but omit their selectors from the live UI.
  // Baseline comparisons, provenance, and current-study evidence remain intact.
  html = html.replace(navigation,'').replace(history,'')
    .replace(/<div class="navwrap">\s*<\/div>/g,'')
    .replace(/歷史版本：<a href="tts-followup-tagged-v\d+-\d{8}\.html">[\s\S]*?<\/a>\s*·\s*<a href="tts-followup-plain-\d{8}\.html">[\s\S]*?<\/a>。/g,'')
    .replace(/<a href="natural-bridges-final-v\d+\.html">查看 final-v\d+ 歷史題組<\/a>；/g,'');
  const links = tabs.map(([href,label]) => `<a href="${href}"${href === name ? ' aria-current="page"' : ''}>${label}</a>`).join('');
  const bar = `<div class="benchmark-nav"><nav class="tabs benchmark-tabs" aria-label="比較分頁">${links}</nav></div>`;
  html = html.replace(/<body\b[^>]*>/, tag => {
    if (/\bclass=["']/.test(tag)) {
      return tag.replace(/class=(["'])(.*?)\1/, (_, quote, classes) => `class=${quote}${classes} benchmark-page${quote}`);
    }
    return tag.replace('<body','<body class="benchmark-page"');
  });
  const body = /<body\b[^>]*>\s*(?:<a\b[^>]*class="skip"[^>]*>[\s\S]*?<\/a>\s*)?/;
  if (!body.test(html)) throw new Error(`Missing document body in ${name}.`);
  html = html.replace(body, match => match + bar).replace('</head>',assets + '</head>');
  fs.writeFileSync(file,html);
}
console.log(`Unified navigation for ${tabs.length} active LINE benchmark pages.`);
