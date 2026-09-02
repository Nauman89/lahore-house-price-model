# Lahore Residential House Price Model

Predicting the asking price of residential houses in Lahore from listing features —
acquisition, cleaning, analysis, modelling and a deployed price estimator.

> **Project status: Stage 0 of 8 — Planning & setup.**
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

## Approach

| Stage | What it does |
|---|---|
| Acquisition | Scrapes public house listings for Lahore, caching every page fetched |
| Cleaning | Reconciles, deduplicates and validates listings into an analysis-ready table |
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
git clone https://github.com/<user>/lahore-house-price-model.git
cd lahore-house-price-model
uv sync
```

For environments without uv, a pinned `requirements.txt` is exported from the same lockfile.

Full run instructions are added as each stage completes.

## Repository layout

```
config/        scraper configuration
data/          raw · interim · processed (gitignored) · sample (committed)
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

The source site's terms of service and `robots.txt` were reviewed before any request was
made, and the findings are recorded in `project-log/decisions/`. The scraper observes a
request delay, caches every page so no URL is fetched twice, and accesses no paid or
personal data. Source and terms are named here once acquisition is complete.

Because the underlying listing data is not ours to redistribute, only a small **sample** is
committed, under `data/sample/`. The full dataset is reproducible by running the scraper.

## Licence

Code is released under the [MIT Licence](LICENSE).

**The licence covers the code only.** Scraped listing data is not covered and remains subject
to the source site's terms.
