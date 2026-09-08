Stage 2 — Cleaning. Lahore House Price Model.

Read first: project-log/PLAN.md, STATE.md, BACKLOG.md, decisions/01-planning.md,
decisions/02-acquisition.md, notes/source-evaluation.md.

Stage 1 complete, milestone met one day early. Tagged v0.1-acquisition, pushed to
github.com/Nauman89/lahore-house-price-model, branch main.

WHAT YOU ARE STARTING FROM
8,459 in-scope Lahore houses for sale, listed 2 Sep 2023 – 14 Sep 2024, in
data/interim/listings.jsonl (8,991 rows including 532 flagged out of scope with reasons —
they are present deliberately, not left behind). data/raw/cache holds ~9,000 gzipped pages;
anything we failed to parse is recoverable from there without re-scraping. Coverage 99.89%,
field accuracy 99.17% on a 30-listing manual audit. Every field except price (99.7%), area
(99.8%) and coordinates (99.6%) is 100% complete.

WORKING CONSTRAINTS — read these before running anything
- You reach my machine through a bridge that cannot delete files. Never create scratch or
  test files in the project folder; I have to remove them by hand.
- Never run git commands that write to the index, INCLUDING git status — a stale
  .git/index.lock blocks my own git. Read-only git (log, ls-files, check-ignore, show) is
  fine. Hand me anything that stages, commits, tags or pushes as a PowerShell block.
- I run every command myself. You write code, I make the decisions and I need to understand
  what ships.
- project-log/LESSONS.md is gitignored and personal. Keep appending process lessons to it;
  we triage them at project close.

WHAT STAGE 2 DOES
Turn data/interim/listings.jsonl into an analysis-ready table. Modules in src/lhp/clean.py,
rerunnable from raw, raw never modified.

EXIT CRITERIA (PLAN §6)
- Every transformation justified and logged
- Row counts reconciled before and after every merge; no silent drops
- Dedup rule applied and its effect quantified
- Raw data untouched
- STATE, BACKLOG and decisions updated; repo pushed and tagged v0.2-cleaning
- Handoff written for the stage 3 chat

STOPPING RULE
2 days, or flagged near-duplicate groups below 5% of rows, whichever comes first.
Milestone Thu 10 Sep. Timeline unchanged.

DO THESE IN THIS ORDER — the first one changes the others
1. B-15 — area_unit is wrong on 18 rows and the title says so. "2 Kanal House" carries
   area=2, area_unit=marla. Parse the unit from the title, prefer it on disagreement, log
   every correction. Do this FIRST: it removes the extreme price-per-marla outliers, so
   B-09's junk list can only be derived afterwards.
2. B-12 — convert everything to marla (1 kanal = 20, 1 marla = 225 sqft = 25 sqyd; confirm
   the sqft factor). Add area_marla as a NEW column; never overwrite area or area_unit.
3. B-09 — then find the residual junk. PKR 53,000 for a 10-marla house, PKR 20,000 for a
   503 sqft listing. Price per marla is the detector: the bulk sits 3.1M–4.3M.
4. B-08 — decompose locality. "DHA" is 1,277 rows with no phase, and Phase 6 medians
   5.65M/marla against Phase 1 at 3.50M — a 61% spread inside one categorical value. Phase
   is in address on 1,265 of them, Block on 670, plus EME (96) and Rahbar (17). Treat the 17
   Rahbar rows with suspicion; they price like main-phase DHA, which is not typical.
5. B-16 — 10 penthouses carry type="House" at source. D-02 excludes apartments. Title-based
   filter. Checked: no flats, portions, plots, shops or farmhouses leak.
6. B-07 — THE BIG ONE. D-08's dedup fingerprint (locality + area + beds + baths) puts 75.9%
   of rows into multi-listing groups, because locality is coarse. Applying it as written
   would merge genuinely different houses. Coordinates are on 99.6% of rows (B-04 closed) —
   rebuild the fingerprint around them. This amends D-08; log it.
7. B-06 — only after B-07. The 15% price-spread threshold cannot be judged until the
   fingerprint is right.
8. B-13 — drop zero-variance columns (condition, year_built, is_verified, is_gold_verified,
   is_sold, is_featured, has_video). Do NOT drop views or image_count; they vary and go to
   EDA. Principle: drop on zero variance, which is mechanical; every other column decision
   belongs to stage 4 after EDA has looked.
9. B-10 — three locality spelling variants: Al Kabir/Al-Kabir Orchard, Sher Shah/Shershah
   Colony, High Court/Highcourt Society. Otherwise the vocabulary is clean, 387 values.
10. D-23 — generate data/sample/ as SYNTHETIC rows matching the real schema. Ilaan publishes
    no licence; we do not redistribute their listings. Notebooks must still run from a clean
    checkout. Also: no verbatim listing rows anywhere public — including notebook cell
    outputs, which store what they printed.

CARRY FORWARD
- created_at must survive cleaning. PLAN §3 was amended: this is a 12-month window, not a
  snapshot, and listing date is a control at modelling. B-03's recency holdout is live.
- amenities is empty on every row and description is populated on ~8%. Neither is a feature.
- Price per marla in the bulk is tight (p25 3.02M, median 3.57M, p75 4.21M). If that holds,
  the PLAN §5.1 baseline — median price-per-marla by locality × size band — may be hard to
  beat. That is a finding, not a failure, and D-06 already anticipates reporting it. Worth
  raising when acceptance criteria are locked at EDA close (B-05).

WATCH OUT FOR
- A value that looks wrong on one row is often a column that is wrong on every row. Check the
  distribution before theorising about the row. That is how year_built was caught.
- Do not drop rows silently. Flag with a reason, count, and reconcile. The 532 out-of-scope
  rows are already carried this way; keep the pattern.
