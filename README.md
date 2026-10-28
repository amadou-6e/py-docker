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
        exit_code = client.containers.wait(identity, timeout=30)
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

## Interactive container sessions

`client.sessions.open(ContainerSession(spec=spec, limits=limits,
receipt_path=private_state.joinpath("session.json")))` returns a creator-owned
`Session`. Supply an immutable image ID, explicit stream limits and an existing
private state directory. Set `stdin_open=True` only when the caller writes input;
output-only services leave it false. Creation attaches both output channels and
optional stdin before starting the container. `write(bytes)` sends stdin;
`read_frame()` returns undecoded stdout/stderr frames. One reader and serialized
writers share the original lifetime and combined byte budget.

`read_line()` is an alternative to frame mode: it preserves channel and newline
bytes, buffers split frames, and returns final unterminated output before EOF.
Choose one mode per session; decoding and application protocols remain with the
caller. `exited()` checks process state after EOF and rejects a still-running
process rather than reporting success. Closing on the creator thread removes the
exact container before detaching and unblocks a concurrent reader.

`client.containers.watch(reservation)` supervises an exact private reservation on
that client's endpoint. `inspect()` returns safe observation categories;
`cleanup(watch_seconds=...)` removes only verified immutable IDs. A loss watch
that never observes a container remains unverified even if the name is absent.
It never resolves an unknown create through a timed-absence shortcut.

`state()` returns a validated `ContainerState`; removal never invents an exit
code. `wait(timeout)` confirms exit independently. `terminate()` may run from
another thread and removes only the verified immutable ID. It deliberately
leaves the receipt for `close()` on the creator thread, which confirms removal,
clears intent, detaches and releases its native lock. Keep the Client open for
the entire session. Closing an attachment alone never establishes termination.
`session.cleanup_confirmed` becomes true only after creator-thread removal,
receipt clearing and stream closure all succeed. Application supervision can
reuse that confirmation instead of issuing a second normal-path cleanup.
If close fails, subsequent close calls re-raise the saved safe failure; they do
not turn that attempt into a silent success or issue duplicate cleanup requests.

Job and session receipts include the original resolved daemon endpoint. Recovery
refuses missing or mismatched endpoint information before inspecting or removing
anything, retaining the receipt. Legacy records without endpoint provenance
require explicit host reconciliation; the library never guesses the daemon or
silently fills in missing provenance. Use the original endpoint for recovery.

`ContainerSpec` also supports an init process, a CPU quota in nanocpus, explicit
host aliases and loopback-only published ports such as `ports={"4096/tcp": None}`.
These options are checked against creation readback. After start,
`client.containers.published_port(session.identity, "4096/tcp")` returns the
observed host port only when the exact owned container has one IPv4 loopback
binding. Wildcard and externally reachable bindings are refused.

Windows named pipes cannot half-close stdin while retaining output. For commands
that require EOF, callers can bind a private input file read-only and redirect
stdin inside their explicit command. The library does not interpret input files
or introduce a shell. Never put request contents or credentials in command args.

`client.jobs.run(job, cancelled=stop_event)` optionally accepts a caller-owned
`threading.Event`. Setting it stops the job's observed owned container; it does
not wait for the command's own deadline or undo earlier effects. The creator
thread confirms cleanup through the same Session lifecycle. A confirmed stop
raises `JobCancelledError`; uncertain cleanup retains the receipt and takes
precedence as `CleanupUnconfirmedError`. Pre-cancelled jobs send no launch.
A stop racing process completion wins if it is observed before `run` returns;
this conservative outcome never means that earlier effects were undone.

After verified creation, jobs and sessions atomically record the observed
immutable ID in their private receipt. Recovery can then safely accept that ID's
confirmed absence, including removal by an independent application supervisor.
Legacy intent-only records remain readable and retain conservative unknown-create
handling. Failed observation persistence retains the earlier intent. Applications
must recover per-run receipts on the original endpoint before dispatching anew.

`ContainerSpec.mounts` supports typed bind and named-volume `Mount` records. These
use Docker's explicit Mounts API and check bind sources on the client host before
dispatch: a missing source is refused rather than silently created by Docker
Desktop. These mounts require local client-visible sources, including when an
explicit remote endpoint is selected. Callers own source-directory stability
between validation and dispatch. Existing `volumes` retains its original bind
semantics. Interactive stdin uses SDK attached-stdin defaults, verified by
`OpenStdin` and `StdinOnce` readback; no independent half-close API is promised.
Readback permits an omitted false `ReadOnly` and, only on the local Windows
named-pipe adapter, Docker Desktop's `/run/desktop/mnt/host/<drive>/...` spelling
of the same absolute Windows source. Other source/target/permission changes and
additional mount options remain failures; remote endpoints do not get this path
translation. Real missing-source and external-removal recovery checks complement
the internal normalization controls.

