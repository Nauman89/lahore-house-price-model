# Technical notes

This project predicts what a residential house in Lahore would be listed at, from its size,
location and room counts. Result so far: a lookup table built from the data alone, median
price per marla by locality and size band, prices a held out listing to within **10.62%**
(median absolute percentage error), and the model has to beat that by a tenth before the
project counts as delivered.

Written at the close of stage 3 (EDA), 11 September 2026. Stages 4 to 8 add to it.

## Data

6,468 houses, one row per distinct property, listed between 2 September 2023 and 14 September
2024 on a single Pakistani property portal. They stand for 8,320 original adverts: the rest
were the same property posted more than once, collapsed to one row at the median price so a
single product could not weigh 44 times in the loss.

42 typed columns. Source, licence and collection terms are in the README. Nothing in this
document is a number I did not measure on this dataset.

## What EDA measured, and what each finding decides

| Finding | The number | What it decides | Logged as |
|---|---|---|---|
| The simple baseline is already strong | MdAPE 10.62%, PPE10 48.5%, PPE20 72.6%, with no model in it | The acceptance criteria set at intake were meaningless, so acceptance became relative: 0.90 x baseline, PPE20 at least 75%, 10.0% absolute backstop | D-47, closes B-05 |
| Locality signal stops at the phase | Society 12.24%, society plus phase 11.47%, full path 11.50% | Features encode at society plus phase. The block tier costs 921 levels and buys nothing, with 17% of rows in levels holding under five | D-52 |
| The window is not a cross section | Median price per marla up 14.1% across the twelve months | A recency holdout gains a motive, listing date earns its place as a control, and the README owes the drift as a number | D-55, B-03, B-24 |
| Collapsing duplicates made the metric easier, not harder | Listing level 10.62% against 11.47% on group medians, reversing to 11.76% without the one over represented development | Validation reports the headline, the group figure, the gap and the excluded figure together. The headline alone rewards doing well on one developer's bulk inventory | D-48, B-21 |
| Some duplication cannot be cleaned away | Upper bound 13.03% of rows, and it cannot be narrowed without using price or a house level coordinate | De-duplication stays on the strict key. The split moves to a looser one, so a pair that might be one house cannot straddle train and test | D-60, B-23 |
| Price per marla rises with plot size | 3.60M at five marla or less, 4.40M at 20 to 40 marla | Size cannot be banded without location. The pattern is location confounding, since kanal plots sit in expensive societies | D-59 |
| Error is not flat across the market | 10.90% in the cheapest price quartile, 15.00% in the dearest | Segmented criteria bind rather than inform. Seven segments were fixed before any model existed | D-49, D-50 |
| Nine columns can never be features | Three leak the target, six are unknowable when someone prices an unposted house | The barred list is written once and inherited, and the two grounds stay apart because their remedies differ | D-51 |
| One development dominates the raw adverts | 807 adverts became 253 rows, 9.7% of the sample down to 3.9% | Weighting has far less to correct than expected, though that development's bulk adverts price about 9% below its individual ones | B-22 |
| Three flagged anomalies dissolved | A pricing anomaly was a size mix artefact, nine area conflicts price normally, 25 cheap rows sit in genuinely cheap societies | No further cleaning changes. One upstream fix was warranted and made | D-58, D-59, D-61 |

## What this adds up to

The market prices consistently per marla inside a locality and size band. That is why a lookup
table is already a competent estimator, and it is why the project measures the model against
that table rather than against an absolute error target chosen before anyone saw the data.

## Limitations

Asking price is not transaction price. The model predicts what a comparable house would be
advertised at.

The data stops on 14 September 2024 and prices rose 14.1% across the window it covers, so an
estimate for today extrapolates past the evidence.

One row is a distinct property rather than a single advert, so the prediction is a group's
median asking price, not an individual poster's position in their own price ladder.
