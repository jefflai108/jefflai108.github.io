import test from 'node:test';
import assert from 'node:assert/strict';
import { addDebugNavigation } from './debug-navigation.mjs';

const snapshot = `<html><body><nav class="page-tabs" aria-label="網站分頁">
        <button id="updates-tab" class="active" aria-current="page">近期更新</button>
        <button id="retention-tab">使用者留存</button>
        <button id="deep-tab">改動地圖</button>
        <a id="benchmark-tab" href="https://jefflai108.github.io/line-v3/">Benchmark</a>
      </nav><main>Snapshot content</main></body></html>`;

test('snapshot rebuilds place Debug directly before Benchmark and preserve existing controls', () => {
  const output = addDebugNavigation(snapshot);
  const ids = [...output.matchAll(/id="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(ids, ['updates-tab', 'retention-tab', 'deep-tab', 'debug-tab', 'benchmark-tab']);
  assert.ok(output.includes('href="https://jefflai108.github.io/debug/">Debug</a>'));
  assert.equal(output.replace(/<a id="debug-tab"[^>]*>Debug<\/a>\s*/, ''), snapshot);
});

test('reapplying navigation to a refreshed snapshot does not duplicate or change the link', () => {
  const once = addDebugNavigation(snapshot);
  assert.equal(addDebugNavigation(once), once);
});

test('an existing Debug tab is moved before Benchmark with the canonical URL', () => {
  const stale = snapshot.replace('</nav>', '<a id="debug-tab" href="/leo-debug/">Old debug</a></nav>');
  const output = addDebugNavigation(stale);
  assert.ok(output.indexOf('id="debug-tab"') < output.indexOf('id="benchmark-tab"'));
  assert.equal([...output.matchAll(/id="debug-tab"/g)].length, 1);
  assert.ok(!output.includes('/leo-debug/'));
});

test('missing or ambiguous navigation stops deployment instead of publishing misplaced tabs', () => {
  assert.throws(() => addDebugNavigation('<nav>Other links</nav>'), /page-tabs/);
  assert.throws(() => addDebugNavigation(snapshot.replace('benchmark-tab', 'other-tab')), /Benchmark/);
  assert.throws(() => addDebugNavigation(snapshot + snapshot), /page-tabs/);
});

test('a native Debug panel keeps its button and position on every snapshot refresh', () => {
  const native = snapshot.replace('</nav>', '<button id="debug-tab">Debug</button></nav>')
    + '<section id="debug-panel"><iframe id="debug-frame"></iframe></section>';
  const output = addDebugNavigation(native);
  assert.ok(output.includes('<button id="debug-tab">Debug</button>'));
  assert.ok(output.indexOf('id="debug-tab"') < output.indexOf('id="benchmark-tab"'));
  assert.equal([...output.matchAll(/id="debug-tab"/g)].length, 1);
  assert.equal(addDebugNavigation(output), output);
});
