# Decisions — Stage 3: EDA

Append-only. One entry per decision: what, why, what was rejected and why.
Entries are stubbed when the decision is taken and prose-edited at stage close (LESSONS L-23).

A **STUB** marker means the shape of a decision is settled and a number in it is not. Every
stub must carry a value before the stage closes; B-05 exists precisely because a provisional
number can reach validation unnoticed.

---

**D-47 · The acceptance criteria have three parts: an absolute level, a relative one, and a
segmented one. Settles the shape of B-05; the numbers are locked at stage close**

PLAN §5.1 set MdAPE ≤ 20% and PPE20 ≥ 55% on 2 Sep 2026 without sight of the data. Stage 2
then found price per marla tight — p25 3.10M, median 3.70M, p75 4.50M — which raises a real
possibility that §5.1's own baseline, median price-per-marla by locality × size band, lands
near the absolute threshold on its own. An absolute criterion that a lookup table satisfies
says nothing about whether the model was worth building, and it would let the project report
a pass while D-06's actual finding went unstated.

So the locked criteria have three parts:

**LOCKED 8 Sep 2026.** The baseline was measured before any threshold was written, on the
D-48 metric: **MdAPE 10.62%, PPE10 48.5%, PPE20 72.6%**, and 11.76% with Park View Villas
excluded. PLAN §5.1's provisional accept (MdAPE <= 20%, PPE20 >= 55%) and even its stretch
(15%) are all beaten by a lookup table with no model in it. Locking them as written would have
certified nothing.

| level | rule | on today's baseline | and |
|---|---|---|---|
| stretch | MdAPE <= 0.80 x baseline | <= 8.50% | PPE20 >= 80% |
| **ACCEPT** | **MdAPE <= 0.90 x baseline** | **<= 9.56%** | **PPE20 >= 75%, and MdAPE <= 10.0% absolute** |
| floor | no improvement on the baseline | > 10.62% | reframe around the pipeline, the analysis and the baseline |

**The margin is relative, not a fixed number of points.** The baseline is an estimate and it
will move — a different fold, a size-band change at stage 4, the recency holdout of D-55 if
stage 5 adopts it. "10% better than the baseline" survives all of those unchanged; "1.1 points
better" silently gets easier or harder. The absolute backstop of 10.0% exists so that a
collapsed baseline cannot make a weak model look good.

**PPE10 is reported and not binding.** Within-group price variation alone caps it at 94.5%
(measured above), and a criterion needs a reachable target. PPE20's ceiling of 98.3% is far
enough from 75% not to bind.

The floor is restated from §5.1's spirit rather than its number: "MdAPE > 30%" was set against
an expectation of 20%, and against a 10.62% baseline the honest floor is failing to beat the
baseline at all.

Rejected: **locking only the absolute pair as written.** It is the cheaper decision and it
leaves the project unable to distinguish "the model works" from "this market is predictable
from two columns" — which is the single most likely outcome given the cleaning findings, and
the one D-06 already committed to reporting honestly.

---

**D-48 · The headline metric is measured on pre-collapse listings, not on group medians.
Closes the measurement half of B-21**

D-45 collapsed each fingerprint group to one row at the median price, so a metric computed on
the analysis set never sees the within-group price variation no model can resolve — 3.23%
median, 7.26% p75, 13.9% p90 on the rows that had replication. B-21 required that floor to be
disclosed. Disclosing it asserts a number the project can instead measure.

**How.** The split is group-aware on `fp_group_id`. The model trains on the ordinary rows of
the analysis set; there is no group-wise fitting, and one row already *is* one group. For
evaluation, each held-out row produces one prediction — every listing in its group has an
identical feature vector — and that prediction is scored against every pre-collapse listing in
the group, at the price each poster actually set. D-53 makes those listings available.

**What is reported.**

| number | role |
|---|---|
| MdAPE over pre-collapse held-out listings | **headline, binding** — what an individual listing experiences |
| MdAPE over held-out rows, one per group | model quality; the set on which D-47's relative comparison against the baseline is computed |
| the gap between the two | the measured cost of the collapse, replacing B-21's asserted floor |
| the headline with Park View City excluded | B-22, see below |

