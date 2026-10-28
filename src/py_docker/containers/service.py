"""Creation and cleanup restricted to exact owned container IDs."""

import uuid

from docker.errors import DockerException, NotFound

from py_docker.containers.models import ContainerIdentity, ContainerSpec
from py_docker.errors import DockerOperationError, OwnershipConflictError


class Containers:
    """No implicit pull, reuse, prune or forced name replacement."""

    def __init__(self, sdk):
        self.sdk = sdk

    def create(self, spec: ContainerSpec) -> ContainerIdentity:
        labels = {key: value.get_secret_value() for key, value in spec.labels.items()}
        labels["py_docker.owner"] = uuid.uuid4().hex
        options = spec.model_dump(exclude={"image", "environment", "labels"})
        options["environment"] = {key: value.get_secret_value() for key, value in spec.environment.items()}
        options["labels"] = labels
        try:
            image = self.sdk.images.get(spec.image)
            container = self.sdk.containers.create(image.id, **options)
            return ContainerIdentity(id=container.id, name=spec.name, labels=labels)
        except DockerException:
            raise DockerOperationError("create container") from None

    def inspect(self, identity: ContainerIdentity):
        try:
            container = self.sdk.containers.get(identity.id)
        except NotFound:
            return None
        except DockerException:
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
        except DockerException:
            raise DockerOperationError("start container") from None

    def remove(self, identity: ContainerIdentity, *, force: bool = False) -> None:
        container = self.inspect(identity)
        if container is None:
            return
        try:
            container.remove(force=force)
        except NotFound:
            pass
        except DockerException:
            raise DockerOperationError("remove container") from None
        if self.inspect(identity) is not None:
            raise DockerOperationError("confirm container removal")
