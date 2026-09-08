Stage 3 — EDA. Lahore House Price Model.

Read first: project-log/PLAN.md, STATE.md, BACKLOG.md, decisions/01-planning.md,
decisions/02-acquisition.md, decisions/03-cleaning.md.

Stage 2 complete, milestone met two days early. Tag v0.2-cleaning.

WHAT YOU ARE STARTING FROM
6,468 Lahore houses in data/processed/listings.parquet, one row per distinct property
fingerprint, listed 2 Sep 2023 – 14 Sep 2024. 40 columns, every one typed by a declared
schema (D-39) — created_at is a real datetime, counts are nullable Int64, low-cardinality
strings are categories. 139 excluded rows sit in listings_excluded.parquet with a reason
each; they are there deliberately, not left behind.

Regenerate everything with: python scripts/run_clean.py

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

WHAT STAGE 3 DOES
Understand the data well enough to lock the acceptance criteria and drive feature choices.
Notebook narrative (notebooks/01_eda), importing from src/lhp/. Plot styling belongs in
src/lhp/viz.py, which does not exist yet.

EXIT CRITERIA (PLAN §6)
- Acceptance criteria LOCKED and logged in decisions/04-eda.md
- Every column's distribution reviewed
- Every anomaly explained or logged in BACKLOG
- Leakage risks identified
- Findings written and ready to drive feature choices
- STATE, BACKLOG and decisions updated; repo pushed and tagged v0.3-eda

STOPPING RULE
2 days. Milestone Mon 14 Sep. Timeline unchanged.

THE TWO THINGS THAT MUST NOT BE MISSED
1. B-05 — lock the acceptance criteria. Provisional since 2 Sep: MdAPE <= 20%, PPE20 >= 55%,
   set without sight of the data. They must not reach validation unlocked.
2. B-21 — the held-out set is made of GROUP MEDIANS. D-45 collapsed 1,852 rows into their
   fingerprints, so MdAPE will not include the within-group price variation no model can
   resolve: median 3.23%, p75 7.26%, p90 13.9% on the rows that had replication. Every row
   carries n_listings and fp_price_spread so this can be quantified rather than asserted.
   Whatever number gets locked in B-05 has to be honest about what it is measured on, and
   the README limitation must say the model predicts a group's median asking price, not an
   individual poster's position in their own ladder.

WHAT THE CLEANING FOUND THAT BEARS ON EDA
- Price per marla is tight: p25 3.10M, median 3.70M, p75 4.50M. The PLAN §5.1 baseline —
  median price-per-marla by locality x size band — may be hard to beat. That is a finding,
  not a failure; D-06 anticipates reporting it, and it is worth raising when B-05 is locked.
- Locality now decomposes (D-40): loc_society (378), loc_phase, loc_sector, loc_block,
  loc_path (926 distinct). DHA phase medians run 3.50M/marla (Phase 1) to 5.64M (Phase 6) —
  a 61% spread that was invisible inside one categorical value. Which tier carries signal is
  an EDA question; cleaning deliberately chose none.
- created_at survives and is a real datetime. B-03's recency holdout is live and decidable.
- 97 rows carry no usable coordinate (D-33). They are not imputed and must not be.
- Ilaan's payload area is a measured figure and its title is the rounded one (D-32). 8.8% of
  areas are fractional. This bears on any size banding.

OPEN BACKLOG FOR THIS STAGE
B-05 acceptance criteria (high) · B-21 collapsed holdout (high) · B-18 DHA Rahbar labelling ·
B-19 Rahbar prices like a main phase and should not · B-20 10 unresolvable area conflicts ·
B-22 Park View City over-represented

WATCH OUT FOR
- A value that looks wrong on one row is often a column that is wrong on every row. Check the
  distribution before theorising about the row.
- But do not theorise about a column from a printout you formatted yourself either. Stage 2
  characterised a rounding defect from a table printed to zero decimal places and got the
  direction backwards; the claim was in a decision entry before anyone checked it against
  the column. LESSONS L-25.
- Effort goes on classifying whether a defect is column-level or row-level. Once it is known
  to be row-level and under roughly 0.5% of the sample, flag, exclude and stop. LESSONS L-24.
- No verbatim listing rows anywhere public, including notebook cell outputs, which store what
  they printed. data/sample/ is synthetic for the same reason (D-23).
