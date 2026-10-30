"""Creation and cleanup restricted to exact owned container IDs."""

import math
import uuid
from pathlib import Path

from docker import DockerClient
from docker.errors import APIError, DockerException, NotFound
from docker.models.containers import Container
from docker.models.images import Image
from docker.utils import convert_volume_binds, parse_bytes
from requests.exceptions import RequestException

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerSpec,
    ContainerState,
)
from py_docker.containers.settings import DEFINITIVE_CREATE_REJECTIONS
from py_docker.containers.watch import ContainerWatch
from py_docker.errors import (
    CreateNotSentDeadlineError,
    CreationRejectedError,
    CreationUnconfirmedError,
    DockerOperationError,
    OwnershipConflictError,
)
from py_docker.settings import OWNERSHIP_LABEL


class Containers:
    """No implicit pull, reuse, prune or forced name replacement.

    Parameters
    ----------
    sdk : DockerClient
        Existing Docker SDK session; the caller owns its lifetime.
    endpoint : str or None
        Original resolved connection endpoint. Lifecycle jobs and sessions require
        it so recovery cannot infer absence on a different daemon.
    """

    def __init__(self, sdk: DockerClient, *, endpoint: str | None = None) -> None:
        """Reuse the supplied SDK session without taking ownership of its lifetime."""
        self.sdk = sdk
        self.endpoint = endpoint

    def watch(self, reservation: ContainerReservation) -> ContainerWatch:
        """Return an endpoint-bound observation and cleanup handle.

        Parameters
        ----------
        reservation : ContainerReservation
            Private exact name and labels whose delayed creation is supervised.

        Returns
        -------
        ContainerWatch
            Lightweight handle sharing this client's lifetime and endpoint.
        """
        return ContainerWatch(self, reservation)

    def reserve(self, spec: ContainerSpec) -> ContainerReservation:
        """Prepare a private ownership token before any create request.

        Parameters
        ----------
        spec : ContainerSpec
            Validated launch request including the exact image, name and sandbox options.

        Returns
        -------
        ContainerReservation
            Ownership intent containing the exact name and generated private token.
        """
        labels = {key: value.get_secret_value() for key, value in spec.labels.items()}
        labels[OWNERSHIP_LABEL] = uuid.uuid4().hex
        return ContainerReservation(name=spec.name, labels=labels)

    def reconcile(self, reservation: ContainerReservation) -> ContainerIdentity | None:
        """Resolve a reservation by name and verify its exact owned identity.

        Parameters
        ----------
        reservation : ContainerReservation
            Private pre-create ownership receipt retained for uncertain-outcome recovery.

        Returns
        -------
        ContainerIdentity | None
            Verified immutable identity, or None only when the owned ID is absent.

        Raises
        ------
        DockerOperationError
            Docker inspection failed; creation remains unconfirmed.
        OwnershipConflictError
            The observed name or ownership labels differ from the receipt.
        """
        try:
            container = self.sdk.containers.get(reservation.name)
        except NotFound:
            return None
        except (DockerException, RequestException):
            raise DockerOperationError("reconcile container creation") from None
        identity = ContainerIdentity(
            id=container.id, name=reservation.name, labels=reservation.labels
        )
        return identity if self.inspect(identity) is not None else None

    def create(
        self, spec: ContainerSpec, reservation: ContainerReservation | None = None
    ) -> ContainerIdentity:
        """Create a local-image container and verify its observed launch policy.

        Parameters
        ----------
        spec : ContainerSpec
            Validated launch request including the exact image, name and sandbox options.
        reservation : ContainerReservation or None
            Private pre-create ownership receipt retained for uncertain-outcome recovery.

        Returns
        -------
        ContainerIdentity
            Verified private ownership receipt for the created resource.

        Raises
        ------
        OwnershipConflictError
            The reservation names a different container; no create request was sent.
        DockerOperationError
            The local image could not be resolved; no create request was sent.
        CreationUnconfirmedError
            Creation or readback is unconfirmed; reconcile the attached receipt before retrying.
        CreationRejectedError
            The create endpoint returned a definitive bad-parameter, missing-image
            or conflict response. No container was created by this request.
        """
        receipt = reservation or self.reserve(spec)
        if receipt.name != spec.name:
            raise OwnershipConflictError("match container reservation")
        for mount in spec.mounts:
            try:
                missing = mount.type == "bind" and not Path(mount.source).exists()
            except (OSError, ValueError):
                raise DockerOperationError(
                    "verify local bind mount source exists"
                ) from None
            if missing:
                raise DockerOperationError("verify local bind mount source exists")
        labels = {
            key: value.get_secret_value() for key, value in receipt.labels.items()
        }
        options = spec.model_dump(exclude={"image", "environment", "labels"})
        options["volumes"] = spec.sdk_volumes()
        options["mounts"] = [mount.to_sdk() for mount in spec.mounts]
        options["ports"] = spec.sdk_ports()
        options["environment"] = {
            key: value.get_secret_value() for key, value in spec.environment.items()
        }
        options["labels"] = labels
        options["use_config_proxy"] = False
        try:
            image = self.sdk.images.get(spec.image)
        except (DockerException, RequestException):
            raise DockerOperationError("resolve container image") from None
        phase = "create container"
        try:
            try:
                container = self.sdk.containers.create(image.id, **options)
            except APIError as error:
                if error.status_code in DEFINITIVE_CREATE_REJECTIONS:
                    raise CreationRejectedError("create container", receipt) from None
                raise
            phase = "validate container receipt"
            identity = ContainerIdentity(id=container.id, name=spec.name, labels=labels)
            phase = "verify container ownership"
            owned = self.inspect(identity)
            if owned is None:
                raise DockerOperationError("confirm newly created container exists")
            self._verify_launch(owned, spec, image)
            return identity
        except (CreationRejectedError, CreateNotSentDeadlineError):
            raise
        except Exception as error:
            if isinstance(error, DockerOperationError):
                phase = error.operation
            raise CreationUnconfirmedError(phase, receipt) from None

    def inspect(self, identity: ContainerIdentity) -> Container | None:
        """Look up an immutable ID and validate its expected name and labels.

        Parameters
        ----------
        identity : ContainerIdentity
            Exact resource identity and expected private ownership labels.

        Returns
        -------
        Container | None
            Verified SDK resource, or None only for Docker NotFound.

        Raises
        ------
        DockerOperationError
            Docker could not inspect the container; absence is not confirmed.
        OwnershipConflictError
            The observed ID, name or ownership labels differ from the receipt.
        """
        try:
            container = self.sdk.containers.get(identity.id)
        except NotFound:
            return None
        except (DockerException, RequestException):
            raise DockerOperationError("inspect container") from None
        attrs = container.attrs
        actual = attrs.get("Config", {}).get("Labels") or {}
        if (
            attrs.get("Id") != identity.id
            or attrs.get("Name", "").lstrip("/") != identity.name.lstrip("/")
            or any(
                actual.get(key) != value.get_secret_value()
                for key, value in identity.labels.items()
            )
        ):
            raise OwnershipConflictError("verify container ownership")
        return container

    def start(self, identity: ContainerIdentity) -> None:
        """Start only the exact container whose ownership was checked.

        Parameters
        ----------
        identity : ContainerIdentity
            Exact resource identity and expected private ownership labels.

        Raises
        ------
        OwnershipConflictError
            Ownership inspection failed; no start request was sent.
        DockerOperationError
            The container is absent, inspection failed, or the start outcome is unconfirmed.
        """
        container = self.inspect(identity)
        if container is None:
            raise DockerOperationError("start missing container")
        try:
            container.start()
        except (DockerException, RequestException):
            raise DockerOperationError("start container") from None

    def wait(self, identity: ContainerIdentity, *, timeout: float) -> int:
        """Wait for an owned container's exit and validate its confirmed status.

        Parameters
        ----------
        identity : ContainerIdentity
            Immutable ID and expected name/labels checked before the wait request.
        timeout : float
            Positive finite request timeout in seconds, separate from stream limits.

        Returns
        -------
        int
            Confirmed process exit code; nonzero values are returned unchanged.

        Raises
        ------
        ValueError
            The timeout is not a positive finite number.
        OwnershipConflictError
            The resource does not match the expected ownership; no wait was requested.
        DockerOperationError
            Inspection, wait transport, absence or malformed status prevents confirmation.
        """
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Wait timeout must be positive and finite")
        container = self.inspect(identity)
        if container is None:
            raise DockerOperationError("wait for missing container")
        try:
            result = container.wait(timeout=timeout)
            if (
                not isinstance(result, dict)
                or type(result.get("StatusCode")) is not int
            ):
                raise DockerOperationError("confirm container exit status")
            return result["StatusCode"]
        except (
            DockerException,
            RequestException,
            TimeoutError,
            TypeError,
            KeyError,
            AttributeError,
        ):
            raise DockerOperationError("wait for container exit") from None

    def remove(
        self,
        identity: ContainerIdentity,
        *,
        force: bool = False,
        remove_anonymous_volumes: bool = False,
    ) -> None:
        """Remove the exact owned ID and confirm it no longer exists.

        Parameters
        ----------
        identity : ContainerIdentity
            Exact resource identity and expected private ownership labels.
        force : bool
            Whether Docker may stop the exact owned container during removal.
        remove_anonymous_volumes : bool
            Explicit permission to remove anonymous volumes with the owned container.

        Raises
        ------
        OwnershipConflictError
            Ownership inspection failed; no removal request follows that failed check.
        DockerOperationError
            Inspection failed, removal failed, or readback still reports the owned container.
        """
        container = self.inspect(identity)
        if container is None:
            return
        try:
            container.remove(force=force, v=remove_anonymous_volumes)
        except NotFound:
            pass
        except (DockerException, RequestException):
            raise DockerOperationError("remove container") from None
        if self.inspect(identity) is not None:
            raise DockerOperationError("confirm container removal")

    def state(self, identity: ContainerIdentity) -> ContainerState:
        """Inspect exact ownership and validate process state without polling loops.

        Parameters
        ----------
        identity : ContainerIdentity
            Observed immutable ID and expected ownership labels.

        Returns
        -------
        ContainerState
            Confirmed state; absence never invents an exit status.

        Raises
        ------
        DockerOperationError
            Ownership, inspection or Docker state fields are unconfirmed.
        """
        container = self.inspect(identity)
        if container is None:
            return ContainerState(running=False, removed=True)
        state = container.attrs.get("State") or {}
        running = state.get("Running")
        status = state.get("Status")
        if type(running) is not bool:
            raise DockerOperationError("confirm container running state")
        code = None
        if not running and status in {"exited", "dead"}:
            code = state.get("ExitCode")
            if type(code) is not int:
                raise DockerOperationError("confirm container exit status")
        return ContainerState(running=running, exit_code=code, removed=False)

    def published_port(self, identity: ContainerIdentity, container_port: str) -> int:
        """Return one confirmed loopback port of an owned, started container.

        Parameters
        ----------
        identity : ContainerIdentity
            Immutable ID and ownership labels authorizing inspection.
        container_port : str
            Exact port/protocol key requested at creation, such as 4096/tcp.

        Returns
        -------
        int
            Confirmed host port bound exclusively to 127.0.0.1.

        Raises
        ------
        DockerOperationError
            The resource, binding or loopback isolation cannot be confirmed.
        """
        container = self.inspect(identity)
        if container is not None:
            bindings = (
                container.attrs.get("NetworkSettings", {})
                .get("Ports", {})
                .get(container_port)
            )
            if isinstance(bindings, list) and len(bindings) == 1:
                binding = bindings[0]
                port = binding.get("HostPort", "")
                if (
                    binding.get("HostIp") == "127.0.0.1"
                    and isinstance(port, str)
                    and port.isdecimal()
                    and 1 <= int(port) <= 65535
                ):
                    return int(port)
        raise DockerOperationError("confirm loopback published port")

    def _verify_launch(
        self, container: Container, spec: ContainerSpec, image: Image
    ) -> None:
        """Compare Docker readback against requested sandbox and image defaults.

        Parameters
        ----------
        container : Container
            SDK container read back from the selected Docker daemon.
        spec : ContainerSpec
            Validated launch request including the exact image, name and sandbox options.
        image : Image
            Locally inspected image supplying immutable ID and inherited defaults.

        Raises
        ------
        OwnershipConflictError
            Readback differs from the requested sandbox, mounts, environment or image configuration.
        """
        host = container.attrs.get("HostConfig", {})
        expected = {
            "NetworkMode": spec.network_mode,
            "ReadonlyRootfs": spec.read_only,
            "PidsLimit": spec.pids_limit,
            "Memory": parse_bytes(spec.mem_limit),
            "Tmpfs": spec.tmpfs,
        }
        actual = {key: host.get(key) for key in expected}
        actual["Tmpfs"] = actual["Tmpfs"] or {}
        if (
            bool(host.get("Init")) != spec.init
            or (host.get("NanoCpus") or 0) != spec.nano_cpus
        ):
            raise OwnershipConflictError("verify container init and CPU quota")
        if sorted(host.get("ExtraHosts") or []) != sorted(
            f"{key}:{value}" for key, value in spec.extra_hosts.items()
        ):
            raise OwnershipConflictError("verify container host aliases")
        bindings = host.get("PortBindings") or {}
        if set(bindings) != set(spec.ports) or any(
            bindings[port]
            != [{"HostIp": "127.0.0.1", "HostPort": str(number) if number else ""}]
            for port, number in spec.ports.items()
        ):
            raise OwnershipConflictError("verify loopback port bindings")
        if actual != expected:
            raise OwnershipConflictError("verify container sandbox configuration")
        for key, values in (
            ("CapDrop", spec.cap_drop),
            ("CapAdd", spec.cap_add),
            ("SecurityOpt", spec.security_opt),
        ):
            if set(host.get(key) or []) != set(values):
                raise OwnershipConflictError("verify container sandbox permissions")
        if sorted(host.get("Binds") or []) != sorted(
            convert_volume_binds(spec.sdk_volumes())
        ):
            raise OwnershipConflictError("verify container bind mounts")
        actual_mounts = host.get("Mounts") or []
        if len(actual_mounts) != len(spec.mounts) or not all(
            mount.matches_readback(
                actual, local_npipe=self.sdk.api.base_url == "http+docker://localnpipe"
            )
            for mount, actual in zip(spec.mounts, actual_mounts)
        ):
            raise OwnershipConflictError("verify explicit container mounts")
        image_config = image.attrs.get("Config", {})
        config = container.attrs.get("Config", {})
        if bool(config.get("OpenStdin")) != spec.stdin_open or bool(config.get("Tty")):
            raise OwnershipConflictError("verify container stdin and terminal")
        if spec.stdin_open and config.get("StdinOnce") is not True:
            raise OwnershipConflictError("verify attached stdin closure")
        expected_env = {
            value.partition("=")[0]: value.partition("=")[2]
            for value in image_config.get("Env") or []
        }
        expected_env.update(
            {key: value.get_secret_value() for key, value in spec.environment.items()}
        )
        actual_env = {
            value.partition("=")[0]: value.partition("=")[2]
            for value in config.get("Env") or []
        }
        if actual_env != expected_env:
            raise OwnershipConflictError("verify explicit container environment")
        for key, supplied in (
            ("User", spec.user),
            ("WorkingDir", spec.working_dir),
            ("Entrypoint", spec.entrypoint),
            ("Cmd", spec.command),
        ):
            expected_value = image_config.get(key) if supplied is None else supplied
            if key == "Cmd" and spec.command is None and spec.entrypoint:
                expected_value = None
            if key in {"Cmd", "Entrypoint"}:
                expected_value = expected_value or None
                actual_value = config.get(key) or None
            else:
                expected_value = expected_value or ""
                actual_value = config.get(key) or ""
            if actual_value != expected_value:
                raise OwnershipConflictError("verify container process configuration")
