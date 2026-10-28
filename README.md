# py-docker

General Docker container lifecycle for Python, built on the official Docker SDK.
Development prerelease: not yet published or approved for Laomedo adoption.

```python
from py_docker import Client
from py_docker.containers.models import ContainerSpec

with Client() as client:
    identity = client.containers.create(
        ContainerSpec(
            image="your-locally-installed-image",
            name="example-job",
            command=["python", "--version"],
        )
    )
    try:
        client.containers.start(identity)
        result = client.sdk.containers.get(identity.id).wait(timeout=30)
    finally:
        client.containers.remove(identity, force=True)
```

Creation resolves a local image to its immutable ID; it never pulls, builds or
replaces an existing named container. Removal validates ID, name and ownership
labels. The SDK remains available as `client.sdk` for other Engine operations;
operations through that escape hatch have the SDK's own contracts.

For recoverable creation, call `reservation = client.containers.reserve(spec)`
before `create(spec, reservation)`. A `CreationUnconfirmedError` also carries
its private receipt. Reconcile that receipt before retrying; a timeout may mean
Docker created the resource. Volume create errors likewise retain a receipt.
Operation phase text is diagnostic wording, not a stable API; use exception
types and their machine `code` for programmatic handling.
Container creation disables Docker config proxy injection and reads back the
requested sandbox, process configuration, bind mounts and environment.

Connection selection: explicit endpoint, explicit context, DOCKER_CONTEXT or
DOCKER_HOST, active CLI context, platform default if Docker CLI is absent.
Simultaneous DOCKER_CONTEXT and DOCKER_HOST environment settings are rejected
unless the caller selects an explicit endpoint/context. This avoids relying on
different CLI/SDK versions' precedence behavior during a mixed migration.
The selected endpoint is exposed as `client.connection`. Remote plain TCP needs
the explicit `Client(allow_remote=True)` argument; an environment variable cannot
grant that permission. `Client(environment=snapshot)` isolates library settings
from the ambient process environment. TLS and SSH are currently rejected rather
than silently ignored. Context
resolution uses read-only `docker context inspect`; container operations use
the SDK. Credential copying is application policy and is not implemented here.

Database helpers and the existing `docker_db` API live in
https://github.com/amadou-6e/pydocker-db. They are separate dependencies.

Attach and exec return binary frames with output limits and monotonic stream
deadlines. API acquisition/inspection has a separate client timeout; this is not
an end-to-end command deadline. Closing an attach socket does not stop the
container, and there is no cross-platform stdin half-close guarantee. Fresh,
unique volume creation verifies its ownership token; generic volume deletion is
not exposed because volumes lack immutable IDs. Applications own credential
selection, lease supervision and recovery UI.

Container removal preserves anonymous volumes by default. Opt in to removing
them with `remove_anonymous_volumes=True` for an exclusively owned container.
Suppressed exception chains remain available in memory via Python's exception
context; only safe library messages should be presented or logged.

Archive helpers and an end-to-end command deadline are outside this first
prerelease: use SDK APIs with their own contracts until dedicated wrappers are
reviewed. Library stream and cleanup tests do not establish agent acceptance.
The Python
import `py_docker` does not shadow the official SDK's `docker` import. A missing
PyPI project page does not guarantee name registration.