**The distortion, stated rather than discovered later.** Weighting by listing gives a
44-listing group 44 times the weight of a singleton. Roughly 2,755 pre-collapse rows sit in
899 multi-listing groups, so about 11% of groups carry some three times their share of the
test set — and B-22 records that this replication is concentrated in one development. The
headline is therefore partly a statement about Park View City's bulk postings, which is why
it is also reported with that society excluded.

**Verified on the artefact, 8 Sep 2026.** The join is well formed: 8,320 member listings
across 6,468 groups, one group per analysis row, one survivor per group, group sizes equal to
`n_listings` on every group, and each analysis row's `price` exactly the median of its members'
`price_listed` — maximum discrepancy 0.

The bound this puts on the locked numbers, measured rather than assumed. Give a model perfect
knowledge of every group median and score it against each listing's own asking price:

| | listing-weighted, all 8,320 | replicated listings only (2,747) |
|---|---|---|
| MdAPE floor | **0.00%** | 3.26% |
| PPE10 ceiling | 94.5% | 83.4% |
| PPE20 ceiling | 98.3% | 95.0% |
| mean APE floor | 1.90% | — |

Two thirds of listings are singletons whose group median is their own price, so the collapse
costs the **headline median almost nothing** — B-21's concern, quantified, is far smaller than
its framing suggested for MdAPE. It is not nothing for the proportional metrics: a perfect
model cannot exceed PPE10 of 94.5%, because 138 listings sit more than 20% from their own
group's median and no prediction can be close to both ends of a ladder at once. PPE20's
provisional 55% is nowhere near its 98.3% ceiling, so that criterion is unconstrained; a PPE10
target, if D-47 sets one, must be read against 94.5% rather than 100%.

This is a bound, not a prediction: it isolates the within-group component and says nothing
about the model's own error. The gap D-48 reports is still measured at stage 6.

Rejected: **reporting the group-median MdAPE with B-21's floor as a caveat.** It asserts what
it could measure, and a caveat in a README is weaker evidence than a number in a table.

Rejected: **collapsing the training fold only**, unchanged from D-45 — it would preserve the
measurement while putting a fold-specific rule into stage 5 and leaving the processed artefact
internally inconsistent. D-53 gets the same measurement without either cost.

---

**D-49 · A segment binds only above a minimum size, and at a looser threshold than the
headline**

§5.1 requires MdAPE broken out by price band and locality tier but does not say what happens
when one is bad. Three ways to resolve that, of which the third is adopted:

- Headline binding, segments informational — permits shipping a model that fails an entire
  market segment as long as the average holds.
- Every segment binding at the headline threshold — a twelve-row slice has a wildly noisy
  MdAPE, so the project would fail on sampling noise.
- **Adopted.** Headline binding at D-47's threshold. A segment binds only if it holds at least
  *n* held-out rows, and then at a multiple of the headline threshold. Segments below *n* are
  reported and not binding, and the README and the estimator disclose which parts of the city
  the model is thinly evidenced on.

**LOCKED 8 Sep 2026: a segment binds above 100 held-out listings, at 1.5x the headline
MdAPE threshold** — 14.3% against the accept level of 9.56%. Measured against a 20% held-out
fold of the 8,320 listings, the smallest of D-50's seven segments holds roughly 344 listings,
so every segment clears the minimum and all seven bind. The minimum stays in the rule anyway:
it has to hold after stage 4 changes the size bands, or after a recency holdout changes what
lands in the fold.

---

**D-50 · Segment definitions are fixed before any model exists**

The price band cut points and the locality tiers of D-49 are fixed here, before stage 5
begins. Choosing them after seeing model results would let the slicing be chosen to pass, and
nothing afterwards could prove it had not been. This is the same objection D-38 raised against
putting price in the dedup fingerprint: a decision about the features must not be settled by
consulting the target.

**LOCKED 8 Sep 2026.** Cut points are absolute, taken from the quartiles of the 8,320 listings
D-48 scores, so they do not move with a fold:

