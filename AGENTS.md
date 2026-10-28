# Package instructions

Preserve the database history in amadou-6e/pydocker-db. This repository now
builds the general py-docker distribution and imports as py_docker.

Apply the owner's [code skill](https://github.com/amadou-6e/my-skills/blob/678a922458ba34e76c58bbdedb105c17629e9ee3/05-software_engineering/skill-code/SKILL.md),
[refactoring skill](https://github.com/amadou-6e/my-skills/blob/678a922458ba34e76c58bbdedb105c17629e9ee3/05-software_engineering/skill-code/skill-refactor_code/SKILL.md)
and [formatting skill](https://github.com/amadou-6e/my-skills/blob/678a922458ba34e76c58bbdedb105c17629e9ee3/05-software_engineering/skill-code/skill-format_code/SKILL.md).
In the owner's workspace the current sources live under
`../my-skills/05-software_engineering`; inspect newer owner instructions when supplied.

Keep feature-owned models.py/settings.py/errors.py; implementation files define
classes or standalone functions, never both. Prefer methods for owned behavior.
Give every Pydantic field a meaningful description; keep nested records typed.
Document modules, classes, constructors, methods and helpers with NumPy-style
docstrings. Order dunders, properties, public methods and private helpers in that
sequence. Keep reusable Base-prefixed interfaces in base.py only when needed.
Use Path(parts...) or joinpath, never pathlib division. Tests live in test_suite/.
Run Ruff check/format checks and the structural regression controls before handoff.
Runtime configuration reads belong in settings.py; inject explicit validated
settings and preserve supplied-environment isolation. Fixed sandbox defaults may
not become ambient environment overrides.
Never expose credentials, raw daemon errors or command output in exceptions.
No implicit pull/build/recreate/prune. Destructive operations require exact
resource identity and ownership verification. Document uncertain outcomes.

Commit and push coherent checkpoints. Claude review is required before merge
or publication; reuse the parent workspace reviewer session. Unit fixtures
do not establish real Docker/agent acceptance. Publish only reviewed artifacts
after packaging and real integration checks, without exposing upload keys.
