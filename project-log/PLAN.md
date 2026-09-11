# PLAN — Lahore Residential House Price Model

**Repo:** `lahore-house-price-model`
**Owner:** Nauman Rasheed
**Planned:** 2 Sep 2026 · **Start:** 3 Sep 2026 · **Delivery:** 24 Sep 2026
**Status:** signed off 2 Sep 2026

---

## 1. Brief

No live job post. Reconstructed from two to three Upwork posts seeking scrapers for
residential and commercial property listings, expanded into a full end-to-end machine
learning engagement.

**Reconstructed statement of work:** acquire residential house listings for Lahore from a
public property portal, clean and validate them, analyse the market, and build a model
that predicts a property's asking price from its features. Deliver as a reproducible
repository with a client-facing report and a working price-estimator application.

The brief is an assumption, not a client instruction. See `decisions/01-planning.md` D-01.

---

## 2. Deliverable

| # | Artifact | Form |
|---|---|---|
| 1 | Listing scraper | `.py` module — configurable, cached, resumable |
| 2 | Cleaning pipeline | `.py` — raw → interim → processed, rerunnable from raw |
| 3 | Market analysis | notebook — Lahore house market EDA |
| 4 | Feature engineering | `.py` module |
| 5 | Model | notebook + serialised model with a metadata card |
| 6 | Validation | held-out performance, segmented error analysis, SHAP |
| 7 | Findings deck | 8–12 slides, client-facing |
| 8 | Price estimator | Streamlit app, publicly deployed |
| 9 | Documentation | README, technical notes, `project-log/`, `notes/` |

---

## 3. In scope

- Lahore only
- Residential **houses** only
- For-sale listings only
- Asking price in PKR as the target
- **A twelve-month window, not a snapshot** — amended 6 Sep 2026. Ilaan's archive spans
  Nov 2022 to Sep 2026, but structured locality and coordinates are absent on everything
  posted after ~Sep 2024, and posting volume collapsed after mid-2024. The usable window is
  **2 Sep 2023 – 14 Sep 2024**. Twelve months is close enough to a cross-section to keep the
  design, but listing date is carried through cleaning as a control, and the extrapolation
  risk when predicting for today is disclosed in the README. See `decisions/02-acquisition.md`

## 4. Out of scope

- Flats and apartments
- Plots and land
- Upper/lower portions
- Commercial property
- Rental listings
- Cities other than Lahore
- Registry or transaction prices
- Price trends or time-series analysis
- Any deployment beyond Streamlit Community Cloud free tier
- Scheduled or automated re-scraping

---

## 5. Acceptance criteria

### 5.1 Model — PROVISIONAL, locked after EDA

| Level | Criterion |
|---|---|
| Stretch | MdAPE ≤ 15% |
| **Accept** | **MdAPE ≤ 20% and PPE20 ≥ 55%** on held-out data |
| Floor | MdAPE > 30% — not honestly a price model; reframe the deliverable around the pipeline and market analysis, and state why the prediction target was not reachable |

Set provisionally on 2 Sep 2026 without sight of the data. **Locked at the close of EDA**
and logged in `decisions/04-eda.md`, once the price distribution, locality granularity and
junk rate are known.

**Reported:** MdAPE (headline), PPE10 and PPE20 (supporting), MAE in PKR (for readers who
think in rupees), R² on log price (internal model comparison only).

**Segmented, not just aggregate:** MdAPE broken out by price band and by locality tier. A
single headline number hides a model that works in established societies and fails on the
periphery.

**Baseline to beat:** median price-per-marla by locality × size band. Reported alongside the
final model. If gradient boosting adds little over it, that is the finding and it is
reported as such.

### 5.2 Optimisation objective

**MAE on `log(price)`** — `objective='mae'` (LightGBM), `reg:absoluteerror` (XGBoost).

Log because price is right-skewed and error is proportional, not absolute. Absolute rather
than squared error because the acceptance metric is a *median* statistic and squared error
chases the tail of over-priced listings. RMSE on log price is reported as a secondary
diagnostic, not optimised for.

### 5.3 Scraper — stage 1 ships independently

The scraper is linked as a standalone portfolio piece before the model exists, so it has
its own definition of done:

- **Field-level accuracy ≥ 98%** on a manual spot-check of 30 randomly sampled listings,
  checked field by field against the live page
- **Coverage ≥ 95%** of discovered listing URLs parsed successfully; every failure logged
  and categorised, none silently dropped
- **Zero requests to disallowed paths**, verified against the cached request log

---

## 6. Stages and exit criteria

Each stage runs in its own chat. A stage does not begin until the previous stage's criteria
pass. Every stage closes with a handoff message written for the next chat.

