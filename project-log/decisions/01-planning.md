# Decisions — Stage 0: Planning

Append-only. One entry per decision: what, why, what was rejected and why.

---

**D-01 · Brief is a reconstruction, not a client instruction**
The project mirrors two to three Upwork posts seeking residential/commercial listing
scrapers, since expired and not recoverable. Scope expanded from "scraper" to a full
end-to-end ML engagement. Recorded as an assumption so no later reader mistakes it for a
client requirement.

**D-02 · Scope: Lahore, residential houses only**
Flats and apartments excluded — they price on different logic (floor, building,
maintenance), and mixing types would need either a heavily weighted type feature or two
models. Plots excluded — no beds, baths or covered area, so they share almost no feature
space. Upper/lower portions excluded — they are overwhelmingly rented, rarely sold.
Rejected: a broader multi-type model, on the grounds that heterogeneity would cost more
accuracy than the extra volume buys.

**D-03 · Target: total asking price in PKR**
Rejected price-per-marla, which is a different model with a different error profile and
pushes size out of the feature set into the denominator.

**D-04 · Asking price is not transaction price — accepted and disclosed**
No accessible registry or transaction source exists. Listings systematically sit above
achievable value. Accepted as a limitation rather than a blocker, disclosed on the front
page of the README. The model answers "what would a comparable house be listed at", which
is a useful and honest question.

**D-05 · Volume: 10,000 target, 3,000 floor**
High-cardinality locality features need depth per locality. Below roughly 3,000 clean rows
the locality effects get too thin to trust. Floor triggers reconsidering the source, not
extending the timeline.

**D-06 · Presentation layer: notebook charts plus a findings deck. No Power BI in v1**
A client buying a price model wants the model, a way to score new properties, and an
explanation of what drives price. Power BI serves none of those. Its natural use here — a
market-analysis dashboard — is a different product for a different buyer, and a Power BI
dashboard already exists in the portfolio. Rejected for v1, logged as B-02.

**D-07 · Streamlit estimator is a committed deliverable, not a stretch goal**
A non-technical client will click a public link and will not open a repository. The app
converts the work into something a prospect can evaluate in ten seconds. Committed as
stage 8 with a contingency day added behind it so it is not the slip absorber.

**D-08 · Deduplication: two passes, median collapse, before the split**
Listing ID handles exact reposts but misses relists under a new ID and the same house
listed by multiple agents. Second pass fingerprints on locality + area + bedrooms +
bathrooms. Groups whose price spread is within 15% of the median collapse to one row at the
**median** — median not mean, because prices are right-skewed and one agent's fantasy
number should not drag the group. `n_listings` is retained as a feature. Groups above 15%
spread are flagged rather than merged. Dedup runs **before** the train/test split; a
duplicate in train with its twin in test turns validation into a memorisation test.
Threshold is provisional — see B-06.

**D-09 · Acceptance metric: MdAPE headline, PPE10/PPE20 supporting. Provisional until EDA**
Property valuation practice reports median absolute percentage error and percentage-predicted-
within-N, not RMSE. MdAPE is robust to the tail of nonsense listings that scraped asking-price
data carries; PPE20 is the most client-legible number available. Rejected: RMSE in PKR
(dominated by the expensive tail across a 100× price range), MAE in PKR (one rupee figure
across the whole market hides everything), plain MAPE (asymmetric, explodes on cheap
listings). Provisional target MdAPE ≤ 20% / PPE20 ≥ 55%, set without sight of the data and
locked at EDA close. Anchoring to mature AVM benchmarks of 2–8% would be dishonest — those
rest on transaction records and decades of sales history.

**D-10 · Optimisation objective: MAE on log(price)**
Log because price is right-skewed and multiplicative — a 10% error means the same thing at
60 lakh and 6 crore. Absolute rather than squared error because RMSE fits the conditional
*mean* of log price while the acceptance metric is a *median* statistic, and squared error
chases the fat tail of over-priced listings. Rejected RMSE on log price, which was the
initial proposal; kept as a secondary reported diagnostic.

