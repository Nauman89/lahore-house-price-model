# Decisions — Stage 1: Acquisition

Append-only. One entry per decision: what, why, what was rejected and why.
Full evidence, verbatim robots.txt groups and terms clauses: `notes/source-evaluation.md`.

---

**D-20 · Source selected: Ilaan.com. Every other candidate rejected**

Five sources evaluated 4–5 Sep 2026. Terms and robots.txt read by Nauman in every case;
Claude fetched nothing from a candidate domain during evaluation (D-17).

| Source | Grade | Rejected because |
|---|---|---|
| Zameen | C | Terms prohibit automated access outright. Clause 2.17.4 forbids "spiders, robots, crawlers, data mining tools"; clause 2.20 grants a **personal use** licence expressly excluding "collection, aggregation, copying". Largest Lahore inventory of any candidate; rejected anyway |
| Graana | E | Permitted to read, impossible to enumerate. Listing pages allowed, but all 301 result pages past the first sit behind `?…` which `Disallow: /*?` blocks, and no sitemap is published at any conventional path |
| Aarz | — | Domain unreachable, 5 Sep 2026 |
| JagahOnline | — | Site is an in-development open-source project, not a live listings portal |
| OLX Pakistan | — | Not checked. Superseded once Ilaan passed; ranked last on terms risk and on data quality |
| **Ilaan** | **B** | **Selected.** robots.txt permits the listing paths; no terms of service exist anywhere on the site |

Grade **E** was added to the framework mid-evaluation, after Graana. The original grading in
`notes/source-evaluation.md` §1 did not anticipate a source that is permitted to read but
offers no lawful way to discover what exists. That gap is itself a finding.

**D-21 · Amendment to D-17: the `/api/` prohibition is relaxed, for discovery only**

D-17 set a self-imposed limit of "no `/api/` paths unless the terms cover them". On Ilaan that
condition is **unmeetable rather than unmet** — the site publishes no terms at all, so no
amount of reading or waiting could satisfy it.

Ilaan's listing pages are permitted but cannot be enumerated: pagination is performed by
JavaScript and carries no URL state, `/house-for-sale/lahore` serves only the ~200-listing
verified subset, and the 58 declared sitemaps contain a single canonical URL form for every
sale listing of every type, with neither city nor property type recoverable from the URL.
Reaching the Lahore house inventory through permitted routes alone would require fetching on
the order of 300,000 pages — infeasible against a three-day stopping rule, and far heavier on
the operator than the alternative.

Pagination calls `https://npi.ilaan.com/api/properties-new/v2`. Under RFC 9309 a robots.txt
governs exactly one authority: `www.ilaan.com`'s `Disallow: /api/` does not reach the host
`npi.ilaan.com`. That host's robots.txt was read on 5 Sep 2026 and contains only the
Cloudflare Content Signals boilerplate — no user-agent groups, no rules, and no content
signals set, which by the boilerplate's own clause (c) "neither grants nor restricts
permission". No restriction applies.

**Decided:** the endpoint may be used for **discovery only** — the list of Lahore house
listing IDs and the total count. Every modelled field is parsed from
`www.ilaan.com/house-for-sale/…` pages, which are unambiguously permitted. The API substitutes
for the sitemap Ilaan does not publish, and for nothing else.

Weighed against: `www.ilaan.com`'s `Disallow: /api/` is the only statement Ilaan has ever made
about API crawling, and it points the other way. It governs a different host and no terms
extend it, but it is recorded here as the argument on the other side rather than omitted.

Rejected: **wholesale use** of the API for listing content — narrow use is the smaller ask and
the easier position to defend. **Declining entirely and falling back to a public dataset** —
the available Kaggle datasets are scrapes of Zameen, whose terms this project read and
respected, so the fallback would build a project about respecting terms on data that exists
because someone did not; that is worse on the dimension the project is about, not better.
**Emailing Ilaan for permission** — the correct move in principle and it would have upgraded
this to grade A, rejected on the practical ground that a weekend enquiry to a portal that
seldom replies cannot gate a three-day stage.

