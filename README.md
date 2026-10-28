# py-docker

General Docker container lifecycle for Python, built on the official Docker SDK.
Development prerelease: not yet published or approved for Laomedo adoption.

```python
from py_docker import Client
from py_docker.containers.models import ContainerSpec

with Client() as client:
    identity = client.containers.create(ContainerSpec(
        image="your-locally-installed-image", name="example-job",
        command=["python", "--version"],
    ))
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

Connection selection: explicit endpoint, explicit context/DOCKER_CONTEXT,
DOCKER_HOST, active CLI context, platform default if Docker CLI is absent.
The selected endpoint is exposed as `client.connection`. Remote plain TCP is
opt-in; TLS and SSH are currently rejected rather than silently ignored. Context
resolution uses read-only `docker context inspect`; container operations use
the SDK. Credential copying is application policy and is not implemented here.

Database helpers and the existing `docker_db` API live in
https://github.com/amadou-6e/pydocker-db. They are separate dependencies.

Pending before release: bounded attach/exec/archive APIs, volume helpers, real
Windows/Linux parity, full independent review and packaging checks. The Python
import `py_docker` does not shadow the official SDK's `docker` import. A missing
PyPI project page does not guarantee name registration.
