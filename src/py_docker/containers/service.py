"""Creation and cleanup restricted to exact owned container IDs."""

import math
import uuid

from docker import DockerClient
from docker.errors import DockerException, NotFound
from docker.models.containers import Container
from docker.models.images import Image
from docker.utils import convert_volume_binds, parse_bytes
from requests.exceptions import RequestException

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerSpec,
)
from py_docker.errors import (
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
    """

    def __init__(self, sdk: DockerClient) -> None:
        """Reuse the supplied SDK session without taking ownership of its lifetime."""
        self.sdk = sdk

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
        """
        receipt = reservation or self.reserve(spec)
        if receipt.name != spec.name:
            raise OwnershipConflictError("match container reservation")
        labels = {
            key: value.get_secret_value() for key, value in receipt.labels.items()
        }
        options = spec.model_dump(exclude={"image", "environment", "labels"})
        options["volumes"] = spec.sdk_volumes()
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
            container = self.sdk.containers.create(image.id, **options)
            phase = "validate container receipt"
            identity = ContainerIdentity(id=container.id, name=spec.name, labels=labels)
            phase = "verify container ownership"
            owned = self.inspect(identity)
            if owned is None:
                raise DockerOperationError("confirm newly created container exists")
            self._verify_launch(owned, spec, image)
            return identity
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
        image_config = image.attrs.get("Config", {})
        config = container.attrs.get("Config", {})
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
