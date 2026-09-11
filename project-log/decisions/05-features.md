# Decisions, Stage 4: Feature engineering

Append-only. One entry per decision: what, why, what was rejected and why.
Entries are stubbed when the decision is taken and prose-edited at stage close (LESSONS L-23).

Every feature names the EDA finding it traces to. A candidate that no finding points at is not
built, and finishing well under the 30-feature ceiling of PLAN §8 is a clean pass.

---

**D-62 · Locality enters as society plus phase, through a smoothed target encoding fitted inside
stage 5's folds, alongside raw coordinates. `loc_phase_num` is dropped**

Approved 11 Sep 2026.

*The tier.* Society plus phase. On the §5.1 baseline, society alone scores MdAPE 12.24%, society
plus phase 11.47%, and the full path to block 11.50% (STATE, finding 2). The full path is no
better and more than doubles the levels. A row without a phase takes its society alone as its
level. `loc_sector`, `loc_block`, `loc_sub` and `loc_path` are not features.

Measured on the analysis set, 11 Sep 2026, 6,468 rows:

| levels holding | levels | rows |
|---|---|---|
| 100 or more | 11 | |
| 20 to 99 | 72 | |
| under 20 | 359 | |
| of which under 5 | 246 | 419 (6.5%) |
| **named levels** | **442** | |

D-50 counts 443. The difference is one row with no society, below. Normalising every level to
lowercase alphanumerics still leaves 442, so no level is split by case or punctuation.

*`loc_phase_num` is dropped.* Nothing in EDA supports treating phase numbers as ordered, and
D-40's table contradicts it: DHA Phase 1 3.50M, Phase 4 3.63M, Phase 7 4.13M, Phase 6 5.64M per
marla. The number is also not comparable across societies. It is populated on 1,832 rows across
35 societies, so Phase 2 of Johar Town and Phase 2 of DHA share a value and nothing else. What it
carries within a society, the tier label already carries. First candidate removed by the
traceability rule.

*The encoding.* A smoothed target encoding of log price per marla (`price / area_marla`),
hierarchical: a level's mean is shrunk toward its society's, and a society's toward the city's,
with weight n / (n + m) on the level's own mean. Price per marla rather than total price because
it is comparable across plot sizes, and it is the quantity the §5.1 baseline is built on. A level
unseen at fit time, or a row with no society, falls back to the next tier up.

The smoothing strength m defaults to 20, matching D-50's long-tail cut. Stage 5 tunes it inside
cross-validation. Choosing it here would mean judging it by model results, which is stage 5's
question (handoff, "whether a feature earns its place").

*Where it is fitted.* `features.py` provides the encoder as a fit/transform object. It is never
computed onto the processed table, and no column derived from price is written to disk by this
stage. Stage 5 fits it inside each training fold. Within a fold, training rows receive
out-of-fold values from inner folds grouped on the B-23 loose key, so no row sees its own price
in its encoding and a pair that might be one house (D-60) cannot feed its price into its twin's.
Validation rows and inference inputs are transformed by the encoder fitted on the whole training
fold. This is the explicit leakage check for locality that PLAN §6 requires.

*Coordinates.* `latitude_clean` and `longitude_clean` enter raw. For the 359 levels under 20 rows
they let the model borrow from neighbouring societies, which a category label cannot. Null on 62
analysis rows (37 `out_of_lahore_nulled`, 25 `missing`), standing for 91 of 8,320 listings.
Not imputed, per D-33; the tree models route nulls natively. The stage 4 handoff gives 97, which
does not describe the analysis set; 62 is the measured figure.

*The raw label stays available.* The society plus phase label is kept as a categorical so stage
5 can compare this encoding with CatBoost's built-in handling. That comparison is a modelling
question, not a feature question.

Rejected: **one-hot encoding**, 442 sparse columns that tree models split on poorly.
**LightGBM's native categorical handling** at this cardinality, which overfits small levels
unless heavily regularised, and 246 levels hold under five rows. **Computing the encoding once
and storing it**, which either fits on every row and leaks the target, or fits on folds that do
not match stage 5's. **The full path tier**, on the evidence above.

*Open, found while verifying this entry.* Property 579334 carries no `loc_society`: `locality`
is null and `loc_path` is "DHA PHASE 6", so the parser read the whole path as a phase with no
society segment. One row, one listing. Its disposition is a separate decision. Until it is taken,
the fallback above prices it at the city level on the locality feature, and its coordinates still
place it.

---

**D-63 · Where `locality` is missing, the society is recovered from the address. Resolves
D-62's open item. Amends D-40**