## One-shot container jobs

`client.execution.run` executes inside an existing owned container.
`client.jobs.run` creates and removes a separate one-shot container, returning
binary stdout/stderr and a confirmed exit code after cleanup. Supply an
immutable local image ID, noninteractive `ContainerSpec`, explicit stream and
wait limits, and a receipt path inside an existing private runtime directory:

```python
from pathlib import Path

from py_docker import Client
from py_docker.containers.models import ContainerSpec
from py_docker.jobs.models import ContainerJob
from py_docker.streams.models import StreamLimits

private_state = Path(
    "/existing/private/runtime"
)  # Replace with your private state directory.
with Client() as client:
    image_id = client.images.resolve("your-locally-installed-image")
    result = client.jobs.run(
        ContainerJob(
            spec=ContainerSpec(
                image=image_id, name="unique-job-name", command=["python", "--version"]
            ),
            limits=StreamLimits(seconds=20, max_bytes=65536),
            receipt_path=private_state.joinpath("job.json"),
            wait_timeout_seconds=20,
        )
    )
```

Image/version authorization stays with the application; call `images.resolve`
with its `expected_id` when a tag must match an application pin. Jobs never pull
or retry creation, reject interactive stdin/TTY requests, attach before start,
and count both output channels against one budget. API, stream and wait limits
are separate; there is no total wall-clock deadline. A nonzero exit is returned
as a result. A timeout/output-limit error still triggers exact forced cleanup.

Receipt files contain private ownership labels. Normal model dumps omit them;
`to_private_record`/`from_private_record` are explicitly private conversions.
The store creates no directories and writes exclusively with POSIX mode 0600;
Windows privacy relies on the caller's directory ACLs. A native inter-process
file lock covers recovery, execution and cleanup. Concurrent use fails with
`ReceiptInUseError` before changing any receipt or sending a job operation;
the empty sibling `.lock` file may remain and must not be deleted during use.
Unsupported soft-lock backends and symlink receipt/lock paths are refused.
Lock contention is a separate `DockerOperationError`, not cleanup uncertainty:
the other caller may still be running. One store belongs to one thread.

Call `client.jobs.recover(receipt_path)` to reconcile an earlier job explicitly;
`run` also recovers before reserving a new job. No receipt is a no-op. An observed
matching owned ID is removed before its receipt is cleared. Absence after an
uncertain create does not prove an old request cannot arrive later, so absence,
conflict, corrupt records and daemon uncertainty retain the receipt and raise
`CleanupUnconfirmedError`. That error overrides a safe primary execution error,
available in `error.primary`; neither output, paths nor raw daemon text are
included in library messages. A receipt-unlink failure also fails conservatively.

For manual recovery, stop the original client and keep its selected endpoint.
Resolve outstanding create requests before clearing anything; if that cannot
be proved, a local engine restart must be coordinated with other active work.
Then inspect the saved name and labels privately, remove only a matching owned
immutable ID, and clear the receipt only after confirmed absence with no pending
create. Never log/share ownership labels, delete a live lock file or blindly
retry a job. These are local single-owner receipts, not a distributed supervisor.

Typed pre-request failures clear only their own unstarted receipt. The create
endpoint's documented 400 (bad parameter), 404 (missing image) and 409 (conflict)
responses raise `CreationRejectedError` and also clear that intent without
deleting any existing resource. Timeout, throttling, server errors, unknown
responses and all post-create readback failures remain uncertain. No error-text
parsing or whole-status-family inference is used. The contract follows the
[Docker create API](https://docs.docker.com/reference/api/engine/version/v1.51/).

This `0.1.0a3` local-trial increment retains `filelock` as a runtime dependency for
native inter-process exclusion; there is no custom platform lock implementation.

## Connection and lifecycle boundaries
Operation phase text is diagnostic wording, not a stable API; use exception
types and their machine `code` for programmatic handling.
`Images.resolve` raises `ImageResolutionError` when local inspection fails,
without claiming that the image is missing. An observed pin mismatch remains
`OwnershipConflictError`. Neither operation pulls or launches a container.
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
