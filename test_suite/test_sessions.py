"""Internal lifecycle controls; real interactive Docker evidence is separate."""

import json
import threading
from unittest.mock import Mock

import pytest

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReceipt,
    ContainerReservation,
    ContainerSpec,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.errors import DockerOperationError
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
