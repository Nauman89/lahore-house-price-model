# Decisions — Stage 2: Cleaning

Append-only. One entry per decision: what, why, what was rejected and why.
Entries are stubbed when the decision is taken and prose-edited at stage close (LESSONS L-23).

---

**D-31 · Canonical area unit is marla at 225 sq ft**

B-12 fixed marla as the canonical unit; this fixes the factor. 1 marla = 225 sq ft = 25 sq
yd, 1 kanal = 20 marla. That is the convention used by DHA and the post-1970s societies that
make up most of this sample.

The table carries one deliberate inconsistency. Pakistani land convention puts 1 acre = 8
kanal = 160 marla, which implies a 272.25 sq ft marla — the older, larger definition. At 225
sq ft an acre is 193.6 marla. Both cannot hold at once. 160 is kept because it is what an
acre means in a Pakistani listing, and the disagreement is recorded in the code beside the
factor rather than silently resolved. In practice it never fires: the single row carrying
`area_unit="acreage"` is a title mismatch that resolves to marla under D-32.

Rejected: the 272.25 sq ft marla, which is correct for older agricultural land records and
wrong for the urban housing societies this model covers.

**D-32 · Title and payload each win on the field where they are the better source**

*Rewritten 8 Sep 2026. The first version of this entry is superseded and its reasoning was
false — see the correction at the end.*

B-15 established that Ilaan's payload `area_unit` is wrong at source and the title is right.
This entry settles what happens when they disagree about anything else. The answer is not
uniform, because the evidence differs field by field.

| disagreement | winner | rows | evidence |
|---|---|---|---|
| unit | **title** | 54 | payload unit wrong at source in both directions, a 20x error either way; verified against live pages by the stage 1 manual audit (D-28) |
| compound encoding | **title** | 5 | "1 Kanal 2 Marla" stored as the decimal `1.2 kanal` — the payload collapsed two tokens into one number |
| quantity, gap < 1 marla | **payload** | 17 | payload is the measured area, title is the rounded marketing figure |
| quantity, gap >= 1 marla | **payload**, flagged | 10 | no evidence either way; the payload keeps precedence as the measured field |

On the unit branch the title wins outright, quantity included. A payload whose unit field is
broken has not earned partial trust in the number beside it.

**Why the payload wins on quantity.** Across the rows where both sources state an area and
disagree by under a marla, the payload carries more decimal places on **16 of 17** and fewer
on **none**: `area=2.52` against a title of "2.5 Marla", `area=6.76` against "6.8 Marla",
`area=11.45` against "12 Marla". 8.8% of payload areas are fractional. The title is what the
agent typed for the advert; the payload is the plot as measured.

The 10 rows a marla or more apart are flagged `area_quantity_conflict` rather than
adjudicated. The cached pages were checked for a third source and there is none — the page
renders the title string and the payload number and nothing further, so no additional
evidence exists anywhere to settle them.

Rejected: **adjudicating those 10 on price-per-marla plausibility.** It would resolve them,
and it points to the title on some rows and the payload on others. Rejected because deciding
what a feature says by checking which answer makes the target look more reasonable is the
same objection that keeps price out of the dedup fingerprint (D-38), and it would be far
harder to notice here.

**The superseded version, and why it was wrong.** This entry first read "the title wins over
the payload on area quantity as well as unit", justified by the claim that Ilaan's payload
rounds every fractional area to a whole number, so that "2.5 Marla" arrives as `area=3`.
That claim is false: 747 of 8,444 payload areas are fractional. It was believed because it
was read off a printout formatted to zero and one decimal places, which displayed 11.45 as
11.0 and 2.52 as 3 — the rounding was in the view, not in the data. Under the superseded
rule 17 rows had a measured area replaced by a rounded one. Caught when Nauman queried a
single row's price on 8 Sep. Recorded in LESSONS L-25.

**D-33 · Coordinates outside Lahore are nulled, never imputed**

77 in-scope rows carry coordinates outside Lahore. They split three ways:

| | rows | treatment |
|---|---|---|
| coordinates and title both say another city | 12 | excluded, D-34 |
| title says Lahore, coordinates do not | 65 | coordinate nulled, row kept |
| title names another city, coordinates say Lahore | 6 | kept as-is — title typo |

`latitude` and `longitude` are left as parsed. The cleaned values go in `latitude_clean` /
`longitude_clean` with `coord_source` recording which of `source`, `out_of_lahore_nulled` or
`missing` applies, so the conversion stays auditable (the B-12 principle).

