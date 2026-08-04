#!/usr/bin/env node
/**
 * Refresh the Google Scholar figures shown next to Selected publications.
 *
 * Scholar has no API, so this parses the public profile page. That is fragile
 * by nature, so the script is built to fail safely: it only overwrites the
 * committed snapshot when it gets numbers that pass a sanity check, and it
 * never exits non-zero — a blocked scrape must not break a deploy.
 *
 * Run by `prebuild`, so every build picks up current figures.
 *
 *   node scripts/fetch-scholar.mjs
 */
import { writeFileSync, existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const USER = 'mV4mRm0AAAAJ';
const URL_ = `https://scholar.google.com/citations?user=${USER}&hl=en`;
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'scholar.json');

const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

function keepExisting(why) {
  if (existsSync(OUT)) {
    const cur = JSON.parse(readFileSync(OUT, 'utf8'));
    console.warn(`[scholar] WARNING: ${why}`);
    console.warn(`[scholar] Keeping the committed snapshot (fetched ${cur.fetchedAt}).`);
    console.warn('[scholar] Refresh locally with: npm run refresh');
  } else {
    console.warn(`[scholar] WARNING: ${why} — and no snapshot exists; stats will be hidden.`);
    writeFileSync(OUT, JSON.stringify({ citations: null, hIndex: null, i10: null, fetchedAt: null }, null, 2));
  }
  process.exit(0); // never fail the build over this
}

let html;
try {
  const res = await fetch(URL_, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9' },
    signal: AbortSignal.timeout(30_000),
  });
  if (!res.ok) keepExisting(`Scholar returned HTTP ${res.status}`);
  html = await res.text();
} catch (err) {
  keepExisting(`fetch failed: ${err.message}`);
}

// Scholar serves a consent/CAPTCHA interstitial to datacenter IPs rather than
// an error, so detect that explicitly instead of parsing garbage.
if (/captcha|unusual traffic|not a robot/i.test(html)) {
  keepExisting('Scholar served a CAPTCHA / bot interstitial');
}

// The stats table is: [citations all, citations since, h all, h since, i10 all, i10 since]
const nums = [...html.matchAll(/<td class="gsc_rsb_std">(\d+)<\/td>/g)].map((m) => Number(m[1]));
if (nums.length < 5) keepExisting(`could not find the stats table (got ${nums.length} cells)`);

const [citations, , hIndex, , i10] = nums;

// Guard against a parse that "succeeds" on the wrong page: these only ever grow,
// and a sudden collapse means we scraped something else.
const prev = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : null;
const sane =
  Number.isFinite(citations) && citations > 0 &&
  Number.isFinite(hIndex) && hIndex > 0 &&
  Number.isFinite(i10) && i10 >= 0 &&
  (!prev?.citations || citations >= prev.citations * 0.9);
if (!sane) keepExisting(`implausible numbers: ${JSON.stringify({ citations, hIndex, i10 })}`);

writeFileSync(
  OUT,
  JSON.stringify(
    { citations, hIndex, i10, fetchedAt: new Date().toISOString().slice(0, 10) },
    null,
    2
  ) + '\n'
);
console.log(`[scholar] ${citations.toLocaleString('en-US')} citations · h-index ${hIndex} · i10 ${i10}`);
