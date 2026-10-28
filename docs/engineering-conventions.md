# Engineering conventions

This package follows the owner's `my-skills/05-software_engineering` guidance,
using guidance at skill revision `678a922458ba34e76c58bbdedb105c17629e9ee3`.
The applicable code, refactoring and formatting sources are linked in AGENTS.md.
Requirements, UI and experimentation workflows are applied when that work is
actually requested; this library alignment does not invent a UI or experiment.

## Contracts and behavior

Feature models live in `models.py`. Every field describes purpose, units and
interpretation. Bind mounts are `BindMount` records rather than nested untyped
dictionaries. Callers can still supply the existing bind dictionaries to
`ContainerSpec`; `sdk_volumes()` projects their explicitly supplied options back
to Docker without adding an absent mode. Docker's mode and propagation syntax
and Windows host path keys are preserved. Python readers now use typed records
such as `spec.volumes[source].bind`; general Pydantic dumps may include declared
model defaults. There is no published persisted ContainerSpec schema to migrate.

Environment, labels and tmpfs remain typed maps because their arbitrary keys are
part of Docker's protocol, not missing record fields. Captured binary output and
ownership secrets stay excluded from serialization and representation. Live SDK
clients, locks and socket handles remain behavior/service resources; they are
not serialized into Pydantic records. Third-party Container/Image/Volume objects
are explicitly typed SDK boundaries, and their inspection dictionaries stay at
that boundary rather than being duplicated into an entire Docker Engine schema.

Stream byte allowance and deadline travel together in a private StreamBudget
model. Budget transitions stay on that model; socket reads, writes and cleanup
stay on AttachedStream. Execution uses the public remaining_seconds() method
rather than reaching into another object's private helper. Raw transport Any
is confined to the SDK's differing Unix and Windows socket adapters and SDK
variadic forwarding; no unused Protocol/base class is introduced to hide that.

## Configuration and layout

Externally supplied connection settings use BaseSettings with described fields
and explicit constructor-only sources. The supported PY_DOCKER_ values are read
from the supplied snapshot; an empty snapshot cannot fall back to the process
environment. Docker's own host/context variables retain their separate selection
rules, and remote permission remains an explicit method argument.

All process-environment reads live in connection/settings.py. Fixed sandbox,
framing, ownership and polling defaults live in owning settings.py modules. The
existing ten-second context-inspection limit remains a constant; this alignment
does not add a new environment option or relax sandbox defaults.

No reusable abstract interface is needed yet. A future one belongs in base.py
with a Base-prefixed name. Concrete SDK subclasses and exception families keep
their existing defining modules and error codes. There is no dataclass or mixed
class/function implementation module. Independent helpers, when needed, belong
in their feature's utils.py rather than a global utility collection.

The library has dependency ranges and no pre-existing lockfile. This refactor
does not invent a deployment lockfile; consumers such as Laomedo must pin reviewed
versions and hashes in their own lockfile. Pydantic and pydantic-settings remain
direct runtime dependencies. Ruff is a test/development dependency.

## Checks

```text
python -m pip install -e .[test]
python -m ruff check src test_suite
python -m ruff format --check src test_suite
python -m pytest -m "not integration"
```

Set PY_DOCKER_TEST_IMAGE to an already installed image containing python3, then
run `python -m pytest -m integration`. The library never pulls an image as a
side effect. Hosted integration CI explicitly pulls its pinned test image.

Ruff enforces import, formatting and NumPy docstring rules. Structural controls
check described fields, model/settings placement, cohesion, method order,
dataclasses, environment access and test layout. These guards are syntactic:
field-description word counts cannot prove meaning, and the Path division check
only detects direct construction and parent expressions, not every typed variable.
Code review remains responsible for semantic documentation and indirect patterns. Boundary tests compare typed
bind projections with the actual SDK conversion and check Client snapshot
isolation. Internal controls and fault injection are distinct from real Docker
acceptance. Neither category establishes a working Laomedo agent graph.
