import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';

const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const artifact=name=>fs.readFileSync(new URL('../../public/line-v3/'+name,import.meta.url));

test('final-v3 archive retains exact reviewed JSON and study hashes',()=>{
  const bytes=artifact('natural-bridges-final-v3-results.public.json');
  assert.equal(sha(bytes),'e278ed448529fe8858bdc2d484742f9cf43fd85b6a4555ce2f129e1ddea77a25');
  const data=JSON.parse(bytes);
  assert.equal(data.source_ref,'a3009d493cc9708c0666554c27cef38b03f15b89');
  assert.equal(data.quality.results_sha256,'c5befbd5565138ff2c894be64d9a78f97333524cc3e4a3aed69b425ce588b939');
  assert.equal(data.receipts.length,60);
  assert.equal(data.receipts.reduce((n,r)=>n+r.turns.length,0),84);
  assert.equal(data.statistics.planned_pairs,42);
});

test('final-v3 page changes only archive identification and links, preserving measured copy',()=>{
  const bytes=artifact('natural-bridges-final-v3.html');
  const html=bytes.toString('utf8');
  assert.match(html,/<meta name="robots" content="noindex,nofollow">/);
  assert.match(html,/href="natural-bridges-final-v3-results.public.json"/);
  assert.match(html,/href="natural-bridges.html">查看目前發布的比較/);
  const restored=html
    .replace('https://jefflai108.github.io/line-v3/natural-bridges-final-v3.html','https://jefflai108.github.io/line-v3/natural-bridges.html')
    .replace('href="natural-bridges-final-v3-results.public.json"','href="natural-bridges-results.public.json"')
    .replace('<h1>Natural bridges · final-v3</h1>','<h1>Natural bridges</h1>')
    .replace('<p class="note">這是保留原始量測的 final-v3 歷史題組。<a href="natural-bridges.html">查看目前發布的比較</a>。</p></header>','</header>');
  assert.equal(sha(restored),'415d879068b7006a1f4645836b1aa5d96a35c5ab4bf9af38a2b2e9dbdf77a5fe');
});
