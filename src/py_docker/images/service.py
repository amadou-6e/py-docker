"""Immutable local image resolution and matching."""

from docker import DockerClient
from docker.errors import DockerException
from requests.exceptions import RequestException

from py_docker.errors import DockerOperationError, OwnershipConflictError


class Images:
    """Resolve local tags without pulling; require expected ID when supplied.

    Parameters
    ----------
    sdk : DockerClient
        Existing Docker SDK session; the caller owns its lifetime.
    """

    def __init__(self, sdk: DockerClient) -> None:
        """Reuse the supplied SDK session for local image inspection."""
        self.sdk = sdk

    def resolve(self, reference: str, *, expected_id: str | None = None) -> str:
        """Resolve a local image and optionally verify its immutable ID.

        Parameters
        ----------
        reference : str
            Locally installed image name or immutable ID; no pull is attempted.
        expected_id : str or None
            Required immutable image ID, or None to return the locally resolved ID.

        Returns
        -------
        str
            Full immutable ID of the locally inspected image.

        Raises
        ------
        DockerOperationError
            The local image could not be inspected; no pull was attempted.
        OwnershipConflictError
            The locally resolved immutable image ID differs from expected_id.
        """
        try:
            image = self.sdk.images.get(reference)
        except (DockerException, RequestException):
            raise DockerOperationError("inspect local image") from None
        if expected_id is not None and image.id != expected_id:
            raise OwnershipConflictError("verify immutable image ID")
        return image.id
