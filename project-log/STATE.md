# STATE

**Updated:** 7 Sep 2026

**Active stage:** 1 — Acquisition · **COMPLETE**, milestone Tue 8 Sep met one day early
**Next stage:** 2 — Cleaning (milestone Thu 10 Sep). Runs in its own chat.

## Outcome

**8,459 Lahore houses for sale**, listed between 2 Sep 2023 and 14 Sep 2024, from Ilaan.com.
Above the 3,000 floor, below the 10,000 target — the band where PLAN §8 (as amended) says
data quality outranks quantity.

### Exit criteria

| Criterion | Required | Result |
|---|---|---|
| ToS and robots.txt checked by Nauman and recorded | — | 5 sources graded, `notes/source-evaluation.md` |
| Field-level accuracy, 30-listing manual spot-check | ≥ 98% | **99.17%** — 3 of 360, all 30 rows confirmed checked |
| Coverage of discovered URLs parsed | ≥ 95% | **99.89%** — 8,991 of 9,001, strict, no exclusions relied on |
| Zero requests to disallowed paths | 0 | **0** across ~19,600 logged requests |
| Row and field counts verified, gaps documented | — | reconciled below; gaps in BACKLOG |
| Repo pushed and tagged | — | `v0.1-acquisition` |

All three spot-check mismatches were `area`/`area_unit` — the defect now logged as B-15. The
audit did not merely pass, it located a real problem.

### Reconciliation

```
20,000  listings discovered via the source's own endpoint (Nov 2022 – Sep 2026)
 9,001  inside the selected window (id 556159–697397, Sep 2023 – Sep 2024)
 9,000  fetched successfully                      1 lost to a suspend-time network failure
 8,991  parsed                                   10 unrecoverable soft 404s (B-11)
 8,459  in scope                                532 excluded, with reasons:
                                                    362 type=Land
                                                    165 type=Commercial
                                                      5 type=Apartment
```

Nothing is dropped silently: excluded rows are written to `data/interim/listings.jsonl` with
`in_scope=false` and a `scope_reason`, and are present in the CSV export.

### Field completeness, 8,459 in-scope rows

`price` 99.7% · `area` 99.8% · `area_unit` 100% · `bedrooms` 100% · `bathrooms` 100% ·
`locality` 100% · `latitude`/`longitude` 99.6% · `created_at` 100% · `address` 100%

## Source

**Ilaan.com**, graded B: robots.txt permits the listing paths, and the site publishes no
terms of service. Zameen rejected on terms (clauses 2.17.4 and 2.20 prohibit automated
access outright); Graana rejected because its inventory cannot be enumerated through any
permitted route; Aarz unreachable; JagahOnline is an in-development project.

Listing discovery uses the endpoint Ilaan's own frontend calls — **for listing IDs only**
(D-21). Every modelled field is parsed from the public listing pages. The reasoning, and the
argument against, are in `decisions/02-acquisition.md`.

## Files added this stage

```
src/lhp/scrape/fetch.py       polite cached HTTP, robots enforcement, audit log
src/lhp/scrape/discover.py    walks the discovery endpoint, builds listing URLs
src/lhp/scrape/parse.py       extracts the record from the React payload
config/scrape.yaml            source, scope, window bounds — with the evidence as comments
scripts/run_discover.py       discovery
scripts/run_scrape.py         page fetching, resumable, holds a power request
scripts/run_parse.py          parsing and the coverage report
scripts/sample_listings.py    stratified sample for sizing a run
scripts/make_spotcheck.py     draws and scores the manual accuracy audit
scripts/export_csv.py         CSV view of the parsed rows
tests/                        52 tests; all fixtures synthetic, no Ilaan content committed
project-log/LESSONS.md        22 process lessons, for triage at project close
```

`data/` holds ~9,000 cached pages, the parsed rows and the full request log. All gitignored.

## Next action

Open the stage 2 chat. First activity: read the handoff, then `decisions/02-acquisition.md`
and BACKLOG B-07 through B-17 — four are high severity and two of them (B-07 dedup
fingerprint, B-15 unit correction) change work that PLAN already specified.

## Blockers

None. Stage 2 is unblocked and unstarted.

## Known gaps

- 1 listing lost to a network failure during a machine suspend; 10 return a "Property Not
  Found" template after retries. 11 of 9,001 (0.12%), documented in B-11.
- `data/sample/` is still empty. D-23 requires synthetic rows rather than real listings;
  generate at stage 2 close, once the processed schema is fixed.
