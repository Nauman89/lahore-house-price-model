# Lahore Residential House Price Model

Predicting the asking price of residential houses in Lahore from listing features —
acquisition, cleaning, analysis, modelling and a deployed price estimator.

> **Project status: Stage 2 of 8 — Cleaning complete.**
> Delivery target: 24 September 2026. Stages are tagged as they complete
> (`v0.1-acquisition`, `v0.2-cleaning`, …).

---

## The problem

Residential property in Lahore is priced largely by locality. Two houses of identical size
and specification can differ severalfold in price depending on the society, phase and block
they sit in, and that knowledge lives with agents rather than in any published index. This
project builds a reproducible pipeline that acquires public listing data, quantifies what
actually drives asking price, and predicts it for an unseen property.

## What this predicts, and what it does not

The model predicts **asking price** — what a comparable house would be *listed* at. It does
not predict sale price. Listing prices in Pakistan routinely sit above achievable value, and
no public registry of transaction prices is available. This is a genuine limitation of the
data, not of the method, and results should be read accordingly.

Three further limitations, established during acquisition and cleaning, all worth knowing
before reading any number this project produces.

**The data is a twelve-month window, not current.** 8,459 listings posted between 2 September
2023 and 14 September 2024. The source stopped recording structured location and coordinates
on listings posted after roughly September 2024, and its posting volume collapsed around the
same time, so a more recent window is not available at usable quality. The model therefore
predicts asking price *as listed during that window*. Applying it to today's market
extrapolates beyond the training period, in an economy where that matters.

**Near-identical listings are collapsed.** Where several listings share a location, size and
room count and differ only in price — overwhelmingly a single poster listing one product many
times in one batch — they are represented by one row at the median price, carrying a count of
how many listings it stood for. The model therefore predicts what a comparable house would be
*listed at on average*, not where an individual poster would place it in their own price
range. On the listings that had duplicates, that unresolvable spread ran 3.2% at the median
and 13.9% at the 90th percentile.

**One source, and a small one.** All listings come from a single Pakistani portal. Any bias in
who lists there — which societies, which price brackets, which kinds of seller — is inherited
whole. The findings describe that portal's Lahore inventory, not the Lahore market.

## How this project was built

I used Claude to write code. The source evaluation, the manual accuracy audit and the
judgement calls are mine. Every decision taken on the project is logged in
`project-log/decisions/` with the reasoning and the rejected alternatives.

## Where to look first

If you are assessing this repository rather than using it:

| File | Why |
|---|---|
| [`notes/source-evaluation.md`](notes/source-evaluation.md) | Five candidate sources graded on terms, robots.txt and enumerability. One rejected on a clause that would have been easy to ignore |
| [`project-log/decisions/02-acquisition.md`](project-log/decisions/02-acquisition.md) | Every acquisition decision with its reasoning and what was rejected — including a coverage failure that was diagnosed rather than argued away |
| [`src/lhp/scrape/fetch.py`](src/lhp/scrape/fetch.py) | The acquisition layer: robots enforcement, caching, an auditable request log |
| [`project-log/decisions/03-cleaning.md`](project-log/decisions/03-cleaning.md) | Every cleaning decision — including five numbers fixed at the planning stage that did not survive measurement, amended with the evidence, and one rule reversed mid-stage after it turned out to rest on a false premise |
| [`src/lhp/clean.py`](src/lhp/clean.py) | The cleaning pipeline: every drop flagged with a reason and counted, nothing removed silently, a declared schema rather than an inferred one |
| [`tests/`](tests/) | 161 tests. The fixtures pin the findings that cost the most to discover, including the rules that were wrong first |

## Approach

| Stage | What it does |
|---|---|
| Acquisition | Scrapes public house listings for Lahore, caching every page fetched — **complete**: 8,459 houses, 99.89% coverage, 99.17% field accuracy on a manual audit |
| Cleaning | Reconciles, deduplicates and validates listings into an analysis-ready table — **complete**: 6,468 rows, 139 listings excluded with a reason each, 1,852 collapsed into their duplicate groups |
| EDA | Establishes the distributions, anomalies and relationships that drive feature choices |
| Feature engineering | Builds features traced to EDA findings, with leakage checked explicitly |
| Modelling | Baseline first, then gradient boosting, optimised on absolute error in log price |
| Validation | Held-out performance against locked acceptance criteria, segmented by price band and locality |
| Reporting | Findings written for a non-technical reader |
| App | Streamlit estimator returning a price range for a described property |

Performance is reported as **MdAPE** with **PPE10/PPE20** alongside — the measures used in
property valuation practice — rather than RMSE, and is broken out by segment so that a
single headline number cannot conceal where the model fails.

## Running it

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Nauman89/lahore-house-price-model.git
cd lahore-house-price-model
uv sync
```

For environments without uv, a pinned `requirements.txt` is exported from the same lockfile.

Reproducing the processed dataset from the parsed listings:

```bash
python scripts/run_clean.py
```

It writes the analysis set, the excluded rows with their reasons, a reconciliation report and
a synthetic sample, and rewrites nothing upstream of `data/interim`. The scraping stage is not
re-run: `data/raw` is immutable and every page fetched is cached.

Full run instructions are added as each stage completes.

## Repository layout

```
config/        scraper configuration
data/          raw · interim · processed (gitignored) · sample (synthetic, committed)
src/lhp/       scraping, cleaning, feature and model modules
notebooks/     EDA, feature exploration, modelling, validation
scripts/       entry points
models/        serialised model and metadata card
reports/       figures, technical notes, findings deck
app/           Streamlit estimator
notes/         reference notes
project-log/   plan, current state, backlog, decision log
```

## Data and terms of use

**Source: [Ilaan.com](https://www.ilaan.com).** Five candidate portals were evaluated on
their terms and `robots.txt` before any request was made. Ilaan's `robots.txt` permits the
listing paths, and the site publishes no terms of service anywhere. Zameen was rejected
outright — its terms prohibit automated access in as many words — despite having the largest
Lahore inventory of any candidate. The full evaluation, including the verbatim clauses and
robots groups, is in [`notes/source-evaluation.md`](notes/source-evaluation.md), and the
reasoning in [`project-log/decisions/02-acquisition.md`](project-log/decisions/02-acquisition.md).

The scraper observes a 1–2 second request delay, caches every page so no URL is fetched
twice, logs every request with the robots decision that permitted it, and accesses no paid or
contact-unlocked personal data. Agent contact details are discarded at the parse boundary, so
they never enter `data/` at all.

**The committed sample is synthetic.** `data/sample/` holds 200 generated rows matching the
processed schema column for column — invented listings that reproduce the *shape* of the data
and none of its content, so the notebooks run from a clean checkout without republishing
anything of Ilaan's. This is deliberate and the reasoning is worth stating: because Ilaan
publishes no terms, no clause prohibits redistribution **and no licence permits it** —
copyright subsists without a terms page. An absent prohibition is not a grant. The real
dataset is reproducible by running the scraper and then the cleaning pipeline; it is not
distributed here.

## Licence

Code is released under the [MIT Licence](LICENSE).

**The licence covers the code only.** Scraped listing data is not covered and remains subject
to the source site's terms.
