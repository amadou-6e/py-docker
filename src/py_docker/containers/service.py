"""Creation and cleanup restricted to exact owned container IDs."""

import uuid

from docker.errors import DockerException, NotFound
from requests.exceptions import RequestException

from py_docker.containers.models import ContainerIdentity, ContainerReservation, ContainerSpec
from py_docker.errors import CreationUnconfirmedError, DockerOperationError, OwnershipConflictError


class Containers:
    """No implicit pull, reuse, prune or forced name replacement."""

    def __init__(self, sdk):
        self.sdk = sdk

    def reserve(self, spec: ContainerSpec) -> ContainerReservation:
        labels = {key: value.get_secret_value() for key, value in spec.labels.items()}
        labels["py_docker.owner"] = uuid.uuid4().hex
        return ContainerReservation(name=spec.name, labels=labels)

    def reconcile(self, reservation: ContainerReservation) -> ContainerIdentity | None:
        try:
            container = self.sdk.containers.get(reservation.name)
        except NotFound:
            return None
        except (DockerException, RequestException):
            raise DockerOperationError("reconcile container creation") from None
        identity = ContainerIdentity(id=container.id, name=reservation.name, labels=reservation.labels)
        return identity if self.inspect(identity) is not None else None

    def create(self, spec: ContainerSpec, reservation: ContainerReservation | None = None) -> ContainerIdentity:
        receipt = reservation or self.reserve(spec)
        if receipt.name != spec.name:
            raise OwnershipConflictError("match container reservation")
        labels = {key: value.get_secret_value() for key, value in receipt.labels.items()}
        options = spec.model_dump(exclude={"image", "environment", "labels"})
        options["environment"] = {key: value.get_secret_value() for key, value in spec.environment.items()}
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

    def _verify_launch(self, container, spec: ContainerSpec, image) -> None:
        from docker.utils import convert_volume_binds, parse_bytes

        host = container.attrs.get("HostConfig", {})
        expected = {"NetworkMode": spec.network_mode, "ReadonlyRootfs": spec.read_only, "PidsLimit": spec.pids_limit, "Memory": parse_bytes(spec.mem_limit), "Tmpfs": spec.tmpfs}
        actual = {key: host.get(key) for key in expected}
        actual["Tmpfs"] = actual["Tmpfs"] or {}
        if actual != expected:
            raise OwnershipConflictError("verify container sandbox configuration")
        for key, values in (("CapDrop", spec.cap_drop), ("CapAdd", spec.cap_add), ("SecurityOpt", spec.security_opt)):
            if set(host.get(key) or []) != set(values):
                raise OwnershipConflictError("verify container sandbox permissions")
        if sorted(host.get("Binds") or []) != sorted(convert_volume_binds(spec.volumes)):
            raise OwnershipConflictError("verify container bind mounts")
        image_config = image.attrs.get("Config", {})
        config = container.attrs.get("Config", {})
        expected_env = {value.partition("=")[0]: value.partition("=")[2] for value in image_config.get("Env") or []}
        expected_env.update({key: value.get_secret_value() for key, value in spec.environment.items()})
        actual_env = {value.partition("=")[0]: value.partition("=")[2] for value in config.get("Env") or []}
        if actual_env != expected_env:
            raise OwnershipConflictError("verify explicit container environment")
        for key, supplied in (("User", spec.user), ("WorkingDir", spec.working_dir), ("Entrypoint", spec.entrypoint), ("Cmd", spec.command)):
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

    def inspect(self, identity: ContainerIdentity):
        try:
            container = self.sdk.containers.get(identity.id)
        except NotFound:
            return None
        except (DockerException, RequestException):
            raise DockerOperationError("inspect container") from None
        attrs = container.attrs
        actual = attrs.get("Config", {}).get("Labels") or {}
        if attrs.get("Id") != identity.id or attrs.get("Name", "").lstrip("/") != identity.name.lstrip("/") or any(actual.get(key) != value.get_secret_value() for key, value in identity.labels.items()):
            raise OwnershipConflictError("verify container ownership")
        return container

    def start(self, identity: ContainerIdentity) -> None:
        container = self.inspect(identity)
        if container is None:
            raise DockerOperationError("start missing container")
        try:
            container.start()
        except (DockerException, RequestException):
            raise DockerOperationError("start container") from None

    def remove(self, identity: ContainerIdentity, *, force: bool = False, remove_anonymous_volumes: bool = False) -> None:
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
