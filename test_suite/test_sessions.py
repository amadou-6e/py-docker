"""Internal lifecycle controls; real interactive Docker evidence is separate."""

import json
import threading
from unittest.mock import Mock, patch

import pytest

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReceipt,
    ContainerReservation,
    ContainerSpec,
    Mount,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.errors import CleanupUnconfirmedError, DockerOperationError
from py_docker.sessions.models import ContainerSession
from py_docker.sessions.service import Sessions
from py_docker.streams.models import StreamLimits


def test_observed_id_recovery_accepts_external_supervisor_removal(tmp_path):
    """Recover by immutable ID after the independent owner removed the container."""
    path = tmp_path.joinpath("receipt.json")
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(
        id="a" * 64, name=reservation.name, labels=reservation.labels
    )
    with ReceiptStore(path) as store:
        store.save(reservation)
        store.observe(reservation, identity)
    recorded = ContainerReceipt.from_private_record(json.loads(path.read_text()))
    assert recorded.identity == identity
    containers = Mock()
    with ReceiptStore(path) as store:
        store.recover(containers)
    containers.reconcile.assert_not_called()
    containers.remove.assert_called_once_with(identity, force=True)
    assert not path.exists()


def test_session_attach_before_start_observed_id_and_cross_thread_terminate(tmp_path):
    """Thread-safe removal leaves creator-owned receipt reconciliation intact."""
    path = tmp_path.joinpath("receipt.json")
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(
        id="a" * 64, name=reservation.name, labels=reservation.labels
    )
    containers, execution = Mock(), Mock()
    containers.reserve.return_value = reservation
    containers.create.return_value = identity
    ordered = Mock()
    ordered.attach_mock(containers, "containers")
    ordered.attach_mock(execution, "execution")
    request = ContainerSession(
        spec=ContainerSpec(image="sha256:" + "b" * 64, name="owned", stdin_open=True),
        limits=StreamLimits(seconds=2, max_bytes=1024),
        receipt_path=path,
    )
    session = Sessions(containers, execution).open(request)
    assert (
        ContainerReceipt.from_private_record(json.loads(path.read_text())).identity
        == identity
    )
    calls = [str(call) for call in ordered.mock_calls]
    assert next(
        i for i, c in enumerate(calls) if c.startswith("call.execution.attach(")
    ) < next(i for i, c in enumerate(calls) if c.startswith("call.containers.start("))
    worker = threading.Thread(target=session.terminate)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert path.exists()
    session.close()
    assert not path.exists()


def test_observed_id_cannot_be_rebound(tmp_path):
    """An observed receipt cannot silently change resource identity."""
    path = tmp_path.joinpath("receipt.json")
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    with ReceiptStore(path) as store:
        store.save(reservation)
        store.observe(
            reservation,
            ContainerIdentity(id="a" * 64, name="owned", labels=reservation.labels),
        )
        with pytest.raises(DockerOperationError):
            store.observe(
                reservation,
                ContainerIdentity(id="b" * 64, name="owned", labels=reservation.labels),
            )
    assert (
        ContainerReceipt.from_private_record(json.loads(path.read_text())).observed_id
        == "a" * 64
    )


def test_desktop_mount_normalization_is_endpoint_and_identity_specific():
    """Accept the observed local translation without weakening mount restrictions."""
    mount = Mount(
        type="bind", source=r"C:\private\source", target="/source", read_only=True
    )
    actual = {
        "Type": "bind",
        "Source": "/run/desktop/mnt/host/c/private/source",
        "Target": "/source",
        "ReadOnly": True,
    }
    assert mount.matches_readback(actual, local_npipe=True)
    assert not mount.matches_readback(actual, local_npipe=False)
    for changes in (
        {"ReadOnly": False},
        {"Target": "/other"},
        {"Source": "/run/desktop/mnt/host/c/private/other"},
        {"Type": "volume"},
        {"BindOptions": {"Propagation": "shared"}},
    ):
        assert not mount.matches_readback(dict(actual, **changes), local_npipe=True)
    writable = Mount(type="bind", source="/existing", target="/source")
    omitted_false = {"Type": "bind", "Source": "/existing", "Target": "/source"}
    assert writable.matches_readback(omitted_false, local_npipe=False)
    assert not writable.matches_readback(
        dict(omitted_false, ReadOnly=None), local_npipe=False
    )


def test_observation_replace_failure_keeps_original_intent(tmp_path):
    """A failed atomic ID update neither corrupts intent nor leaks a temp record."""
    path = tmp_path.joinpath("receipt.json")
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(id="a" * 64, name="owned", labels=reservation.labels)
    with ReceiptStore(path) as store:
        store.save(reservation)
        before = path.read_bytes()
        with patch(
            "py_docker.containers.receipts.os.replace",
            side_effect=OSError("private raw control"),
        ):
            with pytest.raises(CleanupUnconfirmedError) as caught:
                store.observe(reservation, identity)
        assert path.read_bytes() == before
        assert "private raw control" not in str(caught.value)
        assert not list(tmp_path.glob(".container-receipt-*"))


@pytest.mark.parametrize("phase", ["attach", "start"])
def test_session_open_failure_cleans_once_and_preserves_safe_primary(tmp_path, phase):
    """A partially opened session never retries create or strands observed intent."""
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(id="a" * 64, name="owned", labels=reservation.labels)
    containers, execution = Mock(), Mock()
    containers.reserve.return_value = reservation
    containers.create.return_value = identity
    primary = DockerOperationError("internal " + phase)
    (execution.attach if phase == "attach" else containers.start).side_effect = primary
    request = ContainerSession(
        spec=ContainerSpec(image="sha256:" + "b" * 64, name="owned", stdin_open=True),
        limits=StreamLimits(seconds=2, max_bytes=1024),
        receipt_path=tmp_path.joinpath("receipt.json"),
    )
    with pytest.raises(DockerOperationError) as caught:
        Sessions(containers, execution).open(request)
    assert caught.value is primary
    assert not request.receipt_path.exists()
    containers.create.assert_called_once()
    containers.remove.assert_called_once_with(identity, force=True)


def test_context_cleanup_keeps_safe_application_failure(tmp_path):
    """Cleanup uncertainty takes precedence while retaining the safe primary code."""
    reservation = ContainerReservation(name="owned", labels={"owner": "private"})
    identity = ContainerIdentity(id="a" * 64, name="owned", labels=reservation.labels)
    containers, execution = Mock(), Mock()
    containers.reserve.return_value = reservation
    containers.create.return_value = identity
    containers.remove.side_effect = DockerOperationError("internal removal control")
    request = ContainerSession(
        spec=ContainerSpec(image="sha256:" + "b" * 64, name="owned", stdin_open=True),
        limits=StreamLimits(seconds=2, max_bytes=1024),
        receipt_path=tmp_path.joinpath("receipt.json"),
    )
    primary = DockerOperationError("internal application control")
    with (
        pytest.raises(CleanupUnconfirmedError) as caught,
        Sessions(containers, execution).open(request),
    ):
        raise primary
    assert caught.value.primary is primary
    assert request.receipt_path.exists()
