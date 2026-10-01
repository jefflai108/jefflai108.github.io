# Natural bridge publication tooling

## Current reviewed cohort: final-v4

The canonical Natural bridges page now renders the completed current-main
study from serving source `c295145ea863c93f97040520f31a73bf874f5ce4`.
The source includes [reader PR #456](https://github.com/jefflai108/streaming_taiwanese/pull/456)
and [producer PR #457](https://github.com/jefflai108/streaming_taiwanese/pull/457).
Producer merge `5f407752b0dda8994625ee956479715b6c6f8879` has the same full
Git tree as the benchmark source: `2b10d0da5e7d59f9ca21679a69b692cf91642533`.
This benchmark record does not claim a production LINE deployment.

- Raw results SHA-256: `5e7855291d2d71991920ca4e49da4778806e20bb456e72f3c1f12a62ddfee369`
- Quality report SHA-256: `186d337822800332991962712085d59b11971defc77d8fffdf41adb3fb9cb4ae`
- Completed cohort: 60 slots, 84 turns, 42 paired turns and 42 successful
  blinded judgments, across both synthetic accounts and one repeat per arm.
- Bridge preference: natural 27, baseline 4, tie 1, not applicable 10.
- Captured bridge p50: baseline 1.975 s, natural 2.300 s, 24 observed per arm.
- Delegated final p50: baseline 14.385 s, natural 14.509 s, 14 observed per arm.
- All 12 requested host injections applied; all 35 captured capability calls
  had valid scope and arguments. These are authored/injected scenarios and
  captured transport, not production reliability or LINE API latency.

Observed routing limits remain explicit: revised 0/4; successful status 0/4;
resubmitted 0/4, with four fresh accepted tasks instead; crisis-resource
prompts delivered four direct answers without tool calls. Planned scenario
names are not evidence of observed branches. Final-answer quality dimensions
remain separate from bridge quality and are not uniformly improved.

Before replacing the canonical artifacts, independently verify the exact
source and both raw file hashes, then run the renderer below against the
completed frozen study. Run `npm test` and `./node_modules/.bin/astro build`
for local validation; the direct build avoids refreshing unrelated profile
data. Verify the public and built JSON/page match, inspect all eight tabs and
filters, and preserve the final-v3 archives. Open a reviewable website PR;
merging to `master` triggers the existing GitHub Pages deployment workflow.

Final-v4 validation passed all 34 website tests, the Astro build, frozen
publication guard and strict source/hash/count preflight. An independent
artifact audit matched captured public messages and metrics to raw results,
verified all eight navigation tabs, both pages' `noindex,nofollow`, no
root-homepage benchmark link, and preserved archive bytes. Fresh native UI
checks covered the desktop final-v4 page, all eight tabs and the primary
account filter (21/42). Combined filters, mobile layouts and browser console
inspection were not repeated: browser-client commands were unavailable and
native UI focus moved to user activity. The page CSS and filter JavaScript
are byte-identical to final-v3, which retains its earlier full browser QA;
this supports the unchanged UI behavior but is not fresh mobile verification
of the new measured copy.

## Rendering and publication guard

Run from the site repository after generation and judging finish:

```bash
node scripts/render-natural-bridges.mjs /path/to/study/results.json /path/to/study/quality-results.json
```

Keep the full frozen study directory available: `plan.json`,
`quality-samples.json`, and the archived `source/` tree are required. The
renderer checks the study source and exact result bytes, rejects unknown or
duplicate identities, and invokes `check-natural-bridges-publication.py`
before writing either public artifact. Python defaults to `python3`; set
`NATURAL_BRIDGES_PYTHON` to select another interpreter. No provider or LINE
request is made by this tooling.

The Python adapter verifies plan, sample, judge, and individual judgment
bindings. It imports the existing `publication.py` from the frozen source
after checking its manifest hash. Every string in the allowlisted public
projection, including planned text, captured messages, and judge reasons,
is passed through that module's measured-text guard. Known secret values
come only from explicit credential fields in the supplied raw study and
quality JSON; no credential files are read. Rejected content stops
publication. Sanitized replacement text is never substituted into results.
The renderer also checks credential patterns and private URLs.

To validate a projected public JSON independently without writing anything:

```bash
python3 -I -B scripts/check-natural-bridges-publication.py \
  --results /path/to/study/results.json \
  --quality /path/to/study/quality-results.json \
  --public /path/to/projected-public.json
```

The headline statistics retain their observed and planned denominators:

- Frontend latency sums the measured routing-call durations. Executor start
  is measured from ingress under the benchmark's serial scheduling.
- Bridge latency uses the first confirmed bridge capture; delegated final
  latency uses the last confirmed final capture. Direct answers and terminal
  notices have separate rows.
- Paired deltas are natural minus baseline within the same case, account,
  repeat, and turn. Both sides must have the same captured response phase.
  The denominator counts pairs with that phase observed on either side;
  total planned pairs are also shown. Missing captures are never imputed.
- Diversity counts exact captured bridge text arrays, including whitespace
  and message boundaries. It excludes unused candidates, notices, duplicates,
  and final answers. This descriptive count is not a quality score.

Both arms share the benchmark wrapper's cap of **12 admitted host tool calls
per task attempt**. Production V3 has no such benchmark cap. The Hermes
executor otherwise uses V3's unbounded execution mode; the outer slot timeout
is also a benchmark limit. The renderer preserves the study's
`metadata.host_tool_budget` disclosure in the public JSON and presents it in
the methodology so a shared benchmark constraint is not presented as
production behavior.

`npm test` covers metric attribution and publication binding, including an
adapter contract test double in a temporary frozen study. Tests write only
temporary fixture pages; no example result page is installed in `public/`.

Observed coverage for NB006 revision, NB008 resubmission and NB009 crisis
lookup is counted per planned turn in `observed_coverage`. The rendered
notes include partial outcomes and missing turns. A revised or resubmitted
branch requires a matching host phase and captured delivery. A new accepted
task is reported separately from resubmission. Crisis lookup counts actual
`public_search` or `read_link` calls, including rejected or failed calls;
these are not claims of successful research. Missing tool evidence is not
treated as proof that no tools ran.

The original final-v3 public data is preserved at
`public/line-v3/natural-bridges-final-v3-results.public.json`, with exact
SHA-256 `e278ed448529fe8858bdc2d484742f9cf43fd85b6a4555ce2f129e1ddea77a25`.
Its frozen source is `a3009d493cc9708c0666554c27cef38b03f15b89`, raw results
SHA-256 is `c5befbd5565138ff2c894be64d9a78f97333524cc3e4a3aed69b425ce588b939`,
and private quality report SHA-256 is
`2c6a76f482d40de35c68c335d7d9dfd8d728acac858d0405e94957bf12520dcb`.

`natural-bridges-final-v3.html` preserves that cohort's displayed results.
Only its heading, canonical URL, JSON download reference and archive notice
are changed from the original page, whose SHA-256 was
`415d879068b7006a1f4645836b1aa5d96a35c5ab4bf9af38a2b2e9dbdf77a5fe`.
The archive tests verify exact JSON bytes and that undoing those four link
and identification changes recovers the original HTML hash. Rendering a
new reviewed study updates the canonical page and data filenames, adds the
archive link, and never rewrites the final-v3 artifacts. Both pages retain
`noindex,nofollow`; the root homepage remains without a benchmark link.
