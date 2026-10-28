"""Internal job/recovery controls; real Docker coverage lives in integration tests."""

import os
import subprocess
import sys
import time
from unittest.mock import MagicMock, Mock

import pytest
from docker.errors import DockerException
from pydantic import ValidationError

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerSpec,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import (
    CleanupUnconfirmedError,
    CreationUnconfirmedError,
    DeadlineError,
    DockerOperationError,
    PendingReceiptError,
    ReceiptInUseError,
)
from py_docker.jobs.models import ContainerJob
from py_docker.jobs.service import Jobs
from py_docker.streams.models import Frame, StreamLimits


def _job(tmp_path):
    """Build a validated internal command request with explicit lifetime limits.

    Parameters
    ----------
    tmp_path : Path
        Existing private directory allocated by pytest.

    Returns
    -------
    ContainerJob
        Noninteractive immutable-image request; no real Docker operation occurs.
    """
    return ContainerJob(
        spec=ContainerSpec(
            image="sha256:" + "a" * 64, name="owned-job", command=["command"]
        ),
        limits=StreamLimits(seconds=2, max_bytes=64),
        receipt_path=tmp_path.joinpath("receipt.json"),
        wait_timeout_seconds=3,
    )


def _runtime():
    """Configure internal service doubles at the actual runtime ownership boundary.

    Returns
    -------
    tuple[Jobs, Mock, Mock]
        Real job orchestrator and its injected container/execution services.
    """
    containers, execution = Mock(), MagicMock()
    receipt = ContainerReservation(name="owned-job", labels={"owner": "private-owner"})
    identity = ContainerIdentity(id="b" * 64, name=receipt.name, labels=receipt.labels)
    containers.reserve.return_value = receipt
    containers.create.return_value = identity
    containers.reconcile.return_value = identity
    containers.wait.return_value = 7
    execution.attach.return_value.__enter__.return_value.read_frame.side_effect = [
        Frame(channel="stdout", data=b"\x00out"),
        Frame(channel="stderr", data=b"\xfferr"),
        None,
    ]
    return Jobs(containers, execution), containers, execution


def test_job_returns_binary_output_and_nonzero_exit_after_exact_cleanup(tmp_path):
    """Capture both channels without decoding and clean only the created identity."""
    jobs, containers, execution = _runtime()
    ordering = Mock()
    ordering.attach_mock(containers, "containers")
    ordering.attach_mock(execution, "execution")
    job = _job(tmp_path)
    result = jobs.run(job)
    assert (result.exit_code, result.stdout, result.stderr) == (
        7,
        b"\x00out",
        b"\xfferr",
    )
    calls = [str(call) for call in ordering.mock_calls]
    assert next(
        i for i, c in enumerate(calls) if c.startswith("call.execution.attach(")
    ) < next(i for i, c in enumerate(calls) if c.startswith("call.containers.start("))
    containers.remove.assert_called_once_with(
        containers.create.return_value, force=True
    )
    containers.wait.assert_called_once_with(containers.create.return_value, timeout=3)
    assert not job.receipt_path.exists()
    assert "out" not in repr(result) and "err" not in repr(result)


def test_private_receipt_round_trip_is_explicit_and_excluded_from_public_dump():
    """Keep normal serialization secret-free while supporting private recovery files."""
    receipt = ContainerReservation(name="job", labels={"owner": "private-owner"})
    assert "private-owner" not in receipt.model_dump_json()
    assert "private-owner" not in repr(receipt)
    assert (
        ContainerReservation.from_private_record(receipt.to_private_record()) == receipt
    )


def test_receipt_is_exclusive_private_and_saved_before_create(tmp_path):
    """Never overwrite a pending file and persist ownership before daemon dispatch."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    receipt = containers.reserve.return_value

    def create(spec, supplied):
        assert supplied == receipt
        assert (
            ContainerReservation.from_private_record(
                __import__("json").loads(job.receipt_path.read_text())
            )
            == receipt
        )
        if os.name != "nt":
            assert job.receipt_path.stat().st_mode & 0o777 == 0o600
        return ContainerIdentity(id="b" * 64, name=spec.name, labels=supplied.labels)

    containers.create.side_effect = create
    jobs.run(job)
    with ReceiptStore(job.receipt_path) as store:
        store.save(receipt)
        before = job.receipt_path.read_bytes()
        with pytest.raises(PendingReceiptError):
            store.save(receipt)
        assert job.receipt_path.read_bytes() == before


def test_live_receipt_lock_blocks_other_callers_without_docker_access(tmp_path):
    """A second caller must not recover or stop a job still owned by the first."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    with ReceiptStore(job.receipt_path):
        with pytest.raises(ReceiptInUseError):
            jobs.run(job)
        with pytest.raises(ReceiptInUseError):
            jobs.recover(job.receipt_path)
    assert not containers.mock_calls


def test_native_receipt_lock_survives_contention_and_releases_after_process_loss(
    tmp_path,
):
    """Use a real child process to prove exclusion and kernel cleanup on process loss."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    ready = tmp_path.joinpath("ready")
    code = """
