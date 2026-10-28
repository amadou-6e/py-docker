"""Internal cancellation controls; real Docker/provider evidence is separate."""

import threading
from unittest.mock import Mock

import pytest

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerSpec,
)
from py_docker.errors import (
    CleanupUnconfirmedError,
    DockerOperationError,
    JobCancelledError,
)
from py_docker.jobs.models import ContainerJob
from py_docker.jobs.service import Jobs
from py_docker.streams.models import StreamLimits


def test_pre_cancelled_job_never_dispatches(tmp_path):
    """A stop already requested cannot create, recover or mutate resources."""
    containers, execution = Mock(), Mock()
    cancelled = threading.Event()
    cancelled.set()
    job = ContainerJob(
        spec=ContainerSpec(image="sha256:" + "a" * 64, name="owned"),
        limits=StreamLimits(seconds=1, max_bytes=64),
        receipt_path=tmp_path.joinpath("receipt.json"),
        wait_timeout_seconds=1.0,
    )
    with pytest.raises(JobCancelledError):
        Jobs(containers, execution).run(job, cancelled=cancelled)
    assert not containers.mock_calls
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_cancel_removes_only_observed_id_and_retains_uncertain_cleanup(
    tmp_path, cleanup_fails
):
    """Cancellation unblocks reads; cleanup uncertainty overrides the stop result."""
    containers, execution, stream = Mock(endpoint="unix:///test.sock"), Mock(), Mock()
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(id="a" * 64, name="owned", labels=reservation.labels)
    containers.reserve.return_value = reservation
    containers.create.return_value = identity
    execution.attach.return_value = stream
    cancelled, removed = threading.Event(), threading.Event()

    def read():
        """Request stop during a blocked stream, without a fake success receipt."""
        cancelled.set()
        assert removed.wait(3)
        return None

    def remove(observed, *, force):
        """Keep identity authorization strict even in the internal control."""
        assert observed == identity and force
        removed.set()
        if cleanup_fails:
            raise DockerOperationError("internal removal uncertainty")

    stream.read_frame.side_effect = read
    containers.remove.side_effect = remove
    job = ContainerJob(
        spec=ContainerSpec(image="sha256:" + "b" * 64, name="owned"),
        limits=StreamLimits(seconds=4, max_bytes=64),
        receipt_path=tmp_path.joinpath("receipt.json"),
        wait_timeout_seconds=1.0,
    )
    expected = CleanupUnconfirmedError if cleanup_fails else JobCancelledError
    with pytest.raises(expected) as caught:
        Jobs(containers, execution).run(job, cancelled=cancelled)
    assert job.receipt_path.exists() == cleanup_fails
    if cleanup_fails:
        assert isinstance(caught.value.primary, JobCancelledError)
    containers.wait.assert_not_called()
