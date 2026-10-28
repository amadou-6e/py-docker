"""Create uniquely named volumes; existing volumes are never adopted implicitly."""

import uuid

from docker.errors import DockerException, NotFound
from requests.exceptions import RequestException

from py_docker.errors import (
    CreationUnconfirmedError,
    DockerOperationError,
    OwnershipConflictError,
)
from py_docker.volumes.models import VolumeIdentity


class Volumes:
    """Docker volume create is idempotent; read back an unguessable owner label."""

    def __init__(self, sdk):
        self.sdk = sdk

    def create(self, prefix: str = "py-docker") -> VolumeIdentity:
        token = uuid.uuid4().hex
        name = f"{prefix}-{token}"
        labels = {"py_docker.owner": token}
        receipt = VolumeIdentity(name=name, labels=labels)
        try:
            volume = self.sdk.volumes.create(name=name, labels=labels)
            volume.reload()
            if volume.attrs.get("Labels") != labels:
                raise OwnershipConflictError("verify created volume ownership")
        except (DockerException, RequestException, OwnershipConflictError):
            raise CreationUnconfirmedError("create volume", receipt) from None
        return receipt

    def inspect(self, identity: VolumeIdentity):
        try:
            volume = self.sdk.volumes.get(identity.name)
        except NotFound:
            return None
        except (DockerException, RequestException):
            raise DockerOperationError("inspect volume") from None
        actual = volume.attrs.get("Labels") or {}
        if any(
            actual.get(key) != value.get_secret_value()
            for key, value in identity.labels.items()
        ):
            raise OwnershipConflictError("verify volume ownership")
        return volume

    # Deliberately no generic remove-by-name: unlike containers, Docker volumes
    # have no immutable ID for race-safe deletion. Caller must serialize lifecycle.
