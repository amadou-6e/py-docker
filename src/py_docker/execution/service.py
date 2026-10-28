"""Explicit attach/exec APIs. No retry if the execution outcome is uncertain."""

import time
from docker.errors import DockerException
from requests.exceptions import RequestException

from py_docker.containers.models import ContainerIdentity
from py_docker.containers.service import Containers
from py_docker.errors import DockerOperationError
from py_docker.execution.models import CommandResult
from py_docker.streams.models import StreamLimits
from py_docker.streams.socket import AttachedStream


class Execution:
    """Control requests use the client timeout; acquired streams use StreamLimits."""

    def __init__(self, sdk):
        self.sdk = sdk
        self.containers = Containers(sdk)

    def attach(self, identity: ContainerIdentity, limits: StreamLimits, *, stdin: bool = False) -> AttachedStream:
        container = self.containers.inspect(identity)
        if container is None or container.attrs.get("Config", {}).get("Tty"):
            raise DockerOperationError("attach existing non-TTY container")
        try:
            raw = self.sdk.api.attach_socket(identity.id, params={"stdin": stdin, "stdout": True, "stderr": True, "stream": True, "logs": False})
        except (DockerException, RequestException):
            raise DockerOperationError("attach container") from None
        return AttachedStream(raw, limits)

    def run(self, identity: ContainerIdentity, command: list[str], limits: StreamLimits) -> CommandResult:
        if self.containers.inspect(identity) is None:
            raise DockerOperationError("execute in existing container")
        try:
            execution = self.sdk.api.exec_create(identity.id, command, stdout=True, stderr=True, tty=False)
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
                time.sleep(min(0.05, stream._remaining()))
            return CommandResult(exit_code=state["ExitCode"], stdout=bytes(stdout), stderr=bytes(stderr))
        except (DockerException, RequestException):
            raise DockerOperationError("execute container command") from None