| # | Stage | Exit criteria |
|---|---|---|
| 0 | Planning & setup | PLAN signed off; environment created and verified; repo initialised and pushed |
| 1 | Acquisition | ToS and robots.txt checked **by Nauman** and recorded; scraper acceptance criteria (5.3) met; every page cached; row/field counts verified against expectation; known gaps documented |
| 2 | Cleaning | Every transformation justified and logged; row counts reconciled before and after every merge; no silent drops; dedup rule applied and its effect quantified; raw data untouched |
| 3 | EDA | **Acceptance criteria locked and logged**; every column's distribution reviewed; every anomaly explained or logged in BACKLOG; leakage risks identified; findings written and ready to drive feature choices |
| 4 | Feature engineering | Every feature traced to an EDA finding; leakage checked explicitly; definitional relationships verified |
| 5 | Modelling | Baseline established first; model choice justified against at least one alternative; split is group-aware on the dedup fingerprint |
| 6 | Validation | Clear pass or fail against the locked criteria; performance on genuinely held-out data; segmented error analysis reviewed; limitations documented |
| 7 | Reporting & handover | README and technical notes complete; notebooks run clean top to bottom; repo reproducible from a clean checkout; two-line proposal version written |
| 8 | Streamlit app | Deployed, publicly reachable, returns a price range not a point estimate |

---

## 7. Milestone timeline

16 business days. Tracked in days against milestones, not hours.

| # | Stage | Planned | Milestone | Actual | Variance | Effort |
|---|---|---|---|---|---|---|
| 0 | Planning & setup | 1d | Thu 3 Sep | 1d — done 2 Sep | −1d | as planned |
| 1 | Acquisition | 3d | Tue 8 Sep | 3d — done 7 Sep | −1d | heavy |
| 2 | Cleaning | 2d | Thu 10 Sep | 1d — done 8 Sep | −2d | |
| 3 | EDA | 2d | Mon 14 Sep | done 11 Sep | −1d | as planned |
| 4 | Feature engineering | 1.5d | Tue 15 Sep | 1d, done 11 Sep | −2d | as planned |
| 5 | Modelling | 2d | Thu 17 Sep | | | |
| 6 | Validation | 1d | Fri 18 Sep | | | |
| 7 | Reporting & handover | 1.5d | Tue 22 Sep | | | |
| 8 | Streamlit app | 1d | Wed 23 Sep | | | |
| 9 | Contingency | 1d | Thu 24 Sep | | | |

**Client-facing delivery date: Thursday 24 September 2026.** Internal target: 23 September.

Each stage is pushed to GitHub at its close and tagged (`v0.1-acquisition`,
`v0.2-cleaning`, …). The README states the current phase from the first commit.

**Effort** column: `light` / `as planned` / `heavy`, recorded from memory at stage close. Not
timed. Its only purpose is to inform future fixed-price quotes.

---

## 8. Stopping rules

Hit a stopping rule and work halts. Extending it is Nauman's explicit decision, logged.

| Stage | Rule |
|---|---|
| Acquisition | 10,000 clean listings **or** 3 days, whichever first. Floor 3,000 — below that, stop and reconsider the source rather than grinding |
| Cleaning | 2 days **or** flagged near-duplicate groups below 5% of rows, whichever first |
| Feature engineering | 30 engineered features **or** 1.5 days, whichever first |
| Hyperparameter tuning | 60 Optuna trials per model **or** 3 hours total **or** no improvement in the best trial across 20 consecutive trials, whichever first |

Hours appear here only as a guardrail on sub-day activity. They are not a billing or
tracking unit.

---

## 9. Environment and tooling

| Item | Decision |
|---|---|
| Python | 3.13 |
| Environment | `uv venv --python 3.13`, one venv per project |
| Dependencies | `pyproject.toml` + `uv.lock` as source of truth; `requirements.txt` exported for non-uv users |
| Editor | VS Code (Python + Jupyter extensions) |
| Version control | git + GitHub, public repo, tagged per stage |
| Licence | MIT for code. Data licensed separately under the source's terms, stated in README |

3.13 over 3.14: the full stack including CatBoost has Windows wheels for both, but nothing
here exploits 3.14's features and Streamlit Community Cloud defaults to 3.12. 3.13 removes
a class of day-15 surprises for no cost.

### Notebook / script split

Rerunnable work is a module. Narrative work is a notebook that imports from it.

- **Modules** (`src/lhp/`): scraping, cleaning, feature engineering, model training, plot styling
- **Notebooks** (`notebooks/`): EDA, feature exploration, modelling, validation

Scraping never runs in a notebook — a kernel restart loses hours and it cannot run unattended.

