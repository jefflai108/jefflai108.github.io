#!/usr/bin/env node
/**
 * Refresh the GitHub contribution snapshot used by the About section.
 *
 * Runs as a `prebuild` step. It needs a token with no special scopes —
 * GITHUB_TOKEN in CI, or a local `gh auth token`. If the fetch fails for any
 * reason the existing snapshot is left alone, so a build never breaks over it.
 *
 *   node scripts/fetch-contributions.mjs
 */
import { writeFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const USER = 'jefflai108';
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'contributions.json');

function token() {
  if (process.env.GITHUB_TOKEN) return process.env.GITHUB_TOKEN;
  try {
    return execSync('gh auth token', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
  } catch {
    return null;
  }
}

const QUERY = `
  query($login: String!) {
    user(login: $login) {
      contributionsCollection {
        contributionCalendar {
          totalContributions
          weeks {
            contributionDays { date contributionCount }
          }
        }
      }
    }
  }
`;

function bail(why) {
  if (existsSync(OUT)) {
    console.log(`[contributions] ${why} — keeping existing snapshot`);
    process.exit(0);
  }
  console.log(`[contributions] ${why} — writing empty snapshot`);
  writeFileSync(OUT, JSON.stringify({ total: 0, weeks: [], fetchedAt: null }, null, 2));
  process.exit(0);
}

const auth = token();
if (!auth) bail('no GitHub token available');

try {
  const res = await fetch('https://api.github.com/graphql', {
    method: 'POST',
    headers: {
      Authorization: `bearer ${auth}`,
      'Content-Type': 'application/json',
      'User-Agent': 'jefflai108.github.io-build',
    },
    body: JSON.stringify({ query: QUERY, variables: { login: USER } }),
  });

  if (!res.ok) bail(`GitHub API returned ${res.status}`);

  const json = await res.json();
  const cal = json?.data?.user?.contributionsCollection?.contributionCalendar;
  if (!cal) bail(`unexpected API response: ${JSON.stringify(json).slice(0, 200)}`);

  const weeks = cal.weeks.map((w) =>
    w.contributionDays.map((d) => ({ date: d.date, count: d.contributionCount }))
  );

  writeFileSync(
    OUT,
    JSON.stringify(
      { total: cal.totalContributions, weeks, fetchedAt: new Date().toISOString() },
      null,
      2
    )
  );
  console.log(`[contributions] ${cal.totalContributions} contributions across ${weeks.length} weeks`);
} catch (err) {
  bail(`fetch failed: ${err.message}`);
}