| segment | definition | held-out listings, 20% fold |
|---|---|---|
| price Q1 | listing price < 15.5M | ~416 |
| price Q2 | 15.5M to 25.5M | ~416 |
| price Q3 | 25.5M to 50.0M | ~416 |
| price Q4 | > 50.0M | ~416 |
| major developments | society+phase with >= 100 analysis rows (11 of them) | ~591 |
| mid developments | 20 to 99 analysis rows (72) | ~727 |
| long tail | under 20 analysis rows (360) | ~344 |

The locality tiers are cut on **volume, not on price**, for the D-38 reason. The baseline
already runs 10.90% MdAPE in Q1 and 15.00% in Q4, so the price-band split is evidenced rather
than assumed: the dearest quarter is around 60% harder before any model exists.

---

**D-51 · Two separate lists bar a column from the feature set: leakage, and unavailability at
inference**

They are different failures and conflating them loses one of them.

**Leakage** is a column derived from the target. It is barred in every context, forever, and a
model that reads one is reading the answer.

**Unavailable at inference** is a column that is honest and real but unknowable at the moment
someone uses the estimator. PLAN §2's deliverable is an app a person types a house into, and
that person is pricing a property that has not been advertised yet. A model leaning on these
validates well and cannot be served. The bar is a consequence of *what is being built*: the
same column would be legitimate in a model that scores listings that already exist, and that
distinction is worth keeping rather than losing inside one undifferentiated list.

**LOCKED 8 Sep 2026. Nine columns are barred.**

| column | barred because |
|---|---|
| `price_listed` | leakage. It is the target itself, at listing level (D-53) |
| `fp_price_median` | leakage. The group median, which *is* the target on a collapsed row |
| `fp_price_spread` | leakage. The dispersion of the very prices the target was taken from |
| `n_listings` | not at inference, and target construction. Nobody knows how many times a house that has not been posted will be posted. It also records how many prices the median was taken over, and it proxies developer bulk inventory, which prices about 9% below singleton listings in Park View Villas |
| `collapsed` | not at inference. A provenance flag about the row, not a fact about the house |
| `views` | not at inference. Attention an advert accumulated after it went up |
| `image_count` | not at inference |
| `is_featured` | not at inference. A paid placement on an advert that does not yet exist |
| `has_video` | not at inference |

**A correction to this entry's own first draft.** It originally filed all five de-duplication
columns as leakage. Three of them are: `price_listed`, `fp_price_median` and `fp_price_spread`
are built from prices. `n_listings` and `collapsed` are not — the D-43 fingerprint is built
from coordinates, locality, area and room counts, with price deliberately excluded (D-38) — so
they fail the inference test rather than the leakage test. The remedies differ, which is the
whole reason the two lists are kept apart, so the misfiling mattered.

**Barred for weaker reasons, and listed so the count reconciles.** Eleven audit columns carry
provenance and the cleaning trail and are never modelled: `property_id`, `source_url`,
`discovered_on_page`, `price_matches_discovery`, `area_source`, `coord_in_lahore`,
`coord_source`, `clean_flags`, `exclusion_reason`, `excluded`, `fp_group_id`. Six superseded
columns are source values kept beside their cleaned form so a conversion stays auditable
(B-12), and it is the cleaned form that is the candidate: `area`, `area_unit`, `locality`,
`latitude`, `longitude`, `address`. Two are text sources rather than features: `title` and
`description` are never fed to a model as strings, though they may yield features by
extraction, which is a stage 4 question.

**Thirteen candidates go forward**, and whether each becomes a feature is stage 4's decision on
this stage's evidence (D-52): `area_marla`, `bedrooms`, `bathrooms`, `latitude_clean`,
`longitude_clean`, `loc_society`, `loc_phase`, `loc_phase_num`, `loc_sector`, `loc_block`,
`loc_sub`, `loc_path`, `created_at`. One target, nine barred, eleven audit, six superseded, two
text sources and thirteen candidates account for all 42 columns.

