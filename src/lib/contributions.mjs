/**
 * Give each calendar month its own scale, using only the displayed days.
 * GitHub's stored annual level is deliberately replaced; dates and counts stay
 * untouched. YYYY-MM keeps partial months at opposite ends of the year apart.
 *
 * @param {{ date: string, count: number, level?: number }[][]} weeks
 * @returns {{ date: string, count: number, level: number }[][]}
 */
export function normalizeContributionsByMonth(weeks) {
  const maxima = new Map();
  for (const week of weeks) {
    for (const day of week) {
      const month = day.date.slice(0, 7);
      maxima.set(month, Math.max(maxima.get(month) ?? 0, day.count));
    }
  }

  return weeks.map((week) => week.map((day) => ({
    ...day,
    level: day.count > 0
      ? Math.ceil((day.count / maxima.get(day.date.slice(0, 7))) * 4)
      : 0,
  })));
}
