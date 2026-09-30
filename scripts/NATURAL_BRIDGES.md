# Natural bridge publication tooling

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