Bounding box 31.15–31.80 N, 73.95–74.75 E. Checked for sensitivity: widening or narrowing it
by 0.05° in every direction returns the same 77 rows, so the result does not depend on where
the box is drawn.

Rejected: **imputing a locality centroid from our own rows.** Feasible — 64 of the 65 sit in
a locality with at least three good coordinates — and rejected because an imputed coordinate
looks precise and is not, and downstream code cannot tell the two apart. It would also give
every row in a locality one identical point, which recreates the exact coarse-key failure
that B-07 exists to fix. The centroids are meaningless at this granularity in any case: the
good coordinates inside "DHA" span 16 km by 28 km, and "Bahria Town" 16 by 22.

Rejected: **external geocoding.** Nominatim or Google on a Pakistani society name returns a
society centroid — the same value we could compute ourselves, with patchier coverage, no
ground truth to validate against, and an API key and network dependency inside a pipeline
PLAN §10 requires to run from a clean checkout. B-04 closed geocoding as unnecessary and
nothing here reopens it.

Standing constraint regardless of what stage 4 decides about centroids as a *feature*: an
imputed coordinate never enters the dedup fingerprint.

**D-34 · Scope exclusions beyond D-02's type filter**

D-02 excludes flats, apartments, plots and portions; the source's `type` field does not
enforce it. Three leaks, all detected from the title:

- **10 penthouses** carrying `type="House"` (B-16). A penthouse is an apartment.
- **23 rows titled "(Ground Floor)", "(First Floor)" or "(Second Floor)"**, including seven
  Jumeirah Park Villas listings sold floor by floor. A floor being *sold* is an apartment or
  a portion. B-16 checked for the word "portion" and would not have caught these.
- **12 rows in another city**, where the title names one and the coordinates agree (D-33).

Rejected: trusting `city`, which reads "Lahore" on all 8,459 rows and settles nothing.

**D-35 · Zero and impossible room counts are excluded**

31 rows carry `bedrooms=0` or `bathrooms=0` (30 have both). Zero is a missing-value sentinel,
not a house with no bedrooms, and these rows carry no usable structure. 3 further rows are
physically impossible — 41 bedrooms on 5 marla, 33 on 3 marla, 32 on 4 marla.

The cutoff is `bedrooms >= 20`, deliberately blunt. A first attempt tied plausibility to floor
area and fired on 73 rows, because 7 bedrooms on a 10 marla house is entirely normal in
Lahore where houses go up rather than out. Anything subtler than "physically impossible"
requires the joint distribution and belongs to EDA (LESSONS L-24).

**D-36 · Processed table is parquet; CSV is a regenerated view**

`data/processed/listings.parquet` is what every downstream stage reads. Parquet round-trips
dtypes and preserves the null-versus-empty-string distinction, which several cleaning flags
depend on; it is roughly 5–10x smaller; and a re-read cannot silently re-type a column, which
is the failure mode that poisons a pipeline several stages later. A CSV export is kept as a
convenience view for eyeballing rows, regenerated from the parquet and never read back by
code.

`pyarrow` is declared explicitly in `pyproject.toml` rather than relied on as Streamlit's
transitive dependency, per D-18. It was already resolved at 25.0.1, so the lockfile does not
move.

**D-37 · Zero-variance columns are dropped mechanically; varying columns are not**

Fourteen columns hold exactly one value and are dropped. Ten are single-valued at source:
`condition`, `year_built`, `is_verified`, `is_gold_verified`, `is_sold`, `market_status`,
`city`, `province`, `amenity_count`, `amenities`. B-13 listed five of these; the other five
are equally single-valued and were missed.

Four more are constant because of a filter applied upstream rather than because the source is
uniform, and are dropped on the same principle: `property_type` is "House" only because stage
1 selected houses, `in_scope` and `scope_reason` describe a partition this table is already
on one side of, and `id_matches_discovery` is a stage 1 QA flag that passed on every row. The
interim file keeps all four.

`is_featured` (13 True) and `has_video` (123 True) are **kept**, against B-13, which filed
them under "zero-variance columns, safe to drop". They vary. They may proxy for how
professionally a listing is marketed, they cost nothing to carry, and B-13's own principle is
that non-mechanical column decisions wait for stage 4. `views`, `image_count` and
`price_matches_discovery` are kept for the same reason.