**`created_at` is the one genuinely open case, and it is left open deliberately.** It is
knowable at inference only as "today", which lies outside the twelve-month window the data
covers, and D-55 measured a 14.1% drift in median price per marla across that window. Using it
as a feature means extrapolating that trend past the data; holding it fixed at the window's end
means ignoring it. PLAN §3 anticipated it as a control. Stage 4 decides on the D-55 evidence;
EDA's job was to make the evidence exist, not to make the choice (D-52).

This table is written here rather than in stage 4 so that stage 4 inherits it instead of
rediscovering it.

---

**D-52 · EDA measures; stage 4 decides**

Where a choice depends on evidence this stage produces, the evidence is produced here and the
choice is made in stage 4 and logged there. That applies to the locality tier (D-40 left
society, society-phase and full path all available at 378, 471 and 926 distinct values), to
whether anything is extracted from `title` and `description`, and to how B-22's
over-representation is handled.

The reason is not tidiness. A choice made while measuring is a choice made against whichever
slice was on screen, and it becomes hit-and-trial that nobody can audit afterwards. Stage 4's
own exit criterion — every feature traced to an EDA finding — only means something if the
findings exist before the features do. Decisions here remain open to amendment as later stages
produce new information; they are not open to being made twice.

---

**D-53 · The collapse marks its members instead of deleting them, and the run emits
`listings_members`. Amends D-45 and D-42; implements D-48**

D-45 deleted the 1,852 non-surviving rows of each fingerprint group. They were reconciled in
the report and they appear in no artefact — the one step in the pipeline whose removals cannot
be inspected afterwards. D-48 needs exactly those rows.

**What changed in `clean.py`:**

- `collapse_groups` marks folded rows with a new `collapsed` flag instead of dropping them.
  The survivor still takes the group median; a folded row keeps the price its own poster set.
- A new `price_listed` column carries the poster's own asking price on **every** row,
  captured before the survivor's `price` is overwritten. Without it the survivor's real price
  is destroyed and each group is missing exactly one listing — see LESSONS L-27. This is the
  B-12 principle that already keeps `area` beside `area_marla` and `latitude` beside
  `latitude_clean`; price was the one derived value that overwrote its source.
- `analysis_rows` honours both flags, so every count from the collapse onward still reports
  the modelled set and not the frame.
- `write_processed` splits three ways and writes `listings_members.parquet` / `.csv`: one row
  per pre-collapse analysis listing, deliberately slim — `property_id`, `fp_group_id`,
  `price_listed`, `n_listings`, `fp_price_median`, `collapsed`, `created_at`. Slim so that no
  later stage can mistake it for a training table and put every folded listing back into the
  loss D-45 removed it from.
- The write asserts one group per analysis row (L-26: a count an artefact rests on gets a
  bound asserted where it is computed). If that ever stops holding, stage 6 would silently
  score against the wrong listings.
- `SCHEMA` gains `price_listed` and `collapsed`, per D-39. Four tests added, three amended.

**The join is only valid within one run.** `fp_group_id` is a positional code from
`pd.factorize`, so a re-run renumbers it. `listings.parquet` and `listings_members.parquet`
must come from the same execution of `run_clean.py`. A stable hash of the fingerprint key
would remove that constraint and is *not* adopted here: it changes the values of a column
already written, for a fragility that a same-run rule handles. Revisit if stage 6 ever needs
to join across runs.

Rejected: **routing folded rows into `listings_excluded`.** It would answer "why is this
listing not in the model" in one place, and it would blur D-42's meaning — that file holds
rows outside the analysis set on scope and quality grounds, and a later reader would take a
folded row for a rejected one.

---

**D-54 · Every column is profiled; narrative is spent on the columns that could become
features**

The exit criterion is that every column's distribution is reviewed, and there are 40 of them
against a two-day cap. The stage produces one generated profile covering all 40 — dtype,
non-null count, distinct count, a type-appropriate summary, and an explicit disposition of
*feature candidate*, *audit-only* or *superseded by X*. Narrative and plots are spent on the
columns the profile marks as candidates, and on the four that describe the sample rather than
the property (`n_listings`, `fp_price_spread`, `collapsed`, `price_listed`), because B-21 and
B-22 live in those.