Self-imposed constraints, all enforced in code and visible in the request log: 1–2s delay on
API calls as everywhere else, no concurrency; a User-Agent naming the project, repository and
a contact address so the operator can identify and object; immediate hard backoff on 429 and a
full stop if we are ever blocked; every API call logged with the same robots decision and
robots.txt hash as every page fetch.

**D-22 · Agent contact details are dropped at the parse boundary**

The discovery endpoint is expected to return agent contact information. PLAN §11 excludes
personal data. Contact fields are discarded in `parse.py` before anything is written, and
cached API responses are redacted before they are retained. This is a stronger rule than
"don't publish it": the fields do not enter `data/` in parsed form at all.

**D-23 · `data/sample/` ships synthetic rows, not real listings**

PLAN §10 commits ~200 sample rows to the public repository so notebooks run from a clean
checkout. Ilaan publishes no terms, which means no clause prohibits redistribution **and no
licence permits it** — copyright subsists without a terms page. The sample will therefore be
synthetic rows matching the real schema, column for column. The notebooks still run; nothing
of Ilaan's is republished. Amends PLAN §10, which described the sample as real rows.

**D-24 · Source stability recorded as an evaluation criterion for future projects**

Ilaan returned site-wide 502 errors repeatedly during evaluation, and 3 of its 58 declared
sitemaps are empty. Neither was on the criteria list in PLAN §11, and both matter for a source
a multi-day unattended scrape depends on. Added for the next project rather than retrofitted
here. Handling: retries with exponential backoff, and 5xx categorised separately from 404 in
the failure log, so "the site was down" and "the listing was removed" are never pooled.

**D-25 · Process: check enumerability before reading terms**

Roughly 20 minutes was spent recording detailed field observations for Graana before a
30-second check killed it on pagination. Correct order for a candidate is: robots.txt, then
the page-2 URL, then the sitemap — three minutes, and it eliminates a source before any
investment. Terms and field-level observations come after. Recorded for the §13 process review.

A second process finding, same stage: `pyproject.toml` shipped from stage 0 with no
`[build-system]` table, so uv treated the project as virtual — dependencies installed, `lhp`
itself never installed, and `import lhp` failed. Stage 0's exit criterion "environment created
and verified" passed because dependency resolution was verified and importing the project's own
package was not; nothing had imported it until `fetch.py` existed. Add to the stage 0 checklist:
after `uv sync`, import the project package. Fixed 5 Sep 2026, along with modernising the
licence declaration to PEP 639 form, which `setuptools>=77` requires.

---

## Stage close, 7 Sep 2026

**D-26 · Window: property ids 556159–697397, listings of 2 Sep 2023 – 14 Sep 2024**

Discovery returned 20,000 listings spanning Nov 2022 to Sep 2026. Two facts, both measured,
fixed the window from both ends.

*Ceiling.* Structured location collapses above id ~700000. Measured across 145 parsed pages:
below the break, `locality` and coordinates are present on 100% of listings; above it, 1% and
2%. Ilaan evidently changed its posting flow in late 2024 and newer listings carry only a
free-text address. Location is the dominant price driver in Lahore, so those ~1,500 listings
cannot support the model. Excluded deliberately, with the reason recorded; `parse.py` still
emits them if the window is widened.

*Floor.* Chosen for volume against a 3,000 post-dedup floor. Counts are exact against dates
read from real pages: id ≥ 556159 gives 10,500 discovered, ~9,000 within the ceiling.

The result is a twelve-month window rather than the four-year span any wider choice would
have produced — materially better for a design that assumes a cross-section, and the reason
PLAN §3 needed only an amendment rather than a rethink. Widening later costs only the
additional pages, since everything fetched is cached.

