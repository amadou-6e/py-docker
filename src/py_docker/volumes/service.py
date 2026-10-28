"""Create uniquely named volumes; existing volumes are never adopted implicitly."""

import uuid

from docker import DockerClient
from docker.errors import DockerException, NotFound
from docker.models.volumes import Volume
from requests.exceptions import RequestException

from py_docker.errors import (
    CreationUnconfirmedError,
    DockerOperationError,
    OwnershipConflictError,
)
from py_docker.settings import OWNERSHIP_LABEL
from py_docker.volumes.models import VolumeIdentity
from py_docker.volumes.settings import DEFAULT_VOLUME_PREFIX


class Volumes:
    """Docker volume create is idempotent; read back an unguessable owner label.

    Parameters
    ----------
    sdk : DockerClient
        Existing Docker SDK session; the caller owns its lifetime.
    """

    def __init__(self, sdk: DockerClient) -> None:
        """Reuse the SDK session for explicit volume creation and inspection."""
        self.sdk = sdk

    def create(self, prefix: str = DEFAULT_VOLUME_PREFIX) -> VolumeIdentity:
        """Create a unique volume and verify its private ownership label.

        Parameters
        ----------
        prefix : str
            Human-readable prefix for a generated unique volume name.

        Returns
        -------
        VolumeIdentity
            Verified private ownership receipt for the created resource.

        Raises
        ------
        CreationUnconfirmedError
            The daemon may have created the volume; reconcile the attached receipt.
        """
        token = uuid.uuid4().hex
        name = f"{prefix}-{token}"
        labels = {OWNERSHIP_LABEL: token}
        receipt = VolumeIdentity(name=name, labels=labels)
        try:
            volume = self.sdk.volumes.create(name=name, labels=labels)
            volume.reload()
            if volume.attrs.get("Labels") != labels:
                raise OwnershipConflictError("verify created volume ownership")
        except (DockerException, RequestException, OwnershipConflictError):
            raise CreationUnconfirmedError("create volume", receipt) from None
        return receipt

    def inspect(self, identity: VolumeIdentity) -> Volume | None:
        """Return a named volume only when its expected ownership labels match.

        Parameters
        ----------
        identity : VolumeIdentity
            Exact resource identity and expected private ownership labels.

        Returns
        -------
        Volume | None
            Verified SDK resource, or None only for Docker NotFound.

        Raises
        ------
        DockerOperationError
            Docker could not inspect the volume; absence is not confirmed.
        OwnershipConflictError
            The observed ownership labels differ from the receipt.
        """
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
