Stage 5 · Modelling. Lahore House Price Model.

Read first: CLAUDE.md at the repository root, then project-log/PLAN.md, STATE.md, BACKLOG.md,
and all five decision files, decisions/01-planning.md to decisions/05-features.md. The two that
bind this stage hardest are 04-eda.md (D-47 to D-61: the acceptance criteria, the metric, the
segments, the split rule) and 05-features.md (D-62 to D-67: what the model gets).

CLAUDE.md holds the writing rules, the attribution convention and the working constraints, and
wins wherever this handoff disagrees with it. Read it even if your tooling claims to have
loaded it.

Stage 4 complete in one day, milestone Tue 15 Sep met early. Tag v0.4-features.

FIRST, DECIDE WHERE THIS STAGE RUNS
Stage 5 needs LightGBM, CatBoost, XGBoost, Optuna, SHAP and pyarrow. On 11 Sep the Cowork cloud
workspace could install none of them: every package registry answered 403 "Host not in
allowlist", with network egress on and pypi.org explicitly allowed in Settings > Capabilities.
It may have been that one session.
- In a Cowork session, first run: curl -sS -o /dev/null -w "%{http_code}" https://pypi.org/simple/pip/
  200 means packages can be installed; work as normal, verifying code in the workspace before
  I run it.
- 403 means they cannot. Then run stage 5 in Claude Code on my laptop, which uses the project
  .venv directly and can run the models itself. Say which, and why, before writing any code.
The desktop bridge's shell is also broken on this laptop (a Windows update released 8 Sep).
Listing, staging and writing files still work.

WHAT YOU ARE STARTING FROM
- data/processed/listings.parquet: 6,468 rows, one per fingerprint group, 42 typed columns,
  listed 2 Sep 2023 to 14 Sep 2024. Read it with lhp.clean.read_processed, which re-applies the
  schema.
- data/processed/listings_members.parquet: the 8,320 pre-collapse listings, at the price each
  poster set. D-48's headline is scored against these, not against the analysis rows. It joins
  on fp_group_id, which is positional and renumbers on every run: both files must come from the
  same run of scripts/run_clean.py (D-53).
- src/lhp/features.py: FeatureBuilder builds the nine-column matrix. Inside each outer
  training fold:
      builder = FeatureBuilder()
      X_train = builder.fit_transform(train_rows, groups=<B-23 loose key for train_rows>)
      X_valid = builder.transform(valid_rows)
  and for the estimator, builder.transform(house, pin_to_window_end=True).
- notebooks/02_features.ipynb: the evidence behind every feature.
- 208 tests pass. uv run pytest.

WORKING CONSTRAINTS (from CLAUDE.md, restated because they cost time when missed)
- Never create scratch or test files in the project folder; the bridge cannot delete them.
- Never run git commands that write to the index, including git status. Hand me anything that
  stages, commits, tags or pushes as a PowerShell block.
- I run every command. You write code, I make the decisions and I must understand every line.
- A tool reporting a successful write is not evidence the file changed. Verify by checksum.
- project-log/LESSONS.md is gitignored and personal. Keep appending; we triage at project close.

EXIT CRITERIA (PLAN §6)
- Baseline established first: the §5.1 lookup (median price per marla by society plus phase
  and size band) re-run on the current artefact and the stage 5 split. D-47's thresholds are
  relative, so accept becomes 0.90 x this number, with PPE20 at least 75% and a 10.0% absolute
  backstop.
- Model choice justified against at least one alternative
- The split is group-aware on the loose key (B-23, D-60)
- STATE, BACKLOG and decisions/06-modelling.md updated; repo pushed and tagged v0.5-modelling

STOPPING RULE (PLAN §8)
Tuning: 60 Optuna trials per model, or 3 hours in total, or no improvement in the best trial
across 20 consecutive trials, whichever comes first.

THE DECISIONS WAITING FOR YOU (evidence exists; the choice is this stage's, per D-52)
1. THE LOOSE SPLIT KEY (B-23, high). D-60 specifies coordinates, rooms and rounded area,
   ignoring loc_path. Still open: the rounding of area, and a rule for the 62 analysis rows
   with no usable coordinate (D-33; they are not imputed and must not be). The same key is the
   groups argument to FeatureBuilder.fit_transform, so one definition serves both.
2. RANDOM GROUP-AWARE SPLIT OR RECENCY HOLDOUT (B-03, medium). D-55 measured the drift; D-64
   found it tangled with a shift in what was listed. A recency holdout tests exactly what the
   estimator does, pricing dates past the training data, which D-64 records as evidence.
3. THE TARGET'S FORM. Log price directly (D-10, objective MAE on log price) or a correction to
   lookup_log_price (D-65). The feature makes either possible.
4. LOCALITY HANDLING. The D-62 encoding against CatBoost's native handling of the locality
   label. The smoothing strength m defaults to 20 and is tuned inside cross-validation.
5. PARK VIEW VILLAS WEIGHTING (B-22, low). Its bulk postings price about 9% below its singleton
   listings, so down-weighting them is not obviously free.

WHAT STAGE 4 FOUND THAT BEARS ON STAGE 5
- A code sanity check, not a result: the lookup estimate alone, on an 80/20 split with one
  group per row, scored MdAPE 13.96% on 1,345 held-out rows (PPE20 62.9%). It is worse than
  the baseline's 11.47% on group medians because it has no size dimension. Do not use it as a
  benchmark; the baseline is re-established on the stage 5 split.
- D-47's 10.62% was measured before D-63 moved one row (property 579334, now DHA Phase 6).
- Types the models need: locality to category for LightGBM (CatBoost takes strings);
  bedrooms and bathrooms from pandas' nullable Int64 to float.
- The 62 missing coordinates stay missing; tree models route them natively.

WATCH OUT FOR
- fit_transform on training rows, never fit followed by transform on the same rows. The second
  gives in-sample encodings; a test pins the difference.
- Refit FeatureBuilder inside every fold, including the inner folds Optuna tunes on. An
  encoder fitted outside the tuning loop leaks the validation fold's prices into training.
- Whether a feature contributes is this stage's question, answered by SHAP and ablation against
  the baseline. Stage 4 only asked whether each is justified by evidence.
- The segment definitions are locked (D-50). Do not re-cut them after seeing results.
- Do not settle a modelling choice by which answer makes the target look best on the test
  fold. Choose on the validation folds, then score the test fold once.
- No listing rows in notebook outputs (D-23). Every count bounded where it is computed (L-26).

OPEN BACKLOG FOR THIS STAGE AND AFTER
B-23 loose split key (high, stage 5) · B-03 recency holdout (medium, stage 5) · B-22 Park View
Villas weighting (low, stage 5) · B-21 collapse disclosure (high, stage 6) · B-24 README drift
number (medium, stage 7) · B-25 unresolved description pointers (low, only if text is used) ·
B-26 long lines in 01_eda.ipynb (low, stage 7)

STAGE CLOSE CHECKS (added at stage 4, LESSONS L-32)
- uv run pytest
- uv run ruff check src tests scripts notebooks/02_features.ipynb, over everything, not only
  the files touched. 01_eda.ipynb joins the list after B-26 is fixed in stage 7. Add any new
  notebook to the list.
- uv run python scripts/check_prose.py: the client facing count must not rise above 52
- every notebook runs top to bottom
