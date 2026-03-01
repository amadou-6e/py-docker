---
name: repo-marketing-prose
description: >
  Generates SEO-optimised marketing copy for open-source or internal Python repositories.
  Produces a full suite of prose assets: a README hero section, a PyPI / package-index
  long description, GitHub repository "About" one-liner, platform-specific social-share
  blurbs, a keyword-rich meta description for documentation sites, GitHub topic tags,
  and PyPI classifier blocks.
  Use this skill whenever the user wants to make a repository more discoverable, attractive,
  or professional-looking — even if they phrase it as "write a README", "make my repo look
  good", "help me get more stars", "write a description for PyPI", or "how do I market my
  open-source project". Trigger on requests that explicitly touch repo presentation,
  discoverability, or developer audience growth.
---

# Repo Marketing Prose

Generates a cohesive set of marketing and SEO copy for a software repository by reading
the existing project artefacts and synthesising them into prose that is accurate,
developer-friendly, and optimised for search.

---

## Inputs to gather

Before writing, collect as much of the following as is available. Read files directly
from the repository or ask the user to paste them.

| Input | Where to find it | Required |
|---|---|---|
| Project name and tagline | `pyproject.toml`, `setup.py`, existing README | Yes |
| What the project does (one sentence) | README, docstrings, `__init__.py` | Yes |
| Primary user persona | README, docs motivation section | Strongly preferred |
| Key features (3-5 bullet points worth) | README, docs, changelog | Strongly preferred |
| Tech stack / dependencies | `pyproject.toml`, `requirements.txt` | Strongly preferred |
| Existing README | Filesystem | If present |
| Existing docs (motivation, quickstart) | Filesystem or uploaded files | If present |
| Example usage notebooks | `/usage` directory (`.ipynb` files) | Optional |
| Competitor or comparable tools | User input | Optional |
| Target keywords | User input | Optional |

If the user has already shared files in the conversation (e.g. a motivation doc, quickstart,
conf.py), extract what you need from those first before asking.

---

## Outputs to produce

Never add any of these: —

Always produce all seven assets in a single response, clearly separated by headings.
Save them to a single Markdown file so the user can copy-paste from one place.

### 1. README Hero Section
The first ~20 lines of a README. Includes:
- H1 project name with a one-line tagline
- A `pip install {package-name}` code block immediately after the tagline
- A 2-3 sentence elevator pitch (what it is, who it is for, what makes it different)
- A shield/badge line (build, PyPI version, licence) — use placeholder URLs the user
  can fill in
- A short "Why this project?" paragraph (3-5 sentences) that frames the problem,
  positions the tool relative to alternatives, and names at least one comparable tool
  by name if competitors were provided

### 2. PyPI Long Description Intro
A 100-150 word prose block suitable for the top of a `pyproject.toml` description
or a PyPI project page. Must be plain prose (no headers, no bullet lists) because
PyPI renders the full README but search engines index only the first ~150 words.
Front-load the most important keywords naturally.

### 3. GitHub "About" One-Liner
A single sentence of 120-160 characters for the repository's About field.
Must include: what the tool does, primary tech context (e.g. "for Azure Data Factory"),
and one differentiating adjective. No marketing superlatives ("best", "ultimate").

### 4. Social Share Blurbs
Three platform-specific variants. Each mentions the problem it solves and ends with
a call to action.

- **Twitter/X**: Max 280 characters. Punchy, no hashtags unless they are the canonical
  community tag (e.g. `#rstats`). Link at the end.
- **LinkedIn**: 3-4 sentences. Professional tone, can name-drop the tech stack. Ends
  with a question or invitation to comment.
- **Hacker News "Show HN"**: One sentence title in `Show HN: {title}` format, followed
  by 2-3 sentences of plain prose context. No hype. What it does, why you built it,
  where to find it.

### 5. Documentation Meta Description
A 150-160 character string for the `html_meta` or `description` field in Sphinx `conf.py`
or a `<meta name="description">` tag. Must naturally include the project name and primary
use-case keyword.

### 6. GitHub Topics
8-12 lowercase hyphenated tags for the repository's Topics field. Topics are the primary
GitHub browse/discovery mechanism. Include: language (`python`), infrastructure type,
primary use-case, and any framework integrations present in the codebase.
Format as a comma-separated list the user can paste directly into GitHub's Topics field.