The drop is verified rather than trusted: each listed column is checked to be single-valued
before it goes, and every unlisted column is checked *not* to be. Either surprise is reported
instead of proceeding quietly. That check is what found the four filter-constant columns.

Variance is measured over all 8,459 in-scope rows, excluded rows included — not over the
analysis set. On the analysis set `excluded` and `exclusion_reason` are constant by
construction, and they exist precisely to describe the rows outside it.

**D-38 · The 5% near-duplicate stopping rule is unreachable and the 2-day cap governs**

PLAN §8 stops cleaning at "2 days, or flagged near-duplicate groups below 5% of rows,
whichever comes first", set at intake without sight of the data. Measured on the 8,390 rows
carrying coordinates, price and area:

| fingerprint | rows in multi-listing groups | rows flagged (>15% spread) |
|---|---|---|
| D-08 as written: locality + area + beds + baths | 76.4% | 59.7% |
| coordinates + area + beds + baths | 37.3% | 17.8% |

The rebuild is a large improvement and still more than three times the threshold. The cause
is that Ilaan's coordinates are society- or street-level for a large share of rows: 70.6% of
rows share their exact coordinate with at least one other row, the largest cluster being 126.

The 5% is therefore recorded as unmet and the 2-day cap is the operative stopping rule.
Rejected: **adding price to the fingerprint**, which reaches 7.8% and is the cheap route to
the threshold. Using the target to decide which rows are the same house would flatter the
train/test split by construction.

B-06's 15% spread threshold is set from the measured distribution in a later entry, not
inherited.

**D-39 · The processed table has a declared schema, not an inferred one**

Every column is cast to a type named in `clean.SCHEMA`. A column in the frame but not in the
schema, or in the schema but not in the frame, is reported rather than passed through.

Inference is how a pipeline drifts between machines. `DataFrame.from_records` types a string
column as `object` on pandas 2 and `str` on pandas 3; an integer column with one null becomes
a float; and `created_at` stays text, which sorts lexically — B-03's recency holdout would
have appeared to work while splitting on nothing. Declaring the schema is also what makes
D-36's choice of parquet worth anything, since the format preserves whatever types it is
handed, inferred ones included.

Choices worth stating: counts (`bedrooms`, `bathrooms`, `views`, `image_count`,
`loc_phase_num`) are nullable `Int64` rather than `int64`, so a future null cannot silently
turn the column to float; low-cardinality strings (`area_unit`, `coord_source`,
`loc_society`, `loc_phase`, `loc_sector`) are `category`, which parquet stores natively and
the tree models consume directly; `created_at` is `datetime64[ns, UTC]`, pinned by an explicit
cast because `to_datetime` infers its resolution on pandas 3 and fixes it at nanoseconds on
pandas 2.

Verified: the frame round-trips through parquet with identical dtypes and identical values.
0.7 MB as parquet against 3.6 MB as CSV.

**D-40 · Locality is decomposed by parsing the address as a path, not per society**

B-08 called for decomposing the large societies. `address` turns out to be an ordered path
from most specific to least — "Block EE, Phase 4, DHA, Lahore, Punjab, Pakistan" — so one
parser handles every society rather than a rule for DHA and another for Bahria Town. Strip
the city, province and country; the final segment is the society and matches `locality` on
8,322 of 8,358 rows; classify what remains by keyword into phase, sector, block, or other.

Emitted as `loc_society`, `loc_phase`, `loc_phase_num`, `loc_sector`, `loc_block`, `loc_sub`
and `loc_path`. 2,295 rows carry a phase, 2,904 a block, 517 a sector; 3,957 have no sub-tier
at all. Cardinality rises from 378 societies to 471 society-phase combinations to 926 full
paths.

No tier is collapsed into another and no granularity is chosen here. Which of the three
levels carries price signal is an EDA question; cleaning's job is to make all three
available. The verbatim phase label is kept alongside the parsed number for the same reason —
"Phase 9 - Town" and "Phase 9" are different places that share a number.

What it buys, on DHA (median PKR per marla, phases with n >= 5):

| phase | n | median | | phase | n | median |
|---|---|---|---|---|---|---|
| Phase 1 | 50 | 3.50M | | Phase XII (EME) | 95 | 4.68M |
| Phase 4 | 40 | 3.63M | | Phase 9 - Town | 150 | 4.80M |
| Phase 3 | 61 | 3.88M | | Phase 8 | 33 | 4.90M |
| Phase 2 | 33 | 3.88M | | Phase 5 | 99 | 5.36M |
| Phase 7 | 296 | 4.13M | | Phase 6 | 348 | 5.64M |

