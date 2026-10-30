"""Explicit attach/exec APIs. No retry if the execution outcome is uncertain."""

import time

from docker import DockerClient
from docker.errors import DockerException
from requests.exceptions import RequestException

from py_docker.connection.deadline import RequestDeadlineScope
from py_docker.containers.models import ContainerIdentity
from py_docker.containers.service import Containers
from py_docker.errors import DockerOperationError
from py_docker.execution.models import CommandResult
from py_docker.execution.settings import EXIT_STATUS_POLL_SECONDS
from py_docker.streams.models import StreamLimits
from py_docker.streams.socket import AttachedStream


class Execution:
    """Control requests use the client timeout; acquired streams use StreamLimits.

    Parameters
    ----------
    sdk : DockerClient
        Existing Docker SDK session; the caller owns its lifetime.
    """

    def __init__(self, sdk: DockerClient) -> None:
        """Reuse the SDK session for ownership checks and command transport."""
        self.sdk = sdk
        self.containers = Containers(sdk)

    def attach(
        self, identity: ContainerIdentity, limits: StreamLimits, *, stdin: bool = False
    ) -> AttachedStream:
        """Attach to an owned non-TTY container with a bounded output stream.

        Parameters
        ----------
        identity : ContainerIdentity
            Exact resource identity and expected private ownership labels.
        limits : StreamLimits
            Validated combined output-byte limit and acquired-stream lifetime.
        stdin : bool
            Whether the attachment should accept request bytes on container stdin.

        Returns
        -------
        AttachedStream
            Acquired stream; the caller must close it and separately reconcile remote work.

        Raises
        ------
        OwnershipConflictError
            Ownership inspection failed; no attachment was requested.
        DockerOperationError
            Inspection failed, the container is absent or uses TTY, or attachment failed.
        """
        container = self.containers.inspect(identity)
        if container is None or container.attrs.get("Config", {}).get("Tty"):
            raise DockerOperationError("attach existing non-TTY container")
        try:
            raw = self.sdk.api.attach_socket(
                identity.id,
                params={
                    "stdin": stdin,
                    "stdout": True,
                    "stderr": True,
                    "stream": True,
                    "logs": False,
                },
            )
        except (DockerException, RequestException):
            raise DockerOperationError("attach container") from None
        budget = RequestDeadlineScope.current(self.sdk.api)
        stream = AttachedStream(
            raw, limits, deadline=budget.deadline if budget else None
        )
        try:
            if budget:
                budget.remaining_seconds(time.monotonic())
        except DockerOperationError:
            try:
                stream.close()
            except DockerOperationError:
                pass
            raise
        return stream

    def run(
        self, identity: ContainerIdentity, command: list[str], limits: StreamLimits
    ) -> CommandResult:
        """Execute once and confirm binary output and process exit status.

        Parameters
        ----------
        identity : ContainerIdentity
            Exact resource identity and expected private ownership labels.
        command : list[str]
            Argument vector executed once inside the already owned container.
        limits : StreamLimits
            Validated combined output-byte limit and acquired-stream lifetime.

        Returns
        -------
        CommandResult
            Confirmed exit code and separate undecoded stdout/stderr bytes.

        Raises
        ------
        OwnershipConflictError
            Ownership inspection failed; no execution was requested.
        DeadlineError
            The acquired-stream deadline expired; execution may still be active.
        OutputLimitError
            Combined binary output exceeded the stream allowance; execution may still be active.
        DockerOperationError
            Inspection, execution, framing, transport or exit-status confirmation failed; reconcile before retrying.
        """
        if self.containers.inspect(identity) is None:
            raise DockerOperationError("execute in existing container")
        try:
            execution = self.sdk.api.exec_create(
                identity.id, command, stdout=True, stderr=True, tty=False
            )
            raw = self.sdk.api.exec_start(execution["Id"], socket=True, tty=False)
            stdout, stderr = bytearray(), bytearray()
            with AttachedStream(raw, limits) as stream:
                while True:
                    frame = stream.read_frame()
                    if frame is None:
                        break
                    (stdout if frame.channel == "stdout" else stderr).extend(frame.data)
            while True:
                state = self.sdk.api.exec_inspect(execution["Id"])
                if not state.get("Running") and isinstance(state.get("ExitCode"), int):
                    break
                time.sleep(min(EXIT_STATUS_POLL_SECONDS, stream.remaining_seconds()))
            return CommandResult(
                exit_code=state["ExitCode"], stdout=bytes(stdout), stderr=bytes(stderr)
            )
        except (DockerException, RequestException):
            raise DockerOperationError("execute container command") from None
