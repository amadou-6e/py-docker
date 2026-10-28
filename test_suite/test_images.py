"""Internal image failure classification; real Docker acceptance is separate."""

from unittest.mock import Mock

import pytest
from docker.errors import DockerException, ImageNotFound
from requests.exceptions import ConnectionError

from py_docker.errors import ImageResolutionError, OwnershipConflictError
from py_docker.images.service import Images


@pytest.mark.parametrize(
    "failure",
    [
        ImageNotFound("private missing detail"),
        DockerException("private daemon detail"),
        ConnectionError("private endpoint detail"),
    ],
)
def test_image_inspection_failure_is_typed_without_inventing_absence(failure):
    """Absence and daemon failures share a safe resolution category without a pull."""
    sdk = Mock()
    sdk.images.get.side_effect = failure
    with pytest.raises(ImageResolutionError) as caught:
        Images(sdk).resolve("private-reference")
    assert caught.value.code == "docker_image_resolution_failed"
    assert "private" not in str(caught.value)
    assert caught.value.__suppress_context__
    sdk.images.pull.assert_not_called()
    sdk.containers.create.assert_not_called()


def test_image_pin_conflict_retains_its_distinct_type():
    """An observed ID mismatch remains an ownership refusal, not inspection failure."""
    sdk = Mock()
    sdk.images.get.return_value.id = "sha256:" + "a" * 64
    with pytest.raises(OwnershipConflictError):
        Images(sdk).resolve("local-image", expected_id="sha256:" + "b" * 64)