Approved 11 Sep 2026.

Property 579334 is the only in-scope row with no `locality`, and the only address in the
analysis set written as one segment: "DHA PHASE 6". The parser takes the society from
`locality`, so it filed the whole address as a phase belonging to no society, and the row
formed a level of its own. Its title reads "1 Kanal House for Sale in Phase 6, DHA Lahore".
DHA is the society (Nauman, 11 Sep 2026).

Fixed as a rule in `clean.py`, upstream, per D-56, rather than for the one row:

- Only where `locality` is missing, `society_from_address` looks for an address segment that
  starts with a known society name as a whole word. The known names are the corpus's own
  canonical `locality` values (382 on the processed rows), so nothing comes from outside the
  data.
- The rest of the segment must be empty or a phase, sector or block, so a road name is never
  turned into a tier. The longest matching name wins.
- A recovered bare label is tidied to the corpus spelling ("PHASE 6" becomes "Phase 6") so the
  row joins its real level. Labels parsed from their own segment are untouched (D-40).
- `locality` and `address` are not rewritten. The row carries the `loc_society_from_address`
  flag and the step report counts it, along with any row still without a society.

Rejected: **a `MANUAL_CORRECTIONS` entry (D-46).** That step runs before the locality
decomposition and is limited to derived columns, so it would have had to overwrite the source
`locality`, which B-12's principle forbids. **Leaving the row at city level**, which D-62's
fallback would have done: the evidence to place it exists in the address itself. A rule also
covers the case D-26 set aside: listings after the window's ceiling carry only a free-text
address, so a widened window would need this.

Verified before the re-run, 11 Sep 2026: applying the old and new parser to all 6,607
processed rows (6,468 analysis, 139 excluded) changes exactly one, property 579334, whose
society becomes DHA, phase "Phase 6" and path "DHA > Phase 6". `loc_phase_num` stays 6. The old
parser reproduces every shipped `loc_path` on the analysis set, so the comparison is against
the code that built the artefact. No other row shares its coordinate, so the fingerprint
cannot merge it and the analysis set stays at 6,468 rows. Nine tests added, 122 of 126 pass in
the cloud workspace; the four that cannot run there are parquet round trips needing pyarrow.

**Verified on the re-run, 11 Sep 2026.** 178 tests pass on the project environment. The step
report shows one society recovered and none still without one. The regenerated analysis set
differs from the previous one in four cells, all on property 579334: `loc_society`,
`loc_phase`, `loc_path`, and `clean_flags` gaining the new flag. No `fp_group_id` moved, and
the members join still holds: 8,320 listings, 6,468 groups, one per analysis row, sizes equal
to `n_listings`. There are 442 society plus phase levels with none missing a society, so D-50's
count of 443 becomes 442; DHA Phase 6 goes from 259 rows to 260. On the pre-collapse set the
report now gives 468 distinct society > phase/sector combinations and 923 full paths.

The EDA baseline is not re-run for this change (Nauman, 11 Sep 2026). D-47's MdAPE of 10.62%
was measured with the row at a level of its own; one row of 6,468 cannot move it materially,
the accept threshold is relative to the baseline (D-47), and stage 5's first exit criterion
re-establishes the baseline on the current artefact in any case (PLAN §6).

---

**D-64 · `created_at` enters as months since the window opened, and is held at the training
data's latest date at inference. Settles D-51's open case. Amends B-24**

Approved 11 Sep 2026.

*The evidence it traces to.* D-55 measured a 14.1% rise in median price per marla from the
first complete month to the last. Measured here on features alone, no price, 11 Sep 2026, on
the 6,468 analysis rows: the mix of houses listed shifts sharply across the window.

| month | rows | median plot, marla | 1 kanal or larger | in DHA | in the 11 major developments |
|---|---|---|---|---|---|
| Sep 2023 | 577 | 5 | 17.9% | 11.4% | 33.3% |
| Oct 2023 | 297 | 5 | 16.5% | 6.1% | 8.4% |
| Nov 2023 | 547 | 5 | 13.3% | 4.6% | 24.7% |
| Dec 2023 | 613 | 6 | 17.0% | 9.6% | 24.3% |
| Jan 2024 | 373 | 7.3 | 24.9% | 12.1% | 20.6% |
| Feb 2024 | 490 | 10 | 28.2% | 20.4% | 24.1% |
| Mar 2024 | 545 | 10 | 27.3% | 31.6% | 24.2% |
| Apr 2024 | 411 | 6 | 22.4% | 7.5% | 18.7% |
| May 2024 | 479 | 6 | 18.8% | 3.1% | 21.9% |
| Jun 2024 | 491 | 6 | 17.1% | 1.2% | 21.2% |
| Jul 2024 | 851 | 10 | 27.7% | 12.8% | 43.7% |
| Aug 2024 | 604 | 10 | 37.3% | 32.3% | 50.7% |
| Sep 2024 (to the 14th) | 190 | 10 | 36.3% | 35.3% | 27.9% |
| **all** | **6,468** | 7 | 23.3% | 14.0% | 28.5% |

