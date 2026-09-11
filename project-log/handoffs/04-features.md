Stage 4 — Feature engineering. Lahore House Price Model.

Read first: project-log/PLAN.md, STATE.md, BACKLOG.md, decisions/01-planning.md,
decisions/02-acquisition.md, decisions/03-cleaning.md, decisions/04-eda.md.

Stage 3 complete, milestone met three days early. Tag v0.3-eda.

WHAT YOU ARE STARTING FROM
6,468 Lahore houses in data/processed/listings.parquet, one row per fingerprint group, listed
2 Sep 2023 to 14 Sep 2024, 42 typed columns. Beside it, data/processed/listings_members.parquet
holds the 8,320 pre-collapse listings each row stood for, at the price each poster actually set
(D-53). Stage 6 scores against that file, not against the analysis set, so do not lose it.

Regenerate everything with: python scripts/run_clean.py
The EDA narrative is notebooks/01_eda.ipynb and it imports from src/lhp/viz.py.

WORKING CONSTRAINTS — read these before running anything
- You reach my machine through a bridge that cannot delete files. Never create scratch or
  test files in the project folder; I have to remove them by hand.
- Never run git commands that write to the index, INCLUDING git status — a stale
  .git/index.lock blocks my own git. Read-only git (log, ls-files, check-ignore, show) is
  fine. Hand me anything that stages, commits, tags or pushes as a PowerShell block.
- I run every command myself. You write code, I make the decisions and I need to understand
  what ships.
- A tool reporting a successful file write is not evidence the file changed. Verify with a
  checksum before asking me to run anything against it. This cost us a wasted test run on
  8 Sep.
- project-log/LESSONS.md is gitignored and personal. Keep appending process lessons to it;
  we triage them at project close.

WHAT STAGE 4 DOES
Turn EDA's evidence into features. Stage 3 measured and deliberately chose nothing (D-52), so
every choice below is yours to make and log in decisions/05-features.md.

EXIT CRITERIA (PLAN §6)
- Every feature traced to an EDA finding
- Leakage checked explicitly
- Definitional relationships verified
- STATE, BACKLOG and decisions updated; repo pushed and tagged v0.4-features

STOPPING RULE
30 engineered features or 1.5 days, whichever comes first. PLAN §8.

THE THREE DECISIONS WAITING FOR YOU
1. THE LOCALITY TIER. Society scores MdAPE 12.24% on the §5.1 baseline, society plus phase
   11.47%, the full path 11.50%. Phase is where the signal stops: the block tier is marginally
   worse while more than doubling the levels and putting 17% of rows into levels holding under
   five rows. High cardinality is the real question here, not which number is smallest. 443
   levels against 6,468 rows means any target encoding needs out-of-fold fitting or it will
   memorise.
2. `created_at`. The one column D-51 left unresolved. It is knowable at inference only as
   "today", which sits outside the window, and the window carries a 14.1% drift. As a feature
   it extrapolates a trend; held fixed at the window's end it ignores one. PLAN §3 anticipated
   it as a control. Decide, and log the reasoning.
3. SIZE BANDING. Price per marla RISES with plot size across the city, 3.60M at five marla or
   less to 4.40M at 20 to 40 marla. That is the opposite of the usual small-plot premium and
   is almost certainly location confounding, since kanal plots sit in expensive societies. Do
   not band size without location. The §5.1 baseline already crosses the two.

WHAT YOU MAY NOT USE, AND WHY (D-51)
Nine columns are barred on two distinct grounds, and the grounds are not interchangeable.
- Leakage, barred forever: price_listed, fp_price_median, fp_price_spread.
- Unavailable at inference, barred because of what we are building: n_listings, collapsed,
  views, image_count, is_featured, has_video. PLAN §2's deliverable is an app a person types
  an unposted house into; none of these exist at that moment.
Eleven audit columns and six superseded source columns are never modelled either. title and
description are text sources, not features: they may yield features by extraction, and whether
that earns its cost is your call. Thirteen candidates go forward, listed in D-51.

WHAT EDA FOUND THAT BEARS ON STAGE 4
- The baseline is strong. MdAPE 10.62% on the D-48 metric, PPE20 72.6%, with no model in it.
  The locked accept level is 0.90 x baseline (D-47), so features have to earn a tenth of the
  error, not a rounding difference. If gradient boosting adds little over the lookup, that is
  the finding and D-06 already commits to reporting it.
- Error is not flat. 10.90% MdAPE in the cheapest price quartile, 15.00% in the dearest. The
  expensive end is roughly 60% harder and the segment definitions are locked in D-50.
- Residual leakage is bounded at 13.03% of rows, and the fix belongs to the SPLIT, not to
  features or cleaning: dedup on the tight fingerprint, split on a loose key that ignores
  loc_path (D-60, B-23). Do not tighten the fingerprint to chase it.
- 97 rows carry no usable coordinate (D-33). They are not imputed and must not be.
- DHA Rahbar is now DHA Phase 11 with its internal phase in loc_sub (D-58). clean.
  SUB_SOCIETY_PHASES is the place to add another sub-society if one turns up.

OPEN BACKLOG FOR THIS STAGE AND THE NEXT
B-23 loose split key (high, stage 5) · B-21 collapse disclosure (high, stage 6) · B-03 recency
holdout (medium, stage 5) · B-22 Park View Villas weighting (low, stage 5) · B-24 README drift
number (medium, stage 7)

WATCH OUT FOR
- A finer key always looks better inside the sample and stops looking better outside it. The
  full-path tier is the worked example: it wins on nothing and costs support.
- Do not settle a question about a feature by checking which answer makes the target look
  better. That is D-38's objection, and it is easier to breach here than at cleaning.
- Verify every derived statistic the way the data is verified. A count cannot exceed the rows
  and a percentage cannot exceed 100, and the assertion goes in the expression that computes
  it. LESSONS L-26, and it fired again in stage 3 when a null group key silently dropped 265
  rows from a table.
- No verbatim listing rows anywhere public, including notebook cell outputs, which store what
  they printed. data/sample/ is synthetic for the same reason (D-23).
