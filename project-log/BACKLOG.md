# BACKLOG

Open items, deferred work, known limitations. Tagged by stage and severity.

| ID | Stage | Severity | Item |
|---|---|---|---|
| B-01 | Modelling | low | Quantile regression models for prediction intervals. Rejected for v1 in favour of held-out residual quantiles (D-11). Revisit if the residual-quantile interval proves poorly calibrated across price bands |
| B-02 | Reporting | low | Power BI market dashboard — price per marla by locality, supply mix, size distributions. Rejected for v1 (D-06). Possible phase 2 and a separate portfolio piece |
| B-03 | Modelling | medium | Recency holdout instead of random split, if listings carry a usable posting date. Decide at modelling stage |
| B-04 | Acquisition | medium | Latitude/longitude availability unknown until source evaluation. If absent, fallback is geocoding distinct locality names into a committed lookup table |
| B-05 | EDA | high | Acceptance criteria are provisional until locked at EDA close (D-09). Must not reach validation unlocked |
| B-06 | Cleaning | medium | 15% price-spread threshold for collapsing near-duplicate groups is provisional. Validate against real spread distribution at cleaning stage |