D-55's endpoints, Oct 2023 and Aug 2024, are the two months furthest apart in mix: DHA's share
6.1% against 32.3%, plots of a kanal or more 16.5% against 37.3%. Both DHA (D-40) and larger
plots (D-59) price higher per marla, so an unknown but probably large part of the 14.1% is a
change in which houses were listed rather than a change in prices. No month is thin; the
smallest is the partial September 2024 at 190 rows.

*The feature.* Time since 2 Sep 2023 in months, continuous. One engineered feature.

*Why it is included.* As a control. Without it, time and mix are confounded inside the other
features: 534 of DHA's 908 rows (58.8%) fall in Feb, Mar, Aug and Sep 2024, four of thirteen
months, so its locality encoding (D-62) would absorb whatever price change happened in those
months and overstate DHA's premium over societies listed mostly in quieter months. With time
alongside location and size, the model can attribute a mix change to location and size and a
price change to time.

*At inference.* The feature is set to the latest `created_at` in the training data, fitted from
the data rather than hard-coded, so a recency holdout or a re-scrape sets it correctly without
an edit. The estimator therefore prices at the asking-price level of the window's end, 14 Sep
2024, and says so (B-24).

*Why not "today".* A tree model treats every value beyond the last one it saw exactly as the
last one, so "today" would return the same prediction while hiding the assumption, and any
model that extrapolates would project a trend nobody has measured.

*Evidence for stage 5, not a decision here.* B-03's recency holdout tests precisely this
behaviour: its test rows sit beyond the training data's latest date, as every estimator input
will.

*Leakage.* `created_at` is the posting timestamp, not derived from price, and the value used at
inference is a fixed constant known in advance. Members of a fingerprint group share their
posting date on 99.8% of multi-listing groups (D-45), so the D-48 scoring against pre-collapse
listings sees the same value the model did.

Rejected: **dropping it**, which lets time and mix leak into the locality and size effects.
**Deflating the target to a common date with a monthly price index**, because the index would be
built from monthly medians that the table above shows are confounded by mix, baking the
confounding into the target itself. **A month-of-year feature**, since twelve months cannot
separate seasonality from trend.

*Consequence for B-24, amended.* The README cannot disclose 14.1% as the market's drift: it is
largely a mix shift. Stage 7 reports the drift the model attributes to time, the same houses
priced at the window's start and at its end, with the raw 14.1% beside it only as the
unadjusted figure and the reason it overstates.

---

**D-65 · Size enters unbanded, and the lookup estimate enters as one interaction feature**

Approved 11 Sep 2026.

*No bands in the model.* `area_marla` enters as a continuous value. Bands are a lookup-table
device; a tree model places its own cut points and places them within each location, which is
what D-59 requires: price per marla rises with plot size across the city, 3.60M at 5 marla or
less to 4.40M at 20 to 40, almost certainly because kanal plots sit in dear societies, so size
cannot be read without location. Banding stays in the §5.1 baseline only.

*No log or other monotone transform of area.* Tree models split on rank order, so `log(area)`
and `area` produce identical models. It would count against the ceiling and change nothing.

*The interaction feature: the lookup estimate.* The locality's encoded log price per marla
(D-62) plus `log(area_marla)`: the baseline's price estimate as one continuous value, without
its size bands. The target is log price (D-10), and log price equals log price per marla plus
log area. A tree cannot add two continuous features; it approximates the sum with many
axis-aligned steps. Supplying the sum hands the model the baseline's signal in a single split.
It traces to D-47 (the baseline alone scores MdAPE 10.62%) and to D-59 (size is meaningful
only crossed with location).

It is built from the D-62 encoding, so it inherits D-62's discipline in full: fitted inside
each stage 5 training fold, out of fold for training rows, never written to disk. Whether the
model predicts log price directly or a correction to this estimate is a stage 5 question; the
feature makes either possible.

Rejected: **bands crossed with location**, which rebuild the lookup table's cells and their
thin-cell problem, already solved in D-62 by smoothing. **Band-level target encodings**, more
levels estimated from the same few rows.