**D-11 · Prediction interval from held-out residual quantiles**
The app shows a range, not a point estimate — a bare number reads as naive. Rejected
training separate quantile-regression models for v1: better calibrated, but roughly a day
against about an hour for residual quantiles. Logged as B-01.

**D-12 · Python 3.13**
Full stack resolved against 3.12, 3.13 and 3.14 targeting Windows, wheels only: pandas,
numpy, scikit-learn, matplotlib, seaborn, xgboost, lightgbm, catboost, shap, optuna,
streamlit, bs4, nltk all available on all three. CatBoost, the historical laggard, now ships
`cp314` Windows wheels. 3.14 rejected anyway: nothing in this stack exploits its features,
Streamlit Community Cloud defaults to 3.12, and the downside is losing a day to some
transitive dependency without a `cp314` wheel. 3.12 rejected as needlessly conservative.

**D-13 · Repo structure and notebook/script split**
Rerunnable work (scraping, cleaning, feature building) lives in `src/lhp/` modules;
narrative work (EDA, modelling, validation) lives in notebooks that import from them.
Scraping never runs in a notebook — a kernel restart loses hours and it cannot run
unattended. Dependencies managed by `pyproject.toml` + `uv.lock` with `requirements.txt`
exported, so a client without uv can still reproduce the environment.

**D-14 · MIT licence for code; data licensed separately**
Permissive, expected on GitHub, and its warranty disclaimer protects against liability for
downstream use. Rejected Apache 2.0 (patent grant and change-notice requirements add
paperwork without benefit here), GPL (copyleft repels commercial clients), and no licence
(legally all-rights-reserved, and reads as unfinished). The licence covers **code only** —
scraped listings are not ours to license. README states the data's terms separately.

**D-15 · Time tracked in days against milestones, not hours**
Mirrors how work will actually be billed: fixed-price milestones, not hourly. Hourly
contracts on Upwork attach an on-screen tracker, which pays for time served rather than work
delivered. Hours survive only inside stopping rules as a guardrail on sub-day activity. A
one-word effort marker (light / as planned / heavy) is recorded at stage close to inform
future quotes, without timing anything.

**D-16 · Delivery Thursday 24 September 2026**
15 working days plus one contingency day. Quote the 24th, target the 23rd. Rejected
compressing the estimate to look competitive: missing a date costs more on Upwork than a
slower quote does. A repeat project of this type, with the scraper and cleaning modules
already written, should quote 8–10 days.

**D-17 · Source selection deferred and reopened from scratch**
No source carried over from prior work. Claude supplies the shortlist and the specific
clauses and robots.txt paths to check; Nauman visits the sites and reports the findings.
Claude does not fetch pages to assess terms — that reading is not a legal judgement, and a
site prohibiting automated access should not be accessed to check. Evaluation criteria:
terms permissiveness, Lahore house volume, structured versus free-text location, whether
latitude/longitude are exposed, and whether listing data is server-rendered. Self-imposed
limits apply regardless of source: 1–2s request delay, cache every page, no `/api/` paths
unless the terms cover them, no paid or contact-unlock personal data.

**D-18 · Dependency set declared upfront, resolved once**
All shipped dependencies — acquisition, data, modelling, presentation — are declared in
`pyproject.toml` at stage 0 and locked in one resolution, rather than added stage by stage.
Rejected incremental installation: it invites a mid-project resolution conflict at the worst
moment, and the lockfile is the reproducibility guarantee the client is being handed.
Notebook tooling (`ipykernel`, `jupyterlab`) and the linter (`ruff`) sit in a `dev` group so
they do not appear in the client's runtime requirements. `ruff` is configured to enforce the
docstring convention rather than relying on discipline. NLTK is omitted — no text modelling
is planned; it is added only if listing descriptions enter the feature set.

**D-19 · Line endings normalised via .gitattributes**
Development is on Windows, deployment (Streamlit Community Cloud) is on Linux. `* text=auto
eol=lf` prevents a diff full of line-ending churn and prevents CRLF from reaching the
deployed app.