### 7. PyPI Classifiers
A ready-to-paste `classifiers = [...]` block for `pyproject.toml`. Include at minimum:
development status, intended audience, licence, programming language versions, and
topic classifiers that match the project's primary use-case. Use only valid
[PyPI trove classifiers](https://pypi.org/classifiers/).

---

## SEO principles to apply

- **Front-load keywords**: The most important search terms (project name, primary verb,
  primary noun) belong in the first sentence of every asset, not buried mid-paragraph.
- **Use the words developers search for**: Prefer "deploy SQL pipelines to Azure Data Factory"
  over "manage your data transformation workflows in the cloud."
- **Be specific over superlative**: "Generates one ADF pipeline per dbt model" ranks and
  converts better than "powerful, flexible solution."
- **Mirror competitor vocabulary**: If users search for "dbt alternative" or "ADF pipeline
  builder", those phrases should appear naturally in the copy. If competitors were provided,
  name at least one in the README hero's "Why this project?" paragraph — developers
  searching for alternatives will find the repo via those names.
- **Avoid keyword stuffing**: Each keyword cluster should appear 2-3 times across the full
  asset set, not repeatedly in a single paragraph.
- **Active voice throughout**: "Deploy your models with one command" not "Models can be
  deployed using a single command."

---

## Tone guidelines

The tone should match the project's apparent audience. Infer from the tech stack:

| Stack signals | Tone | Emoji |
|---|---|---|
| Azure / enterprise tooling | Professional, precise, productivity-focused | Never |
| ML / research libraries | Technical, peer-to-peer, understated | Rarely, only in social blurbs |
| CLI / developer tools | Direct, terse, shows-don't-tells | Never |
| Data engineering | Pragmatic, problem-first, ops-aware | Never |
| AI / LLM developer tooling | Practical, local-first workflow, notebook-centric examples | Occasionally in social blurbs only |

If an existing README is present, match its emoji style exactly — do not introduce or
remove emoji relative to what the author already uses.

Never use: "cutting-edge", "revolutionary", "game-changing", "seamlessly", "leverage"
(as a verb), "robust solution", "best-in-class".

---

## Workflow

The workflow has two mandatory phases. **Do not generate artifacts until the user has
confirmed an audience at the end of Phase 1.**

### Phase 1: Audience Discovery

1. Read all available project files (README, motivation docs, quickstart, pyproject.toml,
   conf.py, __init__.py). Note: the user may have already shared these in the conversation.
2. Check the `/usage` directory for example notebooks (`.ipynb` files). Scan their cell
   sources for concrete usage patterns, API entry points, and real-world use cases —
   these reveal what users actually do with the tool, not just what the author intended.
3. Identify 2-4 plausible audience segments. Think beyond the obvious intended user —
   look for adjacent communities who share the same pain point but arrive from a different
   background or toolchain. For example, a tool built for data engineers might be equally
   compelling to analytics engineers, DevOps teams managing data infrastructure, or
   backend developers new to the data space.
4. For each candidate audience, produce an **Audience Card**:

   ```
   ### Audience: {name}
   Who they are: 1-2 sentences on their role, background, and daily context.
   Their pain point: The specific problem this tool solves for them.
   Why this framing works: What makes the tool compelling to this group specifically.
   Where they gather: 2-4 concrete channels — subreddits, newsletters, Slack/Discord
     communities, conferences, YouTube channels, LinkedIn groups, Hacker News tags, etc.
   Elevator pitch: 2-3 sentences written in the voice and vocabulary of this audience.
   Keywords they search for: 4-6 terms this group would actually type into Google or GitHub.
   ```

5. Present all Audience Cards and ask the user to either:
   - Pick one audience to target exclusively, and confirm or adjust its keyword list
   - Pick a primary and secondary audience (copy will lead with one, not alienate the other),
     and confirm or adjust the combined keyword list
   - Propose a different audience not on the list

   Include the keyword list for each candidate audience in this message so the user can
   adjust them in a single reply. Do not ask for keyword confirmation in a separate step.

### Phase 2: Full Artifact Generation

Only begin after the user has confirmed an audience and keywords in Phase 1.

6. Write all seven assets anchored to the confirmed audience framing and keyword list.
7. Append all Phase 1 Audience Cards (including the ones not chosen) under an
   "Audience Cards Considered" section at the bottom of the output file.
8. Save to `.skill-planning/marketing_prose.md` relative to the project root, and
   present the file path to the user.

---

## Output file format

```markdown
# Marketing Prose: {Project Name}

**Target audience:** {confirmed audience name}
**Keyword targets:** {comma-separated list}

---

## 1. README Hero Section

{content}

---

## 2. PyPI Long Description Intro

{content}

---

## 3. GitHub "About" One-Liner

{content}

---

## 4. Social Share Blurbs

### Twitter/X
{content}

### LinkedIn
{content}

### Hacker News "Show HN"
{content}

---

## 5. Documentation Meta Description

{content}

---

## 6. GitHub Topics

{comma-separated list}

---

## 7. PyPI Classifiers

```toml
classifiers = [
  {entries}
]
```

---

## Audience Cards Considered

> These were the candidate audiences evaluated in Phase 1. Preserved here so you can
> revisit targeting without starting from scratch.

### Audience: {name}
...

### Audience: {name}
...
```
