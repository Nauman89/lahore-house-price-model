# STATE

**Updated:** 2 Sep 2026

**Active stage:** 0 — Planning & setup (milestone Thu 3 Sep)

## Done

- Intake complete. Scope, acceptance criteria, stopping rules, environment and timeline agreed.
- PLAN.md written and signed off.
- Decisions D-01 to D-19 logged.
- Repo skeleton created: licence, gitignore, gitattributes, pyproject, README, package and data trees.
- Environment verified on the machine: git 2.55, uv 0.11.30, git identity configured. `gh` not installed.

## Files

```
README.md                 client-facing, phase-aware; states the asking-price limitation
LICENSE                   MIT — code only; data remains under the source's terms
pyproject.toml            Python 3.13 pin, full dependency set, ruff config
.gitignore                data/raw, interim, processed excluded; data/sample committed
.gitattributes            eol=lf — Windows dev, Linux deploy
.env.example              placeholder for a geocoding key if one is needed
src/lhp/                  package skeleton (scrape subpackage), no modules yet
data/                     raw/cache, interim, processed, sample — all empty
notes/README.md           index for reference notes
project-log/              PLAN, STATE, BACKLOG, decisions/01-planning.md
```

No venv, no lockfile, no git repo yet. No code written.

## Next action

1. Nauman runs the stage-0 setup commands: `uv venv`, `uv sync`, export `requirements.txt`,
   `git init`, first commit, create and push to GitHub as `lahore-house-price-model`.
2. Claude produces the candidate source shortlist with the clauses and robots.txt paths to check.
3. Nauman checks the sources and reports the findings. That is the gate on stage 1.

## Blockers

- Data source not selected. Stage 1 cannot begin until terms and robots.txt have been checked
  by Nauman and the finding recorded.
