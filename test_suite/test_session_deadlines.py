"""Internal admission and receipt controls; these do not establish live Docker acceptance."""

import json
import threading
from contextlib import closing
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import Response

from py_docker.connection.deadline import RequestDeadlineScope
from py_docker.connection.models import RequestBudget
from py_docker.connection.sdk import DirectDockerClient
from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerSpec,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import (
    CleanupUnconfirmedError,
    CreateNotSentDeadlineError,
    CreationUnconfirmedError,
    DeadlineError,
    DockerOperationError,
    JobCancelledError,
)
from py_docker.execution.service import Execution
from py_docker.jobs.models import ContainerJob
from py_docker.jobs.service import Jobs
from py_docker.sessions.models import ContainerSession, SessionDeadline
from py_docker.sessions.service import Sessions
from py_docker.streams.models import Frame, StreamBudget, StreamLimits


@pytest.fixture(autouse=True)
def _isolated_docker_config(tmp_path, monkeypatch):
    """Keep SDK initialization away from the person's Docker login configuration."""
    monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path.joinpath("empty-config")))


def _response(payload, status=200):
    """Return an internal SDK HTTP response without connecting to an Engine."""
    response = Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    return response


def _runtime(tmp_path):
    """Use real receipt orchestration with injected container/stream controls."""
    containers, execution = Mock(endpoint="unix:///controlled.sock"), Mock()
    reservation = ContainerReservation(name="owned", labels={"owner": "private-test"})
    identity = ContainerIdentity(id="b" * 64, name="owned", labels=reservation.labels)
    containers.reserve.return_value = reservation
    containers.create.return_value = identity
    containers.reconcile.return_value = identity
    request = ContainerSession(
        spec=ContainerSpec(image="sha256:" + "a" * 64, name="owned"),
        limits=StreamLimits(seconds=10, max_bytes=1024),
        receipt_path=tmp_path.joinpath("receipt.json"),
    )
    return containers, execution, request


@pytest.mark.parametrize(
    "deadline,cleanup",
    [
        (True, 1),
        (1, True),
        (None, 1),
        (1, None),
        (float("inf"), 1),
        (1, float("nan")),
        (1, 0),
    ],
)
def test_invalid_options_precede_receipt_and_engine(tmp_path, deadline, cleanup):
    """Strict paired finite options fail before a lock file or resource operation."""
    containers, execution, request = _runtime(tmp_path)
    with pytest.raises(ValueError):
        Sessions(containers, execution).open(
            request, deadline=deadline, cleanup_seconds=cleanup
        )
    assert not list(tmp_path.iterdir())
    containers.reserve.assert_not_called()


def test_expired_open_does_not_acquire_receipt(tmp_path, monkeypatch):
    """A deadline already expired at admission proves no resource was requested."""
    monkeypatch.setattr("time.monotonic", lambda: 100)
    containers, execution, request = _runtime(tmp_path)
    with pytest.raises(DeadlineError):
        Sessions(containers, execution).open(request, deadline=99, cleanup_seconds=5)
    assert not list(tmp_path.iterdir())


def test_actual_send_clamps_direct_post_and_preserves_witness(monkeypatch):
    """Direct post/redirect-style sends use this client and retain first-create admission."""
    monkeypatch.setattr("time.monotonic", lambda: 100)
    with closing(
        DirectDockerClient(base_url="http://127.0.0.1:1", version="1.45", timeout=30)
    ) as sdk:
        budget = RequestBudget(deadline=100.0005)
        with patch(
            "requests.sessions.Session.send", return_value=_response({})
        ) as transport:
            with RequestDeadlineScope(sdk.api, budget):
                sdk.api.post("http://127.0.0.1:1/v1.45/containers/create", timeout=None)
                assert budget.create_dispatched
                with pytest.raises(DockerOperationError):
                    with RequestDeadlineScope(sdk.api, RequestBudget(deadline=200)):
                        pass
                assert RequestDeadlineScope.current(sdk.api) is budget
                assert budget.create_dispatched
            assert RequestDeadlineScope.current(sdk.api) is None
        assert 0 < transport.call_args.kwargs["timeout"] < 0.001
        budget.deadline = 99
        with (
            RequestDeadlineScope(sdk.api, budget),
            pytest.raises(DeadlineError) as caught,
        ):
            sdk.api.post("http://127.0.0.1:1/v1.45/containers/create")
        assert not isinstance(caught.value, CreateNotSentDeadlineError)


