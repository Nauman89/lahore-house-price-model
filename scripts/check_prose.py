"""Check client facing prose against the conventions in CLAUDE.md.

Usage, from the repository root::

    python scripts/check_prose.py          # the client facing files
    python scripts/check_prose.py --all    # every markdown file in the repo
    python scripts/check_prose.py README.md reports/technical-notes.md

Exits 0 when nothing is found and 1 when anything is, so a stage close can depend on it.

There is deliberately no banned word list. Marketing register is caught by what the prose has
to carry (measured numbers, named decisions, traceable claims) rather than by a word filter,
which flags legitimate technical usage and misses the actual problem.

Scope is deliberate. Only markdown and the markdown cells of notebooks are checked: a `.py`
file carries dashes inside regular expressions and string literals, and rewriting those would
break code to satisfy a style rule. The internal working files under `project-log/` are not
client facing and are not checked unless `--all` is passed, which is expected to fail until
the end of project pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: What a reader meets. Everything else in the repo is internal (CLAUDE.md section 2).
CLIENT_FACING = (
    "README.md", "reports/technical-notes.md", "notebooks/01_eda.ipynb",
    "notebooks/02_features.ipynb",
)

#: American spellings that turn up in this kind of writing. Not exhaustive, and not meant to
#: be: it catches the ones that actually recur.
AMERICAN = (
    "optimize", "optimized", "optimizing", "optimization", "normalize", "normalized",
    "analyze", "analyzed", "analyzing", "behavior", "color", "modeling", "labeled",
    "organization", "organize", "recognize", "summarize", "visualize", "center",
    "favorite", "catalog", "defense", "license to",
)

#: First person plural. The prose is published under one name.
PLURAL = ("we ", "we'", "our ", "ours ", "us ")

DASHES = {"—": "em dash", "–": "en dash", "−": "minus sign"}

#: Inline code, fenced code and links are exempt: `color=` is a parameter name, not a spelling
#: mistake, and a URL may contain anything.
CODE_SPAN = re.compile(r"`[^`]*`|```.*?```|\]\([^)]*\)", re.DOTALL)


def strip_code(text: str) -> str:
    """Blank out code spans and link targets, preserving offsets so line numbers stay true."""
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), text)


def prose_of(path: Path) -> str:
    """Return the prose of a markdown file, or of a notebook's markdown cells."""
    if path.suffix != ".ipynb":
        return path.read_text(encoding="utf-8")
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = [c for c in notebook.get("cells", []) if c.get("cell_type") == "markdown"]
    return "\n".join("".join(c.get("source", "")) for c in cells)


def findings(path: Path) -> list[tuple[int, str, str]]:
    """Every violation in one file, as (line number, rule, the offending text)."""
    found: list[tuple[int, str, str]] = []
    for number, raw in enumerate(prose_of(path).splitlines(), start=1):
        line = strip_code(raw)
        lowered = line.lower()
        for char, name in DASHES.items():
            if char in line:
                found.append((number, name, raw.strip()[:90]))

        for word in AMERICAN:
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                found.append((number, f"American spelling: {word}", raw.strip()[:90]))

        for word in PLURAL:
            if lowered.startswith(word) or f" {word}" in lowered:
                found.append((number, "first person plural", raw.strip()[:90]))
    return found


def main() -> int:
    """Check the requested files and report. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true",
                        help="every markdown file in the repo, internal ones included. "
                             "Expected to fail until the end of project style pass.")
    args = parser.parse_args()

    root = Path.cwd()
    if args.paths:
        targets = args.paths
    elif args.all:
        targets = sorted(p for p in root.rglob("*.md")
                         if not any(part in {".venv", ".git", "node_modules"} for part in p.parts))
    else:
        targets = [root / name for name in CLIENT_FACING]

    total = 0
    for path in targets:
        if not path.exists():
            print(f"  {path}: not found, skipped")
            continue
        hits = findings(path)
        total += len(hits)
        label = f"{path.relative_to(root) if path.is_absolute() else path}"
        print(f"{'FAIL' if hits else ' ok '}  {label}  ({len(hits)} found)")
        for number, rule, text in hits[:40]:
            print(f"        line {number:>4}  {rule:<28}  {text}")
        if len(hits) > 40:
            print(f"        ... and {len(hits) - 40} more")

    print(f"\n{total} violation(s) across {len(targets)} file(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
