# jefflai108.github.io

Personal homepage — [jefflai108.github.io](https://jefflai108.github.io).

Astro 7, no UI framework, no CSS framework. Static output deployed to GitHub Pages by
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

Use Node 22.12 or newer. `.nvmrc` selects Node 22, matching the Pages workflow.

```bash
nvm use         # when using nvm
npm install
npm run dev      # http://localhost:4321
npm run build    # -> dist/
npm run preview  # serve dist/
```

## Image comparison gallery

The public comparison is at `/gpt-vs-gemini/`. Its HTML and checksum manifest are
tracked in Git; the 40 generated JPEGs (20 originals at 1024×1024 and 20 previews
at 512×512) are stored in the `image-comparison-2026-09-11` GitHub Release asset
`line-image-comparison-images.zip`. Do not commit generated images or embed their
base64 bytes in HTML.

The Pages workflow downloads that exact asset after building, verifies the ZIP
and every file against `scripts/image-comparison-assets.json`, then adds the images
to `dist/gpt-vs-gemini/images/`. A missing or changed asset fails deployment, so a
gallery with broken image links cannot replace the current site. Publish the
matching release asset before merging changes to its manifest.

For a local preview with images:

```bash
gallery_assets_dir="$(mktemp -d)"
gh release download image-comparison-2026-09-11 \
  --repo jefflai108/jefflai108.github.io \
  --pattern line-image-comparison-images.zip --dir "$gallery_assets_dir"
python3 scripts/install-image-comparison-assets.py \
  "$gallery_assets_dir/line-image-comparison-images.zip" public
npm run dev
```

The installed `public/gpt-vs-gemini/images/` directory is ignored by Git. To preview
a production build, run `npm run build`, pass `dist` instead of `public` to the
installer, then run `npm run preview`. The installer uses only Python's standard
library; its offline archive validation tests run with:

```bash
python3 -m unittest discover -s scripts -p 'test_image_comparison_assets.py'
```

## Mandarin and English TTS voice comparison

The unlisted `/tts/` page compares seven voices across twenty mixed Taiwanese
Mandarin and ten English passages (1–3 sentences each). The four models are Eleven
v3, v3 Conversational, Eleven v4, and Eleven v4 Turbo. Mandarin has ten versions:
plain text for all four models, plus the same emotion and vocal-reaction inputs
for v3, v4, and v4 Turbo. English has four versions, all prefixed with
`[strong American accent]`. Navigation and sitemap omit the page, and its robots
meta tag is `noindex, nofollow`. The static page is unlisted, not authenticated.

The original `src/data/tts-corpus*.json` and `tts-benchmark*.json` datasets are
preserved. New v4 corpora and results use `tts-corpus-v4` / `tts-benchmark-v4`,
with suffixes `-zh-emotion`, `-zh-vocal`, and `-en-us` for the other runs.
The v4 corpora copy the original voices, passages, exact tag prefixes, selection
reasons, request seeds, and output format. Their stability is 0.5 and similarity
is 0.75; Speed and Style settings are omitted because v4 does not support them.
Original v3 requests used stability 0.5 and speed 1.0, without explicitly setting
similarity. v3 was measured on September 25 and v4 on September 28, 2026;
the page identifies these separate sessions instead of implying simultaneous
measurements. Each dataset has per-clip checksums and separate latency summaries.

`tts-comparison.ts` validates that every voice/passage/version has a recording
and that models within a style receive exactly the same input and tags. It keeps
version IDs distinct from model IDs. The comparison selector switches between
Plain text (4 models), Emotion (3), Vocal reaction (3), and All styles (10).
Models appear side by side within each style, then stack on smaller screens.
`?paragraph=p11&style=emotion` links directly to a comparison. English always
shows four models with the American accent tag. The latency language/style
selectors can also be changed independently of the players.

“Play all N” queues the visible versions for one voice; “Play all voices” queues
all seven voices in that view (28 plain, 21 emotion/vocal, or 70 for all Mandarin
styles; 28 English). Changing the passage or style stops playback and clears
hidden player sources. Tags, reasons, exact inputs, generation dates, per-clip
timings, median/p95 tables, and CSV/JSON downloads are available. Audio is loaded
on demand, and the browser makes no ElevenLabs API calls.

Reproduce a run with `ELEVENLABS_API_KEY` set in the environment and
`ffmpeg`/`ffprobe` installed. Generation consumes credits; raw logs stay outside
the repository. Calls and whole runs are sequential, with randomized passage
and voice/model order. One warm-up per voice/model pair is excluded in each run.
Timings include network time and exclude local file writing and decoding;
neither first byte nor full request is pure server processing time or audible
playback latency. Runs resume from successful jobs without charging for them
again. Check the account allowance before starting a batch.

```bash
# Original family (retained for reproducibility)
python3 scripts/benchmark-tts.py --output /path/to/private-v3-run
python3 scripts/package-tts-benchmark.py /path/to/private-v3-run

# New v4 family: plain Mandarin
python3 scripts/benchmark-tts.py --corpus src/data/tts-corpus-v4.json --output /path/to/private-v4-plain
python3 scripts/package-tts-benchmark.py /path/to/private-v4-plain --family v4 --date 2026-09-28

# Matching Mandarin emotion / vocal reaction (repeat with vocal)
python3 scripts/benchmark-tts.py --corpus src/data/tts-corpus-v4-zh-emotion.json --output /path/to/private-v4-emotion
python3 scripts/package-tts-benchmark.py /path/to/private-v4-emotion --family v4 --date 2026-09-28 --style emotion

# English with the same American accent tag
python3 scripts/benchmark-tts.py --corpus src/data/tts-corpus-v4-en-us.json --output /path/to/private-v4-english
python3 scripts/package-tts-benchmark.py /path/to/private-v4-english --family v4 --date 2026-09-28 --language en-US
python3 -m unittest discover -s scripts -p 'test_tts_assets.py'
```

The 1,680 benchmark MP3s (1,400 Mandarin and 280 English) are distributed through
checksum-pinned GitHub release archives. Original releases are named
`tts-v3-benchmark{suffix}-2026-09-25`; new releases are named
`tts-v4-benchmark{suffix}-2026-09-28`. In each family the active suffixes are
empty, `-zh-emotion`, `-zh-vocal`, and `-en-us`. The v4 packaging command verifies
that each passage and tag matches its original corpus before creating the archive.
CI verifies the entire inventory, byte counts, and SHA-256 hashes before installing
an archive into `dist/`. For a local preview, install into `public` before starting
the dev server, or into `dist` after building:

```bash
python3 scripts/install-tts-assets.py ARCHIVE.zip dist --manifest scripts/tts-benchmark-v4-zh-emotion-assets.json
```

Select the matching manifest for each archive. Generated MP3s stay outside Git;
publish each archive before pushing code that references it to master. Existing
release assets are never overwritten. The original untagged English dataset and
`tts-v3-benchmark-en-2026-09-25` release remain installed for old shared URLs.
The original five Multilingual v2 clips and metadata also remain at
`public/tts/audio/2026-09-25/` and `src/data/tts.json`.

The separate microphone pilot adds 21 recordings: one shared Mandarin passage
(`p01`) across seven voices and v3, v4, and v4 Turbo, prefixed with the exact tag
`[speaking into the microphone]`. `/tts/#microphone` pairs each with its existing
plain reference. Pilot settings are stability 0.5, similarity 0.75, seed 42;
original v3 reference settings differ as disclosed on the page. Pilot statistics
are not pooled into the full benchmark. Playback is exclusive across both sections.

The corpus/results use the `-microphone` suffix. Package with
`python3 scripts/package-tts-benchmark.py RUN --pilot microphone --date 2026-09-28`;
the release is `tts-microphone-pilot-2026-09-28`, and its manifest is
`scripts/tts-benchmark-microphone-assets.json`. This brings the active set to
1,701 unique recordings while preserving the older shared URLs.

## LINE architecture comparison

The shareable benchmark is at [/line-v2/](https://jefflai108.github.io/line-v2/).
`public/line-v2/index.html` is a self-contained snapshot comparing v1, v2, and
v2 + follow-up on 50 synthetic conversation turns. It includes measured responses,
latency, three-way AI judging, and optional browser-local blind ratings.

The original v1/v2 measurements and judging are preserved. The follow-up variant
was measured later on the same development cases; the page documents that limit.
This snapshot does not call model APIs or connect to production LINE or memory
services. Ratings stay in each browser and can be exported; they are not synced.
All page content is embedded text, with no generated images or external assets.
The normal Pages build copies it from `public/` to `dist/line-v2/index.html`.

## 台灣語林 · TaiwanCorpus Discovery

The interactive topic tree is served at `/taiwan-corpus/`. It shows a public
snapshot of collected PTT, Dcard and Threads main-post titles, topic assignments,
dates, counts and canonical source links. Full post bodies, previews, reply text
and author metadata stay out of this snapshot. Topic assignments are provisional;
coverage counts describe the collection rather than the population.

The page, assets and generated index live together in a GitHub Release ZIP.
Only the installer and its fixed release namespace are tracked in this repository:

| Setting | Value |
| --- | --- |
| Repository | `jefflai108/jefflai108.github.io` |
| Release tag | `taiwan-corpus-public` |
| Manifest pointer | `taiwan-corpus-manifest.json` |
| Immutable archive | `taiwan-corpus-public-YYYYMMDDTHHMMSSZ-<first12-SHA256>.zip` |
| Installed directory | `dist/taiwan-corpus/` |

[`scripts/taiwan-corpus-assets.json`](scripts/taiwan-corpus-assets.json) pins that
namespace. Every Pages build fetches the small release manifest, downloads the
ZIP it names from the same repository and tag, checks the archive and all five
member hashes, and validates the public-index schema and counts. The allowed ZIP
members are exactly `index.html`, `app.js`, `style.css`, `favicon.svg` and
`data/tree.json`, without an enclosing directory. Extra content fields, unsafe
source links, unexpected files and path traversal are rejected before installation.

The installer rereads the manifest pointer before writing. A changed pointer,
missing asset or failed check stops the build, so incomplete snapshot data cannot
replace the current Pages deployment. The existing image-comparison installer
and its release remain independent.

The corpus publisher generates snapshots outside this repository. To refresh the
site, upload a uniquely named ZIP first, then replace the manifest pointer last.
The pointer's `archive_name` and `asset_name` must both equal the immutable ZIP
name; its byte count and SHA-256 remain those of the original archive. Only after
the pointer is complete should the publisher dispatch this repository's Pages
workflow. This supports regular snapshot updates without generated-data commits.
The public page shows a snapshot, not a connection to the local collector. Publish
the first approved snapshot and pointer before merging this integration.

The installer also writes `/taiwan-corpus/snapshot.json` from the verified pointer,
containing its archive digest, asset name, generation time and post count. This
small deployment marker is generated separately and is not a sixth ZIP member.
The publisher can wait for that public marker to match the new digest before
retiring older archives it owns; replacing a pointer alone is not deployment proof.

For a local preview with the current public release:

```bash
python3 scripts/install-taiwan-corpus-assets.py public
npm run dev
```

For a production preview, run `npm run build`, install into `dist` instead of
`public`, then run `npm run preview`. An already downloaded ZIP and its release
manifest can be checked offline:

```bash
python3 scripts/install-taiwan-corpus-assets.py dist \
  --archive /absolute/path/to/versioned-snapshot.zip \
  --manifest /absolute/path/to/taiwan-corpus-manifest.json
python3 -m unittest discover -s scripts -p 'test_*_assets.py'
```

`public/taiwan-corpus/`, release ZIPs and build output are ignored by Git. Do not
commit a catalog, exported tree JSON, actual post content or private credentials.
Installer tests use authored temporary fixtures only.

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

Colors are normalized separately for each calendar month (including partial
months at the ends of the graph). Zero contributions use the empty shade;
positive counts use four equal ranges relative to that month's highest day.
The darkest shade therefore marks a month's busiest days, while the total and
daily tooltips still show the original counts. `npm test` covers this scale.

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