### Reusable across projects

Flagged as templates, structured as modules rather than inline code:
`scrape/fetch.py` (polite cached HTTP), `viz.py` (plot styling), validation helpers.

---

## 10. Repository layout

```
lahore-house-price-model/
├── README.md  LICENSE  .gitignore  .env.example
├── pyproject.toml  uv.lock  requirements.txt
├── config/scrape.yaml           # source, scope, window bounds, delays
├── tests/                       # pytest; added stage 1 with the pytest dev dependency
├── data/
│   ├── raw/                     # gitignored, immutable
│   │   └── cache/               # gitignored, every page fetched
│   ├── interim/  processed/     # gitignored
│   └── sample/                  # committed: ~200 rows + reason
├── src/lhp/
│   ├── scrape/  fetch.py  discover.py  parse.py
│   ├── clean.py  features.py  model.py  viz.py
├── scripts/  run_discover.py  run_scrape.py  run_parse.py
│           sample_listings.py  make_spotcheck.py  export_csv.py
├── notebooks/  01_eda  02_features  03_modelling  04_validation
├── models/                      # serialised model + metadata card
├── reports/  figures/  technical-notes.md  findings-deck.pptx
│           spotcheck-fields-*.csv are gitignored: they carry real listing values
├── app/streamlit_app.py
├── notes/
└── project-log/  PLAN.md  STATE.md  BACKLOG.md  decisions/
```

**Data rule.** Raw is immutable and gitignored. Every fetched page is cached to disk keyed
by URL hash, so a rerun costs nothing and the site is never hit twice for the same listing.
Everything downstream regenerates from raw by script.

**Config and secrets.** Scraper parameters in `config/scrape.yaml`, committed. `.env`
gitignored, `.env.example` committed, in case geocoding needs a key.

**Reproducibility.** `git clone` → `uv sync` → `python scripts/run_pipeline.py` reproduces
processed data from raw. Sample data ships so the notebooks run without the full dataset.

---

## 11. Source selection

**Stage 1 work.** Evaluated from scratch; no source is carried over from prior work. Stage 0
closes without a source selected — selecting one is the first activity of the acquisition
stage, and its own chat.

**Division of labour:** Claude produces a shortlist of candidate sites and the specific
clauses and robots.txt paths to check. **Nauman visits the sites and reports what the terms
say.** Claude does not fetch pages to assess terms. If a source disallows automated access,
no scraper is written for it.

**Evaluation criteria:** terms and robots.txt permissiveness; Lahore house listing volume;
whether location arrives structured or as free text; **whether latitude/longitude are
exposed**; whether listing data is server-rendered.

Two criteria added 6 Sep 2026, after both eliminated a candidate the original list would have
passed:

- **Enumerability.** Whether the full inventory can be reached through permitted URLs at all.
  Graana permits its listing pages and publishes no sitemap, and paginates behind a
  disallowed pattern — readable but impossible to enumerate. Check this *before* anything
  else: it is a three-minute test that eliminates a source, and it killed Graana after 20
  minutes had already been spent characterising it.
- **Operational stability.** Repeated site-wide 502s, empty sitemap files, and a "not found"
  template served with HTTP 200 all appeared during evaluation. A multi-day unattended scrape
  depends on the source staying up and on responses meaning what their status code says.

**Self-imposed limits, regardless of source:** 1–2s delay between requests; every page
cached; no `/api/` paths unless the terms cover them; no paid or contact-unlock personal data.

---

## 12. Known risks and limitations

| Risk | Handling |
|---|---|
| Asking price ≠ transaction price | Stated on the front page of the README. The model predicts what a comparable house would be *listed* at, not what it sells for |
| Duplicate listings inflate the sample and leak across the split | Two-pass dedup: exact on listing ID, then fingerprint on locality + area + beds + baths. Groups with ≤15% price spread collapse to the median, carrying `n_listings`; groups above 15% are flagged for review. **Dedup runs before the train/test split** |
| Location is the dominant feature and arrives as messy free text | Coordinates if the source exposes them, accepting that they are often society centroids rather than house-level. Otherwise parse the locality hierarchy and geocode the ~150–250 distinct locality names once into a committed lookup table |
| Volume falls short of target | Floor of 3,000 listings; below that the source is reconsidered rather than the timeline extended |
| Single snapshot, no time dimension | Random split, group-aware on the dedup fingerprint. If listings carry a posting date, a recency holdout is an option to decide at modelling |

---

## 13. Post-handover

**Process review — 0.5d, after 24 Sep.** First project run under this process. Review
against the logged milestone table: what each part of the process cost, what it caught or
prevented, what to cut. Amend the working instructions from the review, not from intuition.