The test for which column gets narrative: could it plausibly become a feature, or change a
decision about another column? Every count the profile emits carries an upper-bound assertion
in the expression that computes it (L-26).

---

**D-55 · The recency-holdout evidence is produced here; the choice is made at stage 5**

B-03 has been undecidable since intake and is now live: `created_at` survives cleaning as a
real UTC datetime (D-39). This stage produces the evidence — median price per marla by month
and listing volume by month across the 2 Sep 2023 – 14 Sep 2024 window — so that stage 5 can
choose between a random group-aware split and a recency holdout from measurement rather than
from preference. Per D-52, the choice itself is stage 5's and is logged there.

---

**D-56 · A defect found here is fixed here, upstream, not carried downstream**

If EDA finds that a cleaning, parsing or extraction rule is wrong, the rule is amended and the
pipeline re-run in this stage, so stage 4 receives a correct dataset rather than a correct
dataset plus a list of things to remember. D-44 already defers one such question to this stage
— the ~two dozen rows between 400,000 and 1M per marla, whose band was left soft deliberately.

The cost is accepted knowingly: an amendment invalidates the `v0.2-cleaning` artefacts and
requires a re-run and a re-tag. The alternative is a correction applied in a notebook, which
is invisible to every later reader and to the reproducibility claim in PLAN §10.

---

**D-58 · DHA Rahbar is DHA Phase 11, and its own phase numbering is kept beside it.
Closes B-18. Amends D-40**

Three labels denote one place — `Rahbar - Phase 1` (2 rows), `Rahbar - Phase 2` (5) and
`Phase 11 - Rahbar` (5). Read literally, the first two set `loc_phase_num` to 1 and 2, which
files a peripheral scheme among DHA's inner phases and is what made B-19's comparison look
wrong. DHA Rahbar is officially DHA Phase 11 and numbers its own phases inside it, so both
numbers are real and they describe different levels.

All twelve rows now carry `loc_phase = "Phase 11 - Rahbar"` and `loc_phase_num = 11`; where
the label states Rahbar's internal phase, that goes to `loc_sub` rather than being discarded.
`clean.SUB_SOCIETY_PHASES` holds the mapping, keyed on **(parent society, marker)** so the
word alone rewrites nothing — a Rahbar in another society is left as it is.

The marker is matched against the unclassified segments as well as the phase segment. No row
in this corpus needs that branch; it exists so a re-scrape writing "Rahbar, DHA, Lahore"
cannot be filed silently as an unclassified sub-tier. Five tests pin the behaviour.

This is local knowledge and the data could not have established it — the same class of
correction as D-46, recorded the same way, on Nauman's call of 8 Sep 2026. It is applied
upstream in `clean.py` and the pipeline re-run, per D-56, rather than patched in a notebook.

Rejected: **collapsing the internal phase into the DHA one.** Rahbar Phase 1 and Rahbar
Phase 2 are different places and may price differently; D-40's principle is that cleaning
makes every tier available and chooses none.

---

**D-59 · B-19 is explained: the anomaly was a size-mix artefact. Closes B-19**

B-19 recorded DHA Rahbar at 4.50–4.60M per marla against DHA Phase 1 at 3.50M and Phase 4 at
3.63M, and flagged the direction as wrong for a peripheral scheme. The comparison was not
like for like. Rahbar's twelve rows are 5 to 10 marla with a median of 5; DHA excluding
Rahbar has a median plot of 20 marla. Holding size constant reverses the finding:

| at 5 marla | n | median PKR/marla |
|---|---|---|
| DHA main phases | 123 | 4.91M |
| DHA Rahbar | 7 | 4.50M |
| whole city | 1,610 | 3.70M |

Rahbar sits below the DHA main phases and above the city, which is where a DHA-branded
peripheral scheme belongs. Nothing is wrong with the rows. One hypothesis, inside D-57's
budget.