A 61% spread that was previously hidden inside one categorical value, exactly as B-08
predicted.

**D-41 · Locality spellings: five merges, found by normalisation rather than by eye**

Normalising every locality to lowercase alphanumerics collapses exactly three pairs —
High Court/Highcourt Society, Sher Shah/Shershah Colony, Al Kabir/Al-Kabir Orchard. Stripping
the generic suffixes ("Scheme", "Housing Scheme", "Society") collapses two more: Sabzazar
Scheme/Sabzazar and Taj Bagh Housing Scheme/Taj Bagh. 383 values, 9 rows renamed, 378
societies remaining.

B-10 listed three variants, of which one — "Al Kabir/Al-Kabir Orchard" — was correct while
the entry also implied "Al-Kabir Town" belonged with them; it is a separate development. The
same applies to "Sher Shah Road" against "Sher Shah Colony".

Rejected: merging "Sarwar Town" (3) and "Sarwar Colony" (2), which the suffix pass collides.
Town and Colony are different naming conventions and may be different places; 5 rows do not
justify establishing which.

**D-42 · The processed table is split into the analysis set and the excluded rows**

Every step of cleaning carries all 8,459 rows so the arithmetic reconciles against one table
and no row can disappear without appearing in a count. The artefact splits, because the risk
that survives into stages 3–8 is a stage forgetting to filter, and that failure is silent.

`listings.parquet` holds the analysis set and is what everything downstream reads.
`listings_excluded.parquet` holds the dropped rows, each with its `exclusion_reason`. It is
never read by the pipeline; it exists so "why is this listing not in the model" has an answer
that does not require re-running anything. The split asserts that the two halves sum.

Exclusions are flagged rather than applied at the point of detection so that an excluded row
still passes through the locality decomposition — a half-populated row is a poor answer to
"why was this dropped".

**D-43 · The dedup fingerprint is rebuilt on coordinates and the locality path. Amends D-08**

D-08 fingerprinted on locality + area + beds + baths, which put 77.1% of the analysis set
into multi-listing groups and produced one group of 547 rows — the failure B-07 recorded.
Five candidates were measured:

| fingerprint | groups | rows in multi-groups | largest |
|---|---|---|---|
| locality + area + beds + baths (D-08) | 2,877 | 77.1% | 547 |
| coordinates + area + beds + baths | 6,108 | 37.8% | 125 |
| `loc_path` + area + beds + baths | 3,989 | 66.3% | 86 |
| coordinates + `loc_block` + area + beds + baths | 6,428 | 34.2% | 44 |
| **coordinates + `loc_path` + area + beds + baths** | **6,502** | **33.0%** | **44** |

The last is adopted. Rows without a coordinate (95, after D-33) group on the remaining keys,
so no row is left ungrouped.

**D-44 · Price junk: a generous global band, plus a guard on the collapse. Closes B-09**

Three rules, applied to the analysis set only, excluding 39 rows.

*Global band.* A listing whose price per marla is more than ten times the corpus median
(3.67M) away in either direction — outside 367,000 to 36.7M — is not an asking price. The
factor is deliberately generous: it sits 2.8x beyond the 1st percentile and 4.2x beyond the
99th, so it catches rent figures and typos rather than merely unusual houses. 39 rows: 31 at
the low end (PKR 40,000 for a 3 marla house; PKR 500,000 for 2 kanal in Garden Town), 8 at
the high (PKR 4bn for 2.3 kanal; 250M for 2.1 marla).

*Group guard.* Within a fingerprint group, a price more than four times its group median away
is excluded. This catches 4 rows, all of which the global band already catches, so it adds
nothing as a detector — a prediction that the fingerprint would beat the global cut, which
the data did not support. It is kept because it is not a detector but a guard: with a group
of two the median is the mean, so a pair like [100,000, 18,500,000] would collapse under D-45
to 9,300,000, a fabricated price wrong by a factor of two and undetectable afterwards.

*Minimum area.* Below 0.5 marla is not a house. One row, at 0.2 marla (45 sq ft). One marla
(225 sq ft) is a real category in dense Lahore — Tajpura and Sabzazar have them, priced
normally — so the floor sits below it.

The boundary is soft by design. Roughly two dozen rows survive between 400,000 and 1M per
marla; they read as genuinely cheap houses in peripheral schemes rather than as junk, and the
band stops where "not an asking price" ends rather than where "cheap" begins. EDA revisits
with the full distribution in view.