def test_client_identity_and_concurrent_contexts_are_independent(monkeypatch):
    """One shared SDK client can carry independent request admission in each thread."""
    monkeypatch.setattr("time.monotonic", lambda: 100)
    with closing(
        DirectDockerClient(base_url="http://127.0.0.1:1", version="1.45", timeout=30)
    ) as sdk:
        barrier, outcomes = threading.Barrier(2), []

        def request(deadline):
            with RequestDeadlineScope(sdk.api, RequestBudget(deadline=deadline)):
                barrier.wait(timeout=2)
                try:
                    sdk.api.get("http://127.0.0.1:1/_ping", timeout=3)
                    outcomes.append("sent")
                except DeadlineError:
                    outcomes.append("expired")

        with patch(
            "requests.sessions.Session.send", return_value=_response({})
        ) as transport:
            workers = [
                threading.Thread(target=request, args=(value,)) for value in (99, 110)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=3)
                assert not worker.is_alive()
        assert sorted(outcomes) == ["expired", "sent"]
        assert transport.call_count == 1
        assert transport.call_args.kwargs["timeout"] == 3
        assert RequestDeadlineScope.current(sdk.api) is None


@pytest.mark.parametrize("after_post", [False, True])
def test_real_high_level_create_distinguishes_first_post_and_hidden_inspect(
    tmp_path, monkeypatch, after_post
):
    """Actual docker-py create has a hidden GET; only an unadmitted first POST can discard."""
    clock, methods = [100], []
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    with closing(
        DirectDockerClient(base_url="http://127.0.0.1:1", version="1.45", timeout=30)
    ) as sdk:
        containers = Containers(sdk, endpoint="http://127.0.0.1:1")
        containers._verify_launch = Mock()
        request = ContainerSession(
            spec=ContainerSpec(image="sha256:" + "a" * 64, name="owned"),
            limits=StreamLimits(seconds=30, max_bytes=1024),
            receipt_path=tmp_path.joinpath("receipt.json"),
        )

        def send(prepared, **_):
            methods.append(prepared.method)
            if "/images/" in prepared.url:
                if not after_post:
                    clock[0] = 200
                return _response({"Id": request.spec.image, "Config": {}})
            if prepared.method == "POST":
                clock[0] = 200
                return _response({"Id": "b" * 64}, 201)
            return _response({"message": "not observed"}, 404)

        with patch("requests.sessions.Session.send", side_effect=send):
            if after_post:
                with pytest.raises(CleanupUnconfirmedError) as caught:
                    Sessions(containers, Execution(sdk)).open(
                        request, deadline=150, cleanup_seconds=5
                    )
                assert isinstance(caught.value.primary, CreationUnconfirmedError)
                assert request.receipt_path.exists()
                assert methods == ["GET", "POST", "GET"]
            else:
                with pytest.raises(CreateNotSentDeadlineError):
                    Sessions(containers, Execution(sdk)).open(
                        request, deadline=150, cleanup_seconds=5
                    )
                assert not request.receipt_path.exists()
                assert methods == ["GET"]
        with ReceiptStore(request.receipt_path):
            pass  # The real native lifecycle lock was released in either outcome.


@pytest.mark.parametrize("failure_phase", ["binding", "enter", "store"])
def test_failed_close_keeps_receipt_and_never_reports_cleanup_success(
    tmp_path, monkeypatch, failure_phase
):
    """B1: any cleanup binding/store failure closes stream/releases lock and remains failed."""
    monkeypatch.setattr("time.monotonic", lambda: 100)
    containers, execution, request = _runtime(tmp_path)
    session = Sessions(containers, execution).open(
        request, deadline=150, cleanup_seconds=5
    )
    target = (
        "py_docker.connection.deadline.RequestDeadlineScope.__enter__"
        if failure_phase == "enter"
        else "py_docker.sessions.session.RequestDeadlineScope"
        if failure_phase == "binding"
        else "py_docker.containers.receipts.ReceiptStore.cleanup"
    )
    with patch(target, side_effect=RuntimeError("private diagnostic must not escape")):
        with pytest.raises(CleanupUnconfirmedError) as caught:
            session.close()
    assert not session.cleanup_confirmed
    assert "private diagnostic" not in str(caught.value)
    with pytest.raises(CleanupUnconfirmedError) as repeated:
        session.close()
    assert repeated.value is caught.value
    assert request.receipt_path.exists()
    execution.attach.return_value.close.assert_called_once()
    with ReceiptStore(request.receipt_path):
        pass


@pytest.mark.parametrize("failure_phase", ["binding", "enter", "store"])
def test_open_failure_cleanup_exits_normal_scope_and_always_releases(
    tmp_path, monkeypatch, failure_phase
):
    """B2: acquired stream and real receipt lock survive neither cleanup failure mode."""
    monkeypatch.setattr("time.monotonic", lambda: 100)
    containers, execution, request = _runtime(tmp_path)
    primary = DockerOperationError("controlled start failure")
    containers.start.side_effect = primary
    entries = []

    def bind(api, budget):
        assert RequestDeadlineScope.current(api) is None
        entries.append(budget.deadline)
        if len(entries) == 2 and failure_phase == "binding":
            raise RuntimeError("private binding failure")
        if len(entries) == 2 and failure_phase == "enter":
            failed = MagicMock()
            failed.__enter__.side_effect = RuntimeError("private entry failure")
            return failed
        return RequestDeadlineScope(api, budget)

    with patch("py_docker.sessions.service.RequestDeadlineScope", side_effect=bind):
        with patch.object(
            ReceiptStore, "cleanup", side_effect=RuntimeError("private cleanup failure")
        ):
            with pytest.raises(CleanupUnconfirmedError) as caught:
                Sessions(containers, execution).open(
                    request, deadline=150, cleanup_seconds=5
                )
    assert caught.value.primary is primary
    assert entries == [150, 105]
    assert request.receipt_path.exists()
    assert "private" not in str(caught.value)
    execution.attach.return_value.close.assert_called_once()
    with ReceiptStore(request.receipt_path):
        pass