**A larger finding fell out of it.** Price per marla *rises* with plot size across the city —
3.60M at 5 marla or less, 4.40M at 20–40 — which is the opposite of the usual small-plot
premium and is almost certainly location confounding, since kanal plots sit in the expensive
societies. Consequence for stage 4: size cannot be banded without location. The §5.1 baseline
already crosses the two, which is now supported by evidence rather than convention.

---

**D-57 · B-18, B-19 and B-20 are explained, under a stopping rule**

The handoff's own guidance (L-24) would flag and stop on all three: 14 rows, 14 rows, 10 rows,
each far below 0.5% of the sample. They are explained anyway, because a *wrong direction* is
evidence of a defect in a rule rather than a quirk in a row — B-19's Rahbar medians sit above
two DHA main phases, which is the wrong way round for a peripheral scheme, and a labelling or
parsing fault that produced it would affect every row it touches, not fourteen.

Explaining is bounded: **two hypotheses tested per item, or 45 minutes per item, whichever
comes first.** Then either explained, or logged with the evidence gathered and the hypotheses
ruled out. Some of this may need local knowledge rather than data, in which case it resolves
as a D-46-shaped entry with the evidence attached, or not at all.

**Outcome, 8 Sep 2026.** B-18 explained and fixed upstream (D-58). B-19 explained and
dissolved (D-59). B-20 reviewed and closed with no change (D-61). All three inside the budget;
no item consumed its second hypothesis.


---

**D-60 · De-duplicate on a tight key, split on a loose one. Evidence for stage 5**

D-45's collapse removes only listings that share a fingerprint exactly. A house posted twice
with a slightly different address or a slightly different area lands in two groups and would
sit on both sides of a train/test split. Measured as an upper bound, without using price —
D-38's objection to letting the target establish identity applies with more force here:

| pattern | rows | share |
|---|---|---|
| same coordinates + area + rooms, different `loc_path` | 572 | 8.84% |
| same coordinates + path + rooms, area within one marla | 271 | 4.19% |
| upper bound, both | 843 | 13.03% |

**It is an upper bound and probably a large overestimate.** D-38 measured that 70.6% of rows
share their exact coordinate with another row, because Ilaan geocodes to a society or a street
rather than to a house, so identical coordinates do not mean the same building. It cannot be
narrowed: the only fields that would settle it are price, which is barred, and a house-level
coordinate, which does not exist.

**The mitigation is procedural and costs nothing.** Dedup and splitting are different jobs and
should not share a key. De-duplicate on the **tight** D-43 fingerprint, which is conservative
so that different houses are never merged. Split on a **loose** key — coordinates, rooms and
rounded area, ignoring `loc_path` — so that any pair which might be one house falls wholly into
train or wholly into test. The residual stays in the sample and stops being able to leak.

Stage 5 implements it; per D-52 the choice is logged there. Rejected: **tightening the
fingerprint to merge these rows**, which would merge genuinely different houses on one street
to fix a split problem that a split-time rule fixes for free.

---

**D-61 · B-20 and D-44's soft boundary both close with no change**

Both deferred a judgement to "the distribution in view". The distribution is now in view and
neither changes.

**B-20 — the area conflicts.** Nine rows reach the analysis set, 0.14% (B-20 says ten; one does
not survive the collapse). Under D-32's payload reading their price per marla is
indistinguishable from the corpus — median 3.75M against 3.70M — and seven of the nine sit
inside the corpus 5th-to-95th percentile band. Nothing suggests the measured area is the wrong
one. D-32 stands, the rows stay flagged, and no further effort is spent on ten rows (L-24).

**D-44 — the rows between 400,000 and 1M per marla.** 25 rows, 0.39%, median area 10 marla and
median price 7.0M. The answer is in their societies rather than in the rows: Damaan City prices
at 0.80M per marla across *all* its rows, Barki Road at 1.17M, Chinar Bagh at 1.19M. These are
cheap peripheral developments, not mistyped prices, and a tighter band would delete the bottom
of the market rather than clean it. The band stops where "not an asking price" ends, which is
where D-44 put it.