import sys,time
from pathlib import Path
from py_docker.containers.models import ContainerReservation
from py_docker.containers.receipts import ReceiptStore
with ReceiptStore(Path(sys.argv[1])) as store:
    store.save(ContainerReservation(name='owned-job',labels={'owner':'private-owner'}))
    Path(sys.argv[2]).write_text('ready')
    time.sleep(30)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(job.receipt_path), str(ready)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while (
            not ready.exists()
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert ready.exists(), "Child receipt owner did not become ready"
        with pytest.raises(ReceiptInUseError):
            jobs.recover(job.receipt_path)
        assert not containers.mock_calls
        process.kill()
        process.wait(timeout=5)
        jobs.recover(job.receipt_path)
        containers.remove.assert_called_once()
        assert not job.receipt_path.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()


def test_recovery_of_observed_container_removes_exact_id_and_receipt(tmp_path):
    """Recover a prior owned resource before clearing its durable intent."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    with ReceiptStore(job.receipt_path) as store:
        store.save(containers.reserve.return_value)
    jobs.recover(job.receipt_path)
    containers.remove.assert_called_once_with(
        containers.reconcile.return_value, force=True
    )
    assert not job.receipt_path.exists()


@pytest.mark.parametrize("state", ["absent", "conflict", "unknown", "corrupt"])
def test_uncertain_recovery_retains_receipt_and_refuses_new_create(tmp_path, state):
    """Unobserved or malformed intent cannot justify blindly dispatching again."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    with ReceiptStore(job.receipt_path) as store:
        store.save(containers.reserve.return_value)
    if state == "absent":
        containers.reconcile.return_value = None
    elif state == "corrupt":
        job.receipt_path.write_text("private corrupt content")
    else:
        containers.reconcile.side_effect = DockerOperationError(
            "inspect owned container"
        )
    before = job.receipt_path.read_bytes()
    with pytest.raises(CleanupUnconfirmedError) as captured:
        jobs.run(job)
    assert "private corrupt content" not in str(captured.value)
    assert job.receipt_path.read_bytes() == before
    containers.create.assert_not_called()
    containers.remove.assert_not_called()


def test_cleanup_error_retains_safe_primary_and_creation_receipt(tmp_path):
    """Cleanup uncertainty wins while preserving the original typed stream failure."""
    jobs, containers, execution = _runtime()
    job = _job(tmp_path)
    original = DeadlineError("read container stream")
    execution.attach.return_value.__enter__.return_value.read_frame.side_effect = (
        original
    )
    containers.remove.side_effect = DockerOperationError("remove owned container")
    with pytest.raises(CleanupUnconfirmedError) as captured:
        jobs.run(job)
    assert captured.value.primary is original
    assert captured.value.receipt == containers.reserve.return_value
    assert job.receipt_path.exists()


def test_immediate_absence_after_uncertain_create_stays_unconfirmed(tmp_path):
    """A delayed create may still arrive after the first name lookup reports absent."""
    jobs, containers, _ = _runtime()
    job = _job(tmp_path)
    primary = CreationUnconfirmedError(
        "create container", containers.reserve.return_value
    )
    containers.create.side_effect = primary
    containers.reconcile.return_value = None
    with pytest.raises(CleanupUnconfirmedError) as captured:
        jobs.run(job)
    assert captured.value.primary is primary
    assert job.receipt_path.exists()
    containers.remove.assert_not_called()


def test_unexpected_external_error_is_redacted_and_cleanup_still_runs(tmp_path):
    """Never propagate raw SDK text from an unexpected execution failure."""
    jobs, containers, execution = _runtime()
    execution.attach.side_effect = RuntimeError("external private payload")
    with pytest.raises(DockerOperationError) as captured:
        jobs.run(_job(tmp_path))
    assert "external private payload" not in str(captured.value)
    assert captured.value.__suppress_context__
    containers.remove.assert_called_once()


@pytest.mark.parametrize(
    "image,stdin", [("tag:latest", False), ("sha256:" + "a" * 64, True)]
)
def test_jobs_reject_mutable_image_and_interactive_stdin(tmp_path, image, stdin):
    """Unsupported requests fail validation before opening a receipt or dispatching."""
    with pytest.raises(ValidationError):
        ContainerJob(
            spec=ContainerSpec(image=image, name="job", stdin_open=stdin),
            limits=StreamLimits(seconds=1, max_bytes=2),
            receipt_path=tmp_path.joinpath("receipt"),
            wait_timeout_seconds=1,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "status", [None, [], {"StatusCode": True}, {"StatusCode": "0"}]
)
def test_owned_wait_rejects_malformed_status_without_exposing_it(status):
    """Only an actual integer exit status confirms the owned container result."""
    sdk = Mock()
    identity = ContainerIdentity(id="b" * 64, name="job", labels={"owner": "expected"})
    container = sdk.containers.get.return_value
    container.attrs = {
        "Id": identity.id,
        "Name": "/job",
        "Config": {"Labels": {"owner": "expected"}},
    }
    container.wait.return_value = status
    with pytest.raises(DockerOperationError):
        Containers(sdk).wait(identity, timeout=2)


def test_wait_transport_failure_is_safe_and_distinct_from_process_exit():
    """A transport error cannot be returned as a fabricated process exit code."""
    sdk = Mock()
    identity = ContainerIdentity(id="b" * 64, name="job", labels={"owner": "expected"})
    sdk.containers.get.side_effect = DockerException("external private payload")
    with pytest.raises(DockerOperationError) as captured:
        Containers(sdk).wait(identity, timeout=2)
    assert "external private payload" not in str(captured.value)
