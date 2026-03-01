---
name: readme-generator
description: Generates comprehensive README.md files for software projects by analyzing codebase structure
allowed-tools: ["Read", "Glob", "Grep", "Write"]
version: 1.1.0
author: GLINCKER Team
license: Apache-2.0
keywords: [documentation, readme, markdown, project]
---

# README Generator

Automatically generates professional, comprehensive README.md files by analyzing your
project structure, dependencies, usage examples, and marketing prose.

## What This Skill Does

This skill helps you create high-quality README files by:
- Anchoring the framing and tone to a confirmed marketing prose output throughout the
  entire document, not just the opening
- Propagating the confirmed audience, keywords, and all audience cards into the structure
  and content of every section
- Extracting real usage patterns from notebooks in the `/usage` directory
- Analyzing project structure and identifying key components
- Detecting programming languages and frameworks
- Generating appropriate sections with relevant content
- Following README best practices

---

## Instructions

### 0. Priority Inputs (read these first, before anything else)

**Marketing prose output** — look for `repo_marketing_prose.md` in the project root or
outputs directory. If found, extract and hold all of the following in mind for the
entire README, not just the opening section:

- **Confirmed target audience** — every section should be written for this person.
  Their vocabulary, their pain points, their level of familiarity with the tooling.
- **Keyword list** — these terms must appear naturally across the README body: in
  section headings where relevant, in the first sentence of the Usage section, in any
  "When to use this" or workflow descriptions. Do not cluster them in one place.
- **README Hero Section** — use verbatim as the opening. Do not rewrite or paraphrase.
- **Audience Cards (all of them, including unchosen ones)** — read the elevator pitch
  and pain point of each card. Use the primary audience card to drive the "When to use
  this" section. Use the secondary audience card (if one was confirmed) to add a
  secondary workflow. Use any remaining cards to identify use cases worth naming even
  if they are not the lead framing — for example, a RAG audience card means "RAG
  prototype" belongs in the usage examples and keyword appearances even if it is not
  the primary audience.
- **Social share blurb** — the core problem statement here should be echoed in the
  introduction paragraph that immediately follows the hero.

If no marketing prose file is found, ask the user before proceeding. Generating a README
without confirmed positioning produces generic copy that serves no audience well.

**Usage notebooks** — check the `/usage` directory for `.ipynb` files. For each notebook:
- Read the markdown cells for intent and narrative
- Extract code cells as usage examples, preserving the actual API calls
- Note which engines, configurations, or workflows are demonstrated
- Prefer notebook examples over invented ones in the Usage section
- Check each example for completeness: does it show setup, use, AND teardown? If
  teardown (stop, delete, cleanup) is present in the notebook, include it. If it is
  missing from the example but present in the codebase, add it with a note.

---

### 1. Project Discovery

After reading the priority inputs, analyze the project structure:
- Use Glob to find key files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`
- Use Glob to identify main source directories
- Use Read to examine configuration files
- Use Grep to find test files and CI configuration

### 2. Content Analysis

Based on findings, determine:
- Project type (library, application, CLI tool, etc.)
- Primary programming language(s)
- Dependencies and frameworks
- Build and test commands
- License type (from LICENSE file)

---

### 3. README Structure

Build the README in this order. Sections marked **required** must always appear.
Sections marked **audience-driven** must appear if the marketing prose supports them.
Sections marked **optional** appear only if relevant project files exist.

#### [required] Hero
Use the hero section from marketing prose verbatim. Do not alter it.

#### [required] Introduction paragraph
One short paragraph (3-5 sentences) drawn from the social share blurb and the primary
audience card's pain point. This is the narrative bridge between the hero and the
technical content. It should answer "is this for me?" for the confirmed audience.

#### [audience-driven] When to use this
A short section with 3-5 one-liners, one per audience card (primary, secondary, and
any remaining cards that represent valid use cases). Each line names the context and
the payoff. Example format:

- **Teaching a SQL workshop** — seed classroom datasets automatically and skip the
  environment setup section entirely.
- **Comparing databases for an MVP** — switch engines without changing connection code.
- **Local RAG prototype** — spin up a backing store, test it, swap it out in one
  config change.

Order by: primary audience first, secondary audience second, remaining audiences last.
Use the keywords from the marketing prose naturally in these lines.

#### [required] Prerequisites
Software and system requirements.

#### [required] Installation

#### [required] Usage
Lead the section with one sentence that names the confirmed audience and the primary
use case, using keywords from the marketing prose.

Then present a single canonical example drawn from the primary audience's most likely
entry point (for an instructor audience, use PostgreSQL; for an MVP audience, use
whichever engine is most prominent in the notebooks). The example must show setup,
core usage, AND teardown as a complete lifecycle.

After the single example, add a "More examples" subsection that links directly to each
notebook in the `/usage` directory by filename. Do not reproduce the other engine
examples inline — the notebooks are the right place for that detail.

Surface any notably useful capabilities (init scripts, connection string helpers,
engine switching) as named subsections with a brief description and a short snippet
only if the snippet is 5 lines or fewer. Order subsections by relevance to the
confirmed audience, not by implementation order.

#### [optional] Development
How to set up for development. Include only if a dev setup process exists.

#### [optional] Testing
How to run tests. Include only if a test suite exists.

#### [optional] Contributing

#### [required] License

---

### 4. Writing Style

- Clear, concise language
- Active voice
- No em dashes
- Code blocks with proper syntax highlighting
- Badge shields for status indicators (if CI/CD detected)
- No emoji unless user requests
- Tone must match the confirmed audience from marketing prose:

| Audience type | Tone |
|---|---|
| Instructor / educator | Practical, time-saving framing, classroom-aware |
| Enterprise / Azure | Professional, precise, productivity-focused |
| ML / RAG builder | Technical, experiment-friendly, iteration-aware |
| MVP / early-stage builder | Direct, low-overhead, decision-reducing |

---

### 5. Output

Present the generated README to the user and offer to:
- Write it to README.md
- Make adjustments based on feedback
- Add additional sections

---

## Configuration

This skill adapts to project type:

| Project Type | Key Files | Focus Areas |
|---|---|---|
| Python | `pyproject.toml`, `setup.py` | pip install, virtual env |
| Node.js | `package.json` | npm install, scripts |
| Rust | `Cargo.toml` | cargo build, features |
| Go | `go.mod` | go get, modules |
| Generic | None | Basic structure |

## Tool Requirements

- **Read**: Examine configuration, source files, marketing prose, and notebooks
- **Glob**: Find relevant files across project, including `/usage/*.ipynb`
- **Grep**: Search for patterns (tests, CI, etc.)
- **Write**: Create the README.md file

## Limitations

- Cannot include screenshots (user must add manually)
- May miss custom build processes not in standard files
- Generates a starting point - user should review and customize
- Works best with standard project structures
- Does not analyze actual code logic for features

## Error Handling

- **No marketing prose found**: Ask user to run the `repo-marketing-prose` skill first,
  or confirm they want a generic README with no audience targeting
- **No usage notebooks found**: Fall back to docstring examples and quickstart docs,
  note to user that `/usage` notebooks would improve the examples section
- **No project files found**: Ask user to confirm working directory
- **Multiple languages detected**: Generate sections for each, note polyglot nature
- **Existing README**: Prompt user before overwriting, offer to merge
- **Missing key info**: Generate placeholder sections with TODO markers