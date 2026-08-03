# jefflai108.github.io

Personal homepage — [jefflai108.github.io](https://jefflai108.github.io).

Astro 5, no UI framework, no CSS framework. Static output deployed to GitHub Pages by
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) on every push to `master`.

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
| `src/data/career.ts` | Experience and education timelines, talks, service |
| `src/data/oss.ts` | Open-source projects and their star counts |
| `src/data/writing.ts` | The Medium archive listed on `/blog/` |

Two things are deliberately parameterised in `site.ts`:

- **`scholarStats`** is a manual snapshot with an `asOf` date. Google Scholar has no public API,
  so refresh it by hand every so often and bump `asOf`.
- **`orgs`** holds every outbound URL in one place. `waveforms.ai` is absent on purpose — the
  domain stopped resolving after the Meta acquisition, so the acquisition coverage is linked instead.

## Writing a blog post

Drop a Markdown file in `src/content/blog/`. The filename becomes the URL
(`my-post.md` → `/blog/my-post/`). See [`example-post.md`](src/content/blog/example-post.md)
for the frontmatter schema — it is a draft, so it stays invisible until you flip `draft: false`.

To list a post that lives elsewhere, add an `external:` URL to the frontmatter and no local
page is built.

## The GitHub contribution graph

`scripts/fetch-contributions.mjs` pulls the last year of contributions from the GitHub GraphQL
API into `src/data/contributions.json`, and runs automatically as a `prebuild` step. Locally it
uses your `gh auth token`; in CI it uses the workflow's `GITHUB_TOKEN`. If the fetch fails for
any reason it keeps the committed snapshot rather than breaking the build.

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
