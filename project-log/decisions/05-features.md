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
