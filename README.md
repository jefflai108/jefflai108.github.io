# jefflai108.github.io

Personal homepage — [jefflai108.github.io](https://jefflai108.github.io).

Astro 5, no UI framework, no CSS framework. Static output deployed to GitHub Pages by
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) on every push to `master`.

## Deploying

The Pages source must be **GitHub Actions**, not a branch. This repo served from `master:/`
until the 2026 rebuild, and the switch is a one-time manual step:

```bash
gh api --method PUT repos/jefflai108/jefflai108.github.io/pages -f build_type=workflow
```

or Settings → Pages → Source → "GitHub Actions". Verify with:

```bash
gh api repos/jefflai108/jefflai108.github.io/pages --jq .build_type
```

Do this **before** the first push. The workflow's `actions/configure-pages` step will not do
it for you — its `enablement` option only fires when no Pages site exists at all, and this
repo already has one, so it is a no-op here. Until the source is switched, `deploy-pages`
fails and Pages keeps trying to serve the repo root, which no longer has an `index.html`.

## Running it

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # -> dist/
npm run preview  # serve dist/
```

## Where the content lives

Everything editable is a plain TypeScript file under `src/data/` — no CMS, no frontmatter
juggling. Edit, commit, push; the site rebuilds itself.

| File | What it holds |
| --- | --- |
| `src/data/site.ts` | Name, role, email, social links, Scholar stats, and every outbound org/person URL |
| `src/data/news.ts` | The "Recent updates" feed — newest first, one line of HTML each |
| `src/data/publications.ts` | Full publication list. `selected: true` puts a paper on the homepage |
| `src/data/work.ts` | The "Recent work" showcase — new projects go here |

Three data files are **kept but no longer rendered**, after the page was trimmed to
About → Recent work → Publications → Writing. They are intact if a section comes back:

| File | Was |
| --- | --- |
| `src/data/career.ts` | Experience/education timelines, talks, service |
| `src/data/oss.ts` | Open-source projects and star counts |
| `src/data/writing.ts` | The Medium archive on `/blog/` |

`publications.ts` still holds all 23 papers; `SELECTED` at the bottom of that file picks the
two shown on the homepage.

Three things are deliberately parameterised in `site.ts`:

- **`scholarStats`** is a manual snapshot with an `asOf` date. Google Scholar has no public API,
  so refresh it by hand every so often and bump `asOf`.
- **`orgs`** holds every outbound URL in one place. `waveforms.ai` is absent on purpose — the
  domain stopped resolving after the Meta acquisition, so the acquisition coverage is linked instead.
- **`cv`** points at `public/data/cv.pdf`, which is **generated, not copied** — see below.

## Regenerating the CV

The private résumé carries a phone number in its contact block, and everything under `public/`
is served to the open internet. [`scripts/build-cv.py`](scripts/build-cv.py) produces the public
copy:

```bash
python3 scripts/build-cv.py ~/path/to/resume.pdf public/data/cv.pdf
```

It applies a real redaction — `apply_redactions()` rewrites the content stream, so the digits are
gone from the text layer, not merely covered — then rebuilds the contact line so the removal
doesn't leave a hole, re-attaching the email/LinkedIn/Scholar hyperlinks. It exits non-zero rather
than write a file if a phone-shaped string survives, or if the rebuilt line stops extracting as
selectable text (a CV that renders but doesn't extract is invisible to résumé parsers).

Never drop a résumé PDF into `public/` by hand — route it through this script.

**It needs PyMuPDF, but you don't have to arrange that.** If the `python3` you invoke can't
import it, the script finds an interpreter that can and re-execs into it, falling back to
`uv run --with pymupdf` if nothing on the machine has it. Two traps it routes around:

- PyMuPDF dropped Python 3.7, so on a conda base env pip resolves to an old sdist, tries to build
  it, needs `swig`, and dies inside conda's vendored TOML parser. Unwinnable; not worth trying.
- The PyPI package literally named `fitz` is unrelated to PyMuPDF and shadows it, failing with a
  baffling `No module named 'frontend'`.

## Writing a blog post

Drop a Markdown file in `src/content/blog/`. The filename becomes the URL
(`my-post.md` → `/blog/my-post/`). See [`example-post.md`](src/content/blog/example-post.md)
for the frontmatter schema — it is a draft, so it stays invisible until you flip `draft: false`.

To list a post that lives elsewhere, add an `external:` URL to the frontmatter and no local
page is built.

## Things that keep themselves current

Two numbers on the page would go stale if anyone had to remember to update
them, so nobody does:

| What | Source | Refreshed |
| --- | --- | --- |
| GitHub contribution graph | GitHub GraphQL API | every build |
| Citations · h-index · i10-index | Google Scholar profile page | every build |

Both run in `prebuild` (`npm run refresh`), and **the deploy workflow is on a
weekly cron** (Mondays 06:00 UTC) so the site rebuilds itself even in a week
with no commits. Nothing to run by hand.

Both fetchers fail safe: if the source is unreachable they keep the committed
snapshot, print a warning, and exit 0 — a bad network never breaks a deploy.
The Scholar figures display the date they were actually fetched, so a stale
snapshot reads as stale instead of passing off old numbers as current.

One caveat worth knowing: Scholar has no API, so `fetch-scholar.mjs` parses the
profile page, and Scholar sometimes serves datacenter IPs a CAPTCHA instead.
The script detects that and keeps the old snapshot rather than parsing garbage.
If the Actions log shows that warning repeatedly, run `npm run refresh` locally
(residential IPs are not blocked) and commit the updated `src/data/scholar.json`.

## The GitHub contribution graph

`scripts/fetch-contributions.mjs` pulls the last year of contributions from the GitHub GraphQL
API into `src/data/contributions.json`, and runs automatically as a `prebuild` step. Locally it
uses your `gh auth token`; in CI it uses the workflow's `GITHUB_TOKEN`. If the fetch fails for
any reason it keeps the committed snapshot rather than breaking the build, and prints a loud
warning to the build log.

CI's `GITHUB_TOKEN` is a repository-scoped token, and `contributionsCollection` is a *user*-level
GraphQL field — so the CI refresh may not succeed. If the build log shows the fallback warning,
the reliable path is to refresh locally and commit the snapshot.

Refresh it by hand with:

```bash
npm run contributions
```

The deploy workflow also accepts a manual `workflow_dispatch` run, which is the easiest way to
refresh the graph without pushing a commit.

## Theming

All colour, type, and spacing tokens are at the top of `src/styles/global.css`, with a
`:root.dark` block mirroring every one of them. The theme is applied by an inline script in
`Base.astro` before first paint so there is no light/dark flash, and it respects
`prefers-color-scheme` until the visitor picks a side.

## Archive

The pre-2026 site (a redirect to the now-defunct MIT page, plus its predecessor) is preserved
under [`archive/`](archive/).
