"""Immutable local image resolution and matching."""

from docker.errors import DockerException
from requests.exceptions import RequestException

from py_docker.errors import DockerOperationError, OwnershipConflictError


class Images:
    """Resolve local tags without pulling; require expected ID when supplied."""

    def __init__(self, sdk):
        self.sdk = sdk

    def resolve(self, reference: str, *, expected_id: str | None = None) -> str:
        try:
            image = self.sdk.images.get(reference)
        except (DockerException, RequestException):
            raise DockerOperationError("inspect local image") from None
        if expected_id is not None and image.id != expected_id:
            raise OwnershipConflictError("verify immutable image ID")
        return image.id
