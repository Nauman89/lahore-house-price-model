# STATE

**Updated:** 11 Sep 2026

**Active stage:** 4 · Feature engineering · **COMPLETE**, in one day, milestone Tue 15 Sep met early
**Next stage:** 5 · Modelling (milestone Thu 17 Sep). Runs in its own chat.

## Outcome

The model's input is **nine columns**: five carried raw (`area_marla`, `bedrooms`, `bathrooms`,
`latitude_clean`, `longitude_clean`), the society plus phase label, and **three engineered
features** against PLAN §8's ceiling of 30: the smoothed locality encoding (D-62), months since
the window opened (D-64) and the lookup estimate (D-65). All thirteen D-51 candidates were
decided; five were dropped (`loc_phase_num`, `loc_sector`, `loc_block`, `loc_sub`, `loc_path`).

`src/lhp/features.py` builds the matrix; stage 5, stage 6 and the estimator share it. No
price-derived value is written to disk: the encoding is fitted inside each training fold, out of
fold for training rows, grouped so a possible duplicate pair never sees its twin's price.
`notebooks/02_features.ipynb`, 8 code cells, rebuilds the evidence behind D-62 to D-67 and runs
clean top to bottom.

### Exit criteria

| Criterion | Result |
|---|---|
| Every feature traced to an EDA finding | Each of the nine columns names its decision and finding (D-62 to D-66; notebook section 1) |
| Leakage checked explicitly | Import-time guard against every D-51 barred column; tests fill barred columns with random values and scramble price, and the matrix does not move; `transform` never reads price |
| Definitional relationships verified | Smoothing checked against a hand computation; lookup estimate equals encoding plus log area; a row's own price never enters its training encoding; rows sharing a group never encode each other. Seven deliberate breaks of `features.py`, each caught by its test |
| STATE, BACKLOG and decisions updated; repo pushed and tagged | this file; B-24 amended, B-25 and B-26 opened; `decisions/05-features.md` D-62 to D-67; `v0.4-features` |

### The findings that matter

1. **EDA's 14.1% drift is tangled with a change in mix** (D-64). The two months that bound it,
   Oct 2023 and Aug 2024, differ most in what was listed: DHA 6.1% of rows against 32.3%, plots
   of a kanal or more 16.5% against 37.3%. Both price higher per marla. Time therefore enters as
   a control, held at the training data's latest date for the estimator, and the README must
   report the drift the model attributes to time rather than the raw 14.1% (B-24, amended).
2. **Locality is encoded, not one-hot or native**, at society plus phase: 442 levels over 6,468
   rows, 359 of them under 20 rows. Smoothing (m = 20, tuned in stage 5) lets a thin level
   borrow its society's value; coordinates let it borrow its neighbours'.
3. **The text columns hold almost nothing** (D-67). Descriptions are empty at source on 98.2%;
   titles follow one template on 94.0%; the commonest candidate signal covers 0.5% of rows.
4. **Two upstream defects, handled two ways.** Property 579334 had no society because its
   address was one segment; a parser rule now recovers it and exactly one row changed on the
   re-run (D-63). Eleven descriptions hold an unresolved page-data pointer; logged, not fixed,
   because nothing reads the column (B-25).

## What changed against the plan

| Set at intake or handed over | Measured | Where |
|---|---|---|
| 14.1% drift, to be disclosed in the README (B-24) | Tangled with a shift in what was listed; stage 7 reports the model's time effect instead | D-64 |
| 97 rows with no usable coordinate (stage 4 handoff) | 62 analysis rows, standing for 91 of 8,320 listings | D-62 |
| 443 society plus phase levels (D-50) | 442 named; the 443rd was the one row without a society, now absorbed | D-62, D-63 |
| `created_at` unresolved (D-51) | A control, pinned at the window's end for the estimator | D-64 |
| PLAN §10 lists `notebooks/02_features` | Built, after the evidence was first measured in scratch code (LESSONS L-29) | this stage |

## Files added or amended

```
src/lhp/features.py                 LocalityEncoder and FeatureBuilder (D-62 to D-66)
tests/test_features.py              30 tests: leakage and definitional relationships
notebooks/02_features.ipynb         the stage's evidence, 8 code cells
reports/figures/08-listing-mix-by-month.png
src/lhp/clean.py                    amended: D-63 society recovery from the address
tests/test_clean.py                 9 tests added; the suite is 208, up from 169
reports/stage2-reconciliation.md    regenerated: D-63's counts
src/lhp/viz.py                      bold titles (semibold printed a findfont warning); 3 lint fixes
src/lhp/__init__.py, scrape/__init__.py   docstrings
tests/*.py, scripts/*.py            import order fixed by ruff --fix (8 files, no logic change)
scripts/check_prose.py              02_features added to the client facing list
project-log/decisions/05-features.md  D-62 to D-67
project-log/BACKLOG.md              B-24 amended, B-25 and B-26 opened
project-log/handoffs/05-modelling.md
```

## Next action

Open the stage 5 chat. Read `handoffs/05-modelling.md` first: its first step is deciding where
stage 5 runs, because the Cowork workspace cannot install LightGBM or CatBoost (see Known gaps).

## Blockers

None in the project. Tooling, both found 11 Sep:

- The desktop bridge's shell is broken on this laptop by a Windows update released 8 Sep; the
  tool reports the cause itself. File listing, staging and writing still work, so every write
  is verified by re-staging and comparing checksums.
- The Cowork cloud workspace refuses package registries ("Host not in allowlist: pypi.org")
  even with network egress on and pypi.org added to the allowlist. Untested whether a new
  session honours the setting.

## Known gaps

- B-23's loose split key is specified in words (D-60) but not yet defined; the 62 rows without
  a coordinate need a rule inside it.
- The D-47 baseline, 10.62%, was measured before D-63 moved one row; stage 5 re-establishes it
  first in any case (PLAN §6).
- B-21's disclosure obligations fall due at stage 6, and B-24's README number at stage 7.
- Park View Villas bulk postings price about 9% below its singleton listings (B-22), a stage 5
  weighting question.
- `01_eda.ipynb` has 17 over-long code lines (B-26), deferred to the stage 7 notebook pass.
  Everything else lints clean.