*Running count against PLAN §8's ceiling of 30 engineered features.* Three: the locality
encoding (D-62), months since the window opened (D-64), the lookup estimate (D-65). Carried raw:
`area_marla`, `latitude_clean`, `longitude_clean`, and the society plus phase label for stage 5's
CatBoost comparison (D-62). Dropped: `loc_phase_num` (D-62), and `loc_sector`, `loc_block`,
`loc_sub`, `loc_path` as tiers (D-62). Still to decide: `bedrooms` and `bathrooms`, and
extraction from `title` and `description` (D-52).

---

**D-66 · Bedrooms and bathrooms enter raw. No ratio features**

Approved 11 Sep 2026.

*The evidence.* EDA profiled both (D-54) and recorded no finding beyond D-35's exclusions, so
it was measured here on features alone, no price, 11 Sep 2026, on the 6,468 analysis rows:

- Populated on every row, 1 to 12 after D-35.
- They track size loosely: Spearman 0.70 between bedrooms and `area_marla`. Within a single
  plot size they spread widely: at 5 marla (1,545 rows) the 10th to 90th percentile runs from 3
  to 5 bedrooms, at 20 marla (1,019 rows) from 5 to 6.
- Bathrooms track bedrooms closely but not exactly: Spearman 0.88; equal or one more on 5,870
  rows (90.8%), fewer on 425.

*The rule.* Both enter as integers. They vary within a plot size, so they carry information
area does not, and they are the nearest thing the data holds to covered area, which Ilaan does
not publish and which matters where houses go up rather than out (D-35). They are also inputs
the estimator asks for.

*No ratios* (bedrooms per marla, bathrooms per bedroom). The size by rooms interaction sits on a
small discrete grid, a dozen standard plot sizes (EDA figure 04) against a handful of room
counts, which a tree model splits directly. No EDA finding points at a ratio, so it is not
built. If stage 5's SHAP shows an interaction the model handles poorly, this entry is open to
amendment (D-52).

Rejected: **total rooms**, which adds nothing the two counts do not already give a tree.
**Dropping bathrooms as redundant with bedrooms**: 0.88 is not identity, and whether a feature
contributes is stage 5's question, answered by ablation.

*Running count.* Engineered: three, unchanged (D-62, D-64, D-65). Carried raw: `area_marla`,
`bedrooms`, `bathrooms`, `latitude_clean`, `longitude_clean`, and the society plus phase label.
Still to decide: extraction from `title` and `description` (D-52).

---

**D-67 · Nothing is extracted from `title` or `description`. Settles D-52's text question**

Approved 11 Sep 2026.

*The evidence*, measured 11 Sep 2026 on the 6,468 analysis rows:

- `description` is empty on 6,354 rows (98.2%): null on 6,054, whitespace or line breaks only
  on 300. 101 rows carry more than 20 characters. Checked at source rather than assumed: three
  sampled pages from the local cache (no request to Ilaan) carry `"description":""` in the page
  data, so the sellers wrote nothing and the parser is not losing text.
- 6,082 titles (94.0%) follow the template "<n> Marla House for Sale in <place>". Area and
  place are already extracted (D-32, D-40).
- Twenty candidate signals were searched for in both fields: corner, park facing, near park,
  boulevard, main road, single, double and triple storey, basement, brand new, furnished,
  Spanish, modern, solar, renovated, old construction, road width in feet, owner built,
  possession, installments. The commonest, "brand new" and "furnished", appear on 35 rows each
  (0.5%); sixteen of the twenty appear on fewer than 10.

*The rule.* No text-derived feature is built.

1. At 0.5% coverage no extracted flag can carry weight.
2. An unmentioned attribute is not an absent one: a corner house whose advert omits the word
   would be recorded as not a corner, so a flag would record the advert's wording, not the house.
3. Consistent with D-18, which left NLTK out because no text modelling was planned.

`title` and `description` stay in the processed table as text sources for audit and are never
modelled.

*A defect found while checking, logged rather than fixed (Nauman, 11 Sep 2026).* 9 analysis
rows and 2 excluded rows carry the literal `$2b` as their description: on those pages the text
sits in a separate chunk of the page data and `parse.py` recorded the pointer instead of
resolving it. Every column of both processed files was checked for the same pattern and
`description` is the only one affected. Not fixed because after this entry nothing reads the
column; logged as B-25 with the fix described.

*Running count.* Engineered: three (D-62, D-64, D-65). Carried raw: `area_marla`, `bedrooms`,
`bathrooms`, `latitude_clean`, `longitude_clean`, and the society plus phase label. All five
open questions from the handoff and D-51 are now decided.
