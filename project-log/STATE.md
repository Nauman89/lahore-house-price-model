# STATE

**Updated:** 11 Sep 2026

**Active stage:** 3 — EDA · **COMPLETE**, milestone Mon 14 Sep met three days early
**Next stage:** 4 — Feature engineering (milestone Tue 15 Sep). Runs in its own chat.

## Outcome

The acceptance criteria are locked (B-05 closed), and the number that locks them is the
stage's main finding: **PLAN §5.1's own baseline scores MdAPE 10.62%** with no model in it,
which beats the provisional accept level of 20%, the PPE20 floor of 55%, and the 15% stretch,
all three, before anything is trained.

`notebooks/01_eda.ipynb`, 36 cells, runs clean top to bottom and imports from `src/lhp/viz.py`.

### Exit criteria

| Criterion | Result |
|---|---|
| Acceptance criteria locked and logged | D-47 levels, D-49 segment rule, D-50 segment definitions, all in `decisions/04-eda.md` |
| Every column's distribution reviewed | All 42 profiled mechanically (D-54), each carrying an explicit disposition |
| Every anomaly explained or logged in BACKLOG | B-18 fixed upstream (D-58), B-19 dissolved (D-59), B-20 reviewed (D-61), B-22 corrected, D-44's soft boundary confirmed (D-61) |
| Leakage risks identified | D-51 bars nine columns on two distinct grounds; D-60 bounds the residual at 13.03% and gives the split rule that neutralises it |
| Findings written and ready to drive feature choices | 13 candidate columns, the locality tier measured, the time drift measured |
| STATE, BACKLOG and decisions updated; repo pushed and tagged | this file; 4 backlog items closed, 2 rewritten, 2 opened; `v0.3-eda` |
| Handoff written for the stage 4 chat | `handoffs/04-features.md` |

### The six findings that matter

1. **The baseline is strong and the provisional criteria were meaningless.** Median price per
   marla by locality tier and size band, out of fold: MdAPE 10.62%, PPE10 48.5%, PPE20 72.6%
   on the D-48 metric. Accept is now relative, at 0.90 x baseline (D-47).
2. **The locality tier is society plus phase.** Society alone scores 12.24%, society plus
   phase 11.47%, the full path down to block 11.50%, which is marginally worse while more
   than doubling the levels and putting 17% of rows in levels holding under five. The block
   tier is memorisation dressed as granularity.
3. **The twelve-month window is not a cross-section.** Median price per marla rose 14.1% from
   the first complete month to the last, the same order as the baseline's own error. B-03's
   recency holdout now has a motive, and the README's extrapolation risk has a number (B-24).
4. **B-21's collapse gap runs the opposite way to the assumption.** Listing-level scoring
   gives 10.62% against 11.47% on group medians, because weighting by listing over-weights
   the replicated groups and those are the easiest rows in the corpus. It reverses to 11.76%
   once Park View Villas is excluded, which is why D-48 requires that figure beside the
   headline.
5. **Residual leakage is bounded at 13.03% of rows and cannot be narrowed** without using
   price (barred, D-38) or a house-level coordinate (does not exist). The mitigation is a
   split-time rule, not a cleaning rule: dedup on the tight key, split on a loose one (D-60,
   B-23).
6. **Price per marla rises with plot size**, 3.60M at five marla or less to 4.40M at 20 to 40,
   which is the opposite of the usual small-plot premium and is almost certainly location
   confounding. Size cannot be banded without location.

## What changed against the plan

| Set at intake | Measured | Where |
|---|---|---|
| Accept MdAPE <= 20% and PPE20 >= 55%, stretch 15% | All three beaten by a lookup table before any model exists | D-47 |
| B-21: scoring on group medians will understate the error | It overstates it. Listing-level is 0.85 points *better*, and only reverses with Park View Villas removed | D-48 |
| PLAN §3: twelve months is close enough to a cross-section | 14.1% drift across the window | D-55 |
| B-22: Park View City is the largest single society | Labelled Park View Villas, and largest *development* only once DHA is split into its phases. 9.7% of listings, 3.9% of rows | B-22 |
| B-19: Rahbar prices above DHA main phases, direction wrong | A size-mix artefact. At five marla it is 4.50M against the main phases at 4.91M | D-59 |
| B-20: ten unresolvable area conflicts | Nine reach the analysis set, and they price indistinguishably from the corpus | D-61 |

## Files added or amended this stage

```
src/lhp/viz.py                     house style: palette, chrome, PKR formatting, figure saving
notebooks/01_eda.ipynb             the stage's narrative, 36 cells
reports/figures/03..07             five figures, deck resolution
project-log/decisions/04-eda.md    D-47 to D-61
src/lhp/clean.py                   amended: D-53 members artefact, D-58 Rahbar mapping
scripts/run_clean.py               amended: emits listings_members
tests/test_clean.py                169 tests, up from 160
data/processed/listings_members.*  new artefact, 8,320 pre-collapse listings
```

## Next action

Open the stage 4 chat. Read `handoffs/04-features.md`, then `decisions/04-eda.md`, then
BACKLOG B-21 through B-24. **The tier, the split key and `created_at` are the three decisions
stage 4 and stage 5 inherit as evidence rather than as instructions (D-52).**

## Blockers

None. Stage 4 is unblocked and unstarted.

## Known gaps

- `created_at` is undecided: usable at inference only as "today", which is outside the window,
  against a 14.1% drift. D-51 leaves it to stage 4 deliberately.
- The 13.03% residual leakage bound cannot be reduced with the data available. B-23 carries
  the split rule that makes it harmless.
- B-21's disclosure obligations fall due at stage 6, and B-24's README number at stage 7.
- Park View Villas bulk postings price about 9% below its singleton listings, not yet
  controlled for size or block. A stage 5 weighting question. B-22.