Not recoverable, and recorded because it is the interesting case: id 684395, "2.1 Marla House
on Mian Mehmood Ali Kasoori Road" at 250M, would be entirely plausible as 2.1 *kanal*
(5.95M/marla). Title and payload both say marla, so nothing supports the correction.

**D-45 · Fingerprint groups collapse to one row at the median price. Amends D-08, closes B-06**

Rows sharing a fingerprint share every feature the model will see and differ only in price.
99.8% of multi-listing groups have every listing posted on the same date, against a 1.4%
chance for two random listings — these are single bulk postings, not the relists and
multi-agent duplicates D-08 anticipated. The largest is 44 listings of "6 Marla House, Rose
Block, Park View City" posted in 6 minutes 46 seconds, one title, 24 images on every one, one
URL slug apart from the id, priced in an unbroken 100,000 ladder from 20.0M to 23.0M.

Whether those are one house posted 44 times or 44 identical units of one product cannot be
established from the data, and does not matter: rows with an identical feature vector and
different prices carry one observation of signal between them. Kept, they weight one product
44x in the loss.

Each group therefore becomes one row at the **median** price, carrying `n_listings`.
Median rather than a randomly chosen member: since the rows are identical in every feature,
"which row to keep" reduces to "which price to keep", and a random draw imports that poster's
ladder position into the target as noise. Median is the same operation with lower variance,
and is what D-08 already argued for.

8,319 → 6,467 rows. Above the 3,000 floor of D-05 with room to spare.

**B-06's 15% threshold is retired rather than tuned.** It exists to separate groups safe to
merge from groups that are false merges. Measured, the two do not differ: across every spread
band from 0–5% to 30%+, groups are same-day on 99–100%, carry one distinct title on 93–98%,
and one distinct image count on 73–82%. The widest-spread groups are not false merges — they
are pairs containing one junk price, which D-44 removes first. With no false merges to guard
against, a threshold has nothing to separate. This is the third of PLAN §8's cleaning numbers
to be superseded by measurement, after the 5% stopping rule (D-38).

**The cost, stated plainly.** The held-out set is now made of group medians, so the reported
MdAPE will not include the within-group price variation that no model can resolve: on the
2,755 rows that had replication, the median deviation from their own group median was 3.23%
(p75 7.26%, p90 13.9%). `fp_price_spread` and `n_listings` are carried into the processed
table so validation can disclose that floor quantitatively even though it is no longer
measuring it. Rejected: collapsing the training fold only, which would preserve the
measurement but puts a fold-specific rule into stage 5 that a later reader could get wrong,
and leaves the processed artefact internally inconsistent.

**D-46 · Hand-made corrections live in one auditable table, not in the rules**

`clean.MANUAL_CORRECTIONS` holds corrections that no rule can derive, each with the evidence
that justifies it. Corrections set a **derived** column only — `area`, `area_unit`, `price`
and the rest stay exactly as Ilaan published them, so a correction is a visible override
rather than a rewriting of the source. A correction whose listing is absent, or whose value
is already in place, is reported rather than silently skipped, so a stale entry cannot hide.

This is a deliberate exception to LESSONS L-24, which says cleaning effort goes on
classifying defects and never on adjudicating individual rows. The exception is admissible
only when there is a specific, statable piece of external evidence the data cannot contain —
local knowledge, a comparable, a physical impossibility — and it is recorded with that
evidence attached. **If this table grows past a handful of entries, a rule is missing.**

*One entry.* Listing 684395, "2.1 Marla House for Sale on Mian Mehmood Ali Kasoori Road" at
PKR 250,000,000. Title and payload both say marla, which is 119M per marla and impossible;
D-44 excluded it. Read as 2.1 **kanal** (42 marla) it is 5.95M per marla, against a Gulberg
median of 5.53M and p75 of 7.03M in this dataset — the local comparables land on it almost
exactly. No reading of the price as a typo works: even 25,000,000 would be 11.9M per marla.

Against it: `bedrooms=2` and `bathrooms=3` suit a small house rather than a 2.1 kanal one.
Recorded rather than dismissed, though room counts on this source carry a demonstrated error
rate — D-35 excluded 31 rows with zero bedrooms and 3 with twenty or more.

Nauman's call, 8 Sep 2026, on knowledge of the road. The row returns to the analysis set;
`area_marla` becomes 42.0 and the row carries the `manual_correction` flag.
