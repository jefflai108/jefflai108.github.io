// Describe observed captures only; a waiting message cannot supply final latency.
export const latencyNames = {
  frontend: '前景模型呼叫耗時（合計）',
  bridge: '承接訊息',
  executor_start: '背景執行起點（序列測試）',
  final: '委派任務 · 最終結果',
  direct_answer: '直接互動 · 最終文字',
  terminal_notice: '未等待新結果的狀態通知',
};

const arms = ['baseline', 'natural'];
const finite = n => typeof n === 'number' && Number.isFinite(n);

function stats(values) {
  const sorted = values.filter(finite).sort((a, b) => a - b);
  const n = sorted.length;
  return n ? {n, median: (sorted[Math.floor((n - 1) / 2)] + sorted[Math.ceil((n - 1) / 2)]) / 2,
    p95: sorted[Math.ceil(.95 * n) - 1]} : {n: 0, median: null, p95: null};
}

export function latency(turn, kind) {
  if (!turn) return null;
  if (kind === 'frontend' || kind === 'executor_start') {
    const value = turn.metrics?.[kind === 'frontend' ? 'frontend_latency_ms' : 'executor_start_ms'];
    return finite(value) && value >= 0 ? value : null;
  }
  const values = turn.messages.filter(m => m.role === kind).map(m => m.elapsed_ms)
    .filter(n => finite(n) && n >= 0);
  // Match the harness: first acknowledged bridge/notice; last completed answer.
  return (kind === 'bridge' || kind === 'terminal_notice' ? values[0] : values.at(-1)) ?? null;
}

export function summarize(data, paired) {
  const rows = [...paired.values()];
  const observed = Object.fromEntries(arms.map(arm => [arm,
    data.receipts.filter(r => r.arm === arm).flatMap(r => r.turns)]));
  const timings = Object.fromEntries(arms.map(arm => [arm,
    Object.fromEntries(Object.keys(latencyNames).map(kind => [kind,
      {...stats(observed[arm].map(turn => latency(turn, kind))), planned_turns: rows.length}]))]));
  const deltas = Object.fromEntries(['bridge', 'final'].map(kind => {
    const pairs = rows.map(row => arms.map(arm => latency(row[arm], kind)));
    const values = pairs.filter(pair => pair.every(finite)).map(([baseline, natural]) => natural - baseline);
    return [kind, {...stats(values), observed_either: pairs.filter(pair => pair.some(finite)).length,
      planned_pairs: rows.length}];
  }));
  const diversity = Object.fromEntries(arms.map(arm => {
    const delivered = observed[arm].flatMap(turn => turn.messages)
      .filter(m => m.role === 'bridge' && m.texts.length > 0);
    // Preserve every character and message boundary. Do not normalize candidates.
    return [arm, {n: delivered.length, distinct_exact: new Set(delivered.map(m => JSON.stringify(m.texts))).size}];
  }));
  return {planned_pairs: rows.length, latency: timings, paired_delta_ms: deltas,
    bridge_diversity: diversity};
}