Rejected: **2025 onwards** (413 listings, ~371 houses — far below the floor); **everything**
(20,000 listings spanning 46 months, mixing 2022 asking prices with 2026 ones through a
period of severe inflation).

**D-27 · Coverage is reported strictly, without excluding removed listings**

The stage 1 criterion is ≥95% of discovered URLs parsed. The intake definition (4 Sep,
before any data existed) allowed listings removed between discovery and fetch to leave the
denominator. They are not being excluded, because the strict figure already clears the gate:
**8,991 of 9,001 = 99.89%**.

This matters because of what happened first. An initial run produced 89.23% coverage with 969
`no_initial_property` failures. Every one of those pages carried Ilaan's "Property Not Found"
template, which supported an argument — pre-agreed denominator, correct arithmetic — that
coverage was really 100%. Re-fetching three of the 969 returned live listings with normal page
sizes, 3 of 3. They had never been removed; the template was served transiently under load and
cached as a success. The reasoning was sound and the premise was false.

Fixed systematically rather than by exception: `FetchConfig.content_validator` rejects a 2xx
response that does not carry the content it should, retries it, never caches it, and treats an
already-cached invalid entry as a miss so a re-run repairs itself. The re-run recovered 942
listings (`invalid_cache` 969, `invalid_content` 43, unrecoverable 10). Where a claim survives
without a supporting premise, the premise is not relied upon. See LESSONS L-18, L-20.

**D-28 · Field accuracy: 99.17%, from a sample re-drawn after the data changed**

30 listings, 12 fields, 360 comparisons, 3 mismatches. All three are `area` or `area_unit` —
the defect logged as B-15, where Ilaan's payload states marla for a listing its own title
calls kanal. Our extraction is faithful; the source field is wrong.

Two procedural notes, both of which changed the number.

*The sample was re-drawn.* An earlier draw scored 100% on a 7,517-row corpus, but the data
subsequently grew to 8,459 rows and the 942 additions were exactly the population that draw
could not reach. Sound evidence about the wrong population. Sheets are now named by seed with
a provenance sidecar recording the corpus size, so a stale draw is visible rather than
assumed.

*The scorer could not tell a completed audit from an untouched sheet.* Blank
`mismatched_fields` meant "no disagreements", and an unfilled file is entirely blank, so an
unopened sheet scored 100% and printed PASS. A `checked` column now requires an affirmative
mark per row; unmarked rows are excluded and the gate reports INCOMPLETE rather than a
percentage. The defect was in the verification layer — the layer least likely to be verified
itself. See LESSONS L-22.

One mismatch is conservative: the page displays "1 Kanal 2 Marla" where we recorded 22 marla,
which is the same quantity and the representation cleaning will adopt. Counted against
ourselves rather than adjudicated in our own favour. Excluding it would give 99.72%.

**D-29 · Test fixtures are synthetic, never cached pages**

52 tests cover the acquisition modules. Every fixture is invented: the tests reproduce the
*shape* of Ilaan's pages — an RSC payload split across push calls, JSON-LD, the soft-404
template — with fabricated values. Committing a real cached page as a fixture would
redistribute Ilaan's content in a public repository, which is the same objection that sends
`data/sample/` synthetic under D-23. Consistency here is not pedantry: a repository that
argues for restraint in its decision log and ignores it in `tests/` argues for nothing.

The suite pins the findings that cost the most to discover — Graana's duplicate
`User-agent: *` groups, the longest-match rule, the unreadable-robots fail-closed behaviour,
and the poisoned-cache repair.

**D-30 · Spot-check sheets are gitignored; provenance files are committed**

`reports/spotcheck-fields-*.csv` carry real prices, areas and localities for 30 listings.
Gitignored under D-23's reasoning. The `.meta.json` sidecars carry no listing data and are
committed, and the accuracy result is recorded here — so the audit is reproducible from the
seed without republishing the rows.
