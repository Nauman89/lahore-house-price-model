# Project conventions

Read this before writing anything in this repository. It holds three things: how prose is
written, how the project credits AI assistance, and the constraints on working with Nauman's
machine. The planning documents in `project-log/` hold everything else.

---

## 1. Attribution

**Never put `Co-Authored-By: Claude` or a Claude session link in a git commit message.** This
has been added by mistake twice and is not the project's convention.

The project credits AI assistance once, in the README, in these words:

> I used Claude to write code. The source evaluation, the manual accuracy audit and the
> judgement calls are mine. Every decision taken on the project is logged in
> `project-log/decisions/` with the reasoning and the rejected alternatives.

Commit messages describe what changed and why, and nothing else.

---

## 2. Writing

These rules apply to **client facing prose**: `README.md`, `reports/technical-notes.md`,
notebook markdown cells, and the findings deck. They do not apply to internal working files.
`project-log/decisions/`, `project-log/handoffs/`, `STATE.md`, `BACKLOG.md`, `LESSONS.md` and
docstrings stay impersonal, in whatever style suits the job. The subject of a decision entry
is the rule, not the author.

The client facing surface gets its style pass at the end of the project, in one go. Files
written mid project are not retrofitted, and new prose is written to these rules from the
start.

### Absolute

1. **British spelling**: organisation, optimise, modelling, analyse, behaviour, colour,
   licence (noun). Code, library and parameter names keep their own spelling: `normalize`,
   `color=`.
2. **No dashes of any kind** in prose, headings or lists. Use a comma, parentheses, a colon
   or a full stop. Hyphens inside compound words are fine. This applies to markdown and
   notebook markdown cells only, never to `.py` files, where dashes live inside regular
   expressions and string literals.
3. **First person singular**: "I chose", not "we" and not the passive.
4. **No emoji and no badge walls.** There is no banned word list: the guard against
   marketing register is the content rules below, which demand measured numbers, named
   decisions and traceable claims. Prose that carries those does not read as a brochure.

### How Nauman writes

- Start at the answer. The first two sentences say what the project does and its headline
  result, with a number. No "This project aims to", no background before the finding.
- Label things with a plain word: "Data:", "Result:", "Limitation:", "Why not X:". For a
  mixed finding, "The good news:" and "The bad news:".
- Keep sentences short. When one runs long, split it and start the second with "This".
- Turn a paragraph of parallel items into a numbered list.
- Before a long section, say its shape first: "Three decisions shaped the model: 1. ... 2.
  ... 3. ..."
- Cut concluding flourishes. No closing sentence that restates the point, no "In summary",
  no "This demonstrates".
- State limitations as plain facts, with no commentary on his own honesty ("to be
  transparent", "I won't claim otherwise"). State a limitation only where it changes how the
  result can be used, never as a generic disclaimer.

### What the content must carry

This is what stops it looking generated. A model can produce fluent prose about any project.
It cannot produce these.

- Numbers measured in this project, with their denominators: rows, columns, sources, date
  range, the metric on held out data, and the baseline it beats. Never a number that was not
  measured.
- **Every number carries its denominator and the date it was measured**, because a README
  outlives the run that produced it. "MdAPE 10.62% on 8,320 held out listings, measured
  8 September 2026" survives a re-run that moves the figure. "10.62%" does not.
- **Every claim is traceable to a decision or backlog identifier**, so a reader can check the
  prose against the record instead of trusting it. This project numbers its decisions D-01
  onward and its backlog B-01 onward. Cite them.
- Every decision with its reason: why this data source (and what its terms and robots.txt
  said), why this method over the obvious one, what was tried and dropped.
- What went wrong and how it was caught, where something did.
- Only claims that can be explained line by line. If the code does not do it, the prose does
  not say it. Work in progress is described as in progress.
- Data sources credited, with their licence or terms.

### Default README structure

Adjust to the project. Length follows the project: a small analysis gets a short README.

1. Title, then a two sentence summary with the headline number.
2. The question, and why it matters, in one short paragraph.
3. Data: source, licence or terms, size, date range.
4. Approach: the decisions, numbered, each with its reason.
5. Results: the numbers, and a chart if one exists.
6. Limitations.
7. How to run it.

No "Future work" section unless a specific next step is actually planned. This project has a
`BACKLOG.md`, so point at it instead.

### Before handing over any prose

Run the check rather than relying on memory:

```powershell
python scripts\check_prose.py
```

It scans the client facing files for dashes, "we" and American spellings, and exits non zero
if it finds any. `--all` widens it to every markdown file in the repo,
including the internal ones, which is only useful as a survey.

It reported 53 violations on 11 September 2026, the day the rules were adopted: 16 in
`README.md` and 37 in the notebook, every one of them a dash, with `reports/technical-notes.md`
clean because it was the first file written to the rules. That is the expected state. The
client facing pass happens once, at the end of the project, and the count going to zero is
what closes it. New prose is written to the rules from the start, so the number should not
grow.

---

## 3. Working on Nauman's machine

- **He runs every command himself.** Claude writes code, Nauman makes every substantive
  decision and has to understand every line that ships.
- **Never run git commands that write to the index, including `git status`.** The bridge
  shell cannot delete files, so a stale `.git/index.lock` blocks his own git until he removes
  it by hand. Read only git is fine: `log`, `ls-files`, `check-ignore`, `show`. Anything that
  stages, commits, tags or pushes goes to him as a PowerShell block.
- **Never create scratch or test files in the project folder**, for the same reason. Use the
  bridge shell's own `$HOME`, outside the mounted folder, or the cloud workspace.
- **A successful file write result is not evidence the file changed.** Verify with a checksum
  before asking him to run anything against it. This cost a wasted test run on 8 September
  2026.
- **The bridge shell is Linux and the project `.venv` is Windows.** `.venv/Scripts/python.exe`
  cannot run there. Anything needing the project's dependencies is a script he runs in
  PowerShell.
