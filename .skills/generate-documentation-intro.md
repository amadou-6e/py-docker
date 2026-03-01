---
name: sphinx-intro-docs
description: >
  Generates the introductory Sphinx documentation section for a Python repository:
  a landing page and a quickstart guide. Anchors both files to the confirmed audience
  and framing from a marketing prose output, and derives quickstart examples directly
  from usage notebooks rather than inventing them.
  Use this skill whenever the user wants to create or improve the introductory part of
  their Sphinx docs, set up a docs landing page, write a getting-started guide, or
  produce the human-readable entry point to an API reference site. Trigger even if the
  user phrases it as "write the intro for my docs", "make a quickstart page", or
  "set up the first page of my documentation".
---

# Sphinx Intro Docs

Generates two files that form the introductory layer of a Sphinx documentation site:
a landing page and a quickstart guide. Both are derived from existing project artefacts
rather than written from scratch, ensuring the docs stay consistent with the README and
marketing positioning.

---

## Inputs to gather

Read these before writing anything. They are listed in priority order.

| Input | Where to find it | Required |
|---|---|---|
| Marketing prose output | `repo_marketing_prose.md` in project root or outputs dir | Yes |
| README.md | Project root | Yes |
| Usage notebooks | `/usage/*.ipynb` | Strongly preferred |
| Existing Sphinx conf.py | `docs/conf.py` | Preferred |
| Existing toctree structure | `docs/index.rst` or `docs/introduction.rst` | If present |

If no marketing prose file is found, ask the user to run the `repo-marketing-prose`
skill first. The landing page without confirmed positioning will default to generic copy
that serves no audience.

If no usage notebooks are found, fall back to the README usage section, but flag this
to the user — the quickstart will be weaker without runnable notebook examples.

---

## What to extract from each input

**From marketing prose:**
- Confirmed target audience and any secondary audience
- Keyword list
- Hero section (use verbatim on the landing page)
- Elevator pitch for each audience card — these inform the "Who is this for" section
- "Where they gather" from each card — useful context for tone but not written into docs

**From README.md:**
- The single canonical usage example — reuse it in the quickstart rather than
  rewriting it. Keep the code identical; only adjust surrounding prose if needed.
- The "When to use this" one-liners — adapt (do not copy verbatim) for the landing page
- Prerequisites and installation steps — copy these exactly into the quickstart

**From usage notebooks:**
- Read markdown cells to understand the narrative arc of each notebook
- Extract the first complete workflow from the most beginner-friendly notebook
  (prefer a notebook named `quickstart`, `intro`, or `example` over engine-specific ones)
- Note any "what next" or "see also" references at the end of notebooks — use these
  to populate the "Next steps" section of the quickstart

---

## Phase 1: Landing Page

### File
Produce `docs/introduction.rst` (or `.md` if the project uses MyST — check `conf.py`
for `myst_parser` in extensions).

### Structure

```
[Hero section from marketing prose — verbatim]

Who is this for
---------------
Short paragraph per confirmed audience (primary first, secondary second).
Draw from the audience card elevator pitches. 2-3 sentences each.
Do not list features here — this section answers "is this for me?".

What you can do with {project name}
------------------------------------
Adapt the "When to use this" one-liners from the README into a slightly fuller
form — one short paragraph per use case, not a bullet list.
Each paragraph should name the context, the action, and the payoff.
Use keywords from the marketing prose naturally.

Where to go next
----------------
A toctree or a short set of links:
- Quickstart (link to quickstart page)
- API Reference (link to modules page if it exists)
- Usage notebooks (link to /usage directory or rendered notebook pages)
Keep this section minimal — it is navigation, not content.
```

### Tone
Match the confirmed audience tone from the marketing prose. The landing page sits
between the README (persuasive) and the quickstart (instructional) — it should feel
welcoming and orienting, not salesy and not yet technical.

---

## Phase 2: Quickstart Guide

### File
Produce `docs/quick_start.md` (MyST) or `docs/quick_start.rst` depending on project
setup. Check `conf.py` — if `myst_parser` is in extensions, use `.md`.

### Structure

```
# Quickstart

One sentence: what the reader will have working by the end of this page.

## Prerequisites
[Copy exactly from README prerequisites section]

## Installation
[Copy exactly from README installation section]

## Your first {project name} workflow
[Single canonical example from README, identical code]
Brief prose before the code block explaining what is about to happen.
Brief prose after explaining what just ran and what the output means.

## What just happened
2-4 sentences explaining the pattern the example demonstrated — config, create,
connect, teardown in the case of py-dockerdb. This is the one place where a
core concept is introduced, but only the concept directly visible in the example.
Do not introduce abstractions that are not in the code block.

## Next steps
- Link to each usage notebook by name with a one-line description of what it covers
- Link to the API reference if it exists
- Link to any configuration or debug guides if they exist
```

### On the code example
Use the identical code from the README canonical example. Do not simplify, shorten,
or abstract it — a quickstart that runs is more valuable than one that is tidy.
If the example requires a teardown step, include it and note why (leaked containers,
cleanup, reproducibility — whatever is relevant to the confirmed audience).

### Tone
Instructional and direct. The reader has committed to trying the tool. Minimize
explanation before the first code block — they want to run something, not read.
Save explanation for after the code has run.

---

## Output files

Save both files to the `docs/` directory (or wherever the existing Sphinx source
files live — check `conf.py` for `source_dir` if present).

After generating both files, update the toctree immediately so the pages appear in
sidebar navigation on the next build. Do not leave this to the user.

Find the relevant toctree file — typically `docs/index.rst` or `docs/introduction.rst`.
If an `introduction.rst` toctree exists, add entries there. If only `index.rst` exists,
add them there. If neither exists, create a minimal `introduction.rst` that wraps both
files and add a reference to it in `index.rst`.

Add entries in this order: landing page first, quickstart second:

```rst
.. toctree::
   :maxdepth: 2

   introduction
   quick_start
```

If the toctree already has entries, insert the new ones at the top of the relevant
toctree block so the intro section leads the navigation.

After updating, tell the user exactly which file was modified and what was added.

---

## Writing style

- No em dashes
- Active voice
- No marketing superlatives ("powerful", "robust", "seamless")
- RST: use underline-only headings (`===`, `---`, `~~~`) consistent with existing files
- MyST: use standard `#` heading hierarchy
- Code blocks must specify language (` ```python `, ` ```bash `, etc.)
- Cross-references to other doc pages use `:doc:` in RST or relative links in MyST