def test_absolute_stream_cap_and_late_attach_close_raw(monkeypatch):
    """Acquisition never resets an absolute deadline, even through endpoint-less Containers."""
    clock = [100]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    budget = StreamBudget.from_limits(
        StreamLimits(seconds=10, max_bytes=3), 100, deadline=102
    )
    assert budget.deadline == 102 and budget.remaining_bytes == 3
    sdk, raw = Mock(), Mock()
    identity = ContainerIdentity(id="b" * 64, name="owned", labels={"owner": "test"})
    sdk.containers.get.return_value.attrs = {
        "Id": identity.id,
        "Name": "owned",
        "Config": {"Labels": {"owner": "test"}},
    }

    def attach(*_, **__):
        clock[0] = 200
        return raw

    sdk.api.attach_socket.side_effect = attach
    with RequestDeadlineScope(sdk.api, RequestBudget(deadline=150)):
        with pytest.raises(DeadlineError):
            Execution(sdk).attach(identity, StreamLimits(seconds=30, max_bytes=1024))
    raw.close.assert_called_once()


def test_cleanup_reserve_is_never_reset_and_jobs_forward_options(tmp_path, monkeypatch):
    """One reserve is shared across termination/close and Jobs uses that same lifecycle."""
    limits = SessionDeadline.from_options(150, 5)
    assert (
        limits.cleanup_budget(100).deadline
        == limits.cleanup_budget(200).deadline
        == 105
    )
    monkeypatch.setattr("time.monotonic", lambda: 100)
    containers, execution, request = _runtime(tmp_path)
    execution.attach.return_value.read_frame.side_effect = [
        Frame(channel="stdout", data=b"ok"),
        None,
    ]
    containers.wait.return_value = 0
    with patch(
        "py_docker.jobs.service.Sessions.open",
        wraps=Sessions(containers, execution).open,
    ) as opened:
        result = Jobs(containers, execution).run(
            ContainerJob(
                spec=request.spec,
                limits=request.limits,
                receipt_path=request.receipt_path,
                wait_timeout_seconds=3,
            ),
            deadline=150,
            cleanup_seconds=5,
        )
    assert result.stdout == b"ok" and result.exit_code == 0
    assert opened.call_args.kwargs == {"deadline": 150, "cleanup_seconds": 5}
    stopped = threading.Event()
    stopped.set()
    with pytest.raises(JobCancelledError):
        Jobs(containers, execution).run(
            ContainerJob(
                spec=request.spec,
                limits=request.limits,
                receipt_path=request.receipt_path,
                wait_timeout_seconds=3,
            ),
            cancelled=stopped,
            deadline=True,
        )


def test_successful_terminate_can_leave_conservative_receipt_after_reserve(
    tmp_path, monkeypatch
):
    """A removal followed by expired verification never clears an unverified receipt."""
    clock = [100]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    containers, execution, request = _runtime(tmp_path)
    session = Sessions(containers, execution).open(
        request, deadline=150, cleanup_seconds=5
    )
    observed = []

    def remove(*_, **__):
        budget = RequestDeadlineScope.current(containers.sdk.api)
        observed.append(budget.deadline)
        budget.remaining_seconds(clock[0])
        clock[0] = 106

    containers.remove.side_effect = remove
    session.terminate()
    with pytest.raises(CleanupUnconfirmedError):
        session.close()
    assert observed == [105, 105]
    assert request.receipt_path.exists() and not session.cleanup_confirmed
    with ReceiptStore(request.receipt_path):
        pass


def test_actual_redirect_rechecks_send_without_losing_create_witness(monkeypatch):
    """Requests redirects recurse through the real send override before a second POST."""
    clock = [100]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    with closing(
        DirectDockerClient(base_url="http://127.0.0.1:1", version="1.45", timeout=30)
    ) as sdk:
        budget = RequestBudget(deadline=150)

        def redirect(_, prepared, **__):
            response = _response({}, 307)
            response.request, response.url = prepared, prepared.url
            response.headers["Location"] = prepared.url + "?redirect=1"
            response._content_consumed = True
            clock[0] = 200
            return response

        with patch(
            "requests.adapters.HTTPAdapter.send", autospec=True, side_effect=redirect
        ) as transport:
            with (
                RequestDeadlineScope(sdk.api, budget),
                pytest.raises(DeadlineError) as caught,
            ):
                sdk.api.post("http://127.0.0.1:1/v1.45/containers/create")
        assert transport.call_count == 1 and budget.create_dispatched
        assert not isinstance(caught.value, CreateNotSentDeadlineError)
