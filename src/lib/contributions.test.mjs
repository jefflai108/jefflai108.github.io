import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeContributionsByMonth } from './contributions.mjs';

const day = (date, count, level = 1) => ({ date, count, level });
const levels = (weeks) => normalizeContributionsByMonth(weeks).flat().map((d) => d.level);

test('empty calendars and inactive months stay empty', () => {
  assert.deepEqual(normalizeContributionsByMonth([]), []);
  assert.deepEqual(normalizeContributionsByMonth([[]]), [[]]);
  assert.deepEqual(levels([[day('2026-08-01', 0), day('2026-09-01', 0)]]), [0, 0]);
});

test('positive counts occupy four equal ranges of their monthly maximum', () => {
  const counts = [0, 1, 25, 26, 50, 51, 75, 76, 100];
  assert.deepEqual(
    levels([counts.map((count, index) => day(`2026-08-${String(index + 1).padStart(2, '0')}`, count))]),
    [0, 1, 1, 2, 2, 3, 3, 4, 4],
  );
});

test('a busy month cannot wash out a quieter month', () => {
  assert.deepEqual(levels([
    [day('2026-07-29', 100), day('2026-07-30', 50), day('2026-08-01', 1)],
    [day('2026-08-02', 2), day('2026-08-03', 4)],
  ]), [4, 2, 1, 2, 4]);
});

test('all weeks in the same month share a scale', () => {
  assert.deepEqual(levels([
    [day('2026-08-01', 2)],
    [day('2026-08-08', 4)],
    [day('2026-08-31', 8)],
  ]), [1, 2, 4]);
});

test('partial months in different years are normalized separately', () => {
  assert.deepEqual(levels([
    [day('2025-09-29', 100), day('2025-09-30', 50)],
    [day('2026-09-01', 1), day('2026-09-02', 2)],
  ]), [4, 2, 2, 4]);
});

test('one active day and tied monthly maxima use the darkest shade', () => {
  assert.deepEqual(levels([
    [day('2026-07-31', 1)],
    [day('2026-08-01', 3), day('2026-08-02', 3), day('2026-08-03', 0)],
  ]), [4, 4, 4, 0]);
});

test('annual levels are ignored without mutating counts, dates, or the snapshot', () => {
  const weeks = [[day('2026-08-01', 0, 4), day('2026-08-02', 2, 4), day('2026-08-03', 4, 1)]];
  const before = structuredClone(weeks);
  const normalized = normalizeContributionsByMonth(weeks);
  assert.deepEqual(normalized.flat().map((d) => d.level), [0, 2, 4]);
  assert.deepEqual(normalized.flat().map(({ date, count }) => ({ date, count })),
    weeks.flat().map(({ date, count }) => ({ date, count })));
  assert.deepEqual(weeks, before);
});
