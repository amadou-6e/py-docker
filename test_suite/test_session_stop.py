"""Internal monitor controls; real container cancellation is checked separately."""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from py_docker.errors import CleanupUnconfirmedError, DockerOperationError
from py_docker.sessions.session import Session


def test_monitor_only_terminates_owned_id_and_creator_closes_receipt():
    """Stopping cannot clear a receipt from the background monitor thread."""
    containers, store, stopped = Mock(), MagicMock(), threading.Event()
    identity = object()
    containers.remove.side_effect = lambda *args, **kwargs: stopped.set()
    session = Session(containers, store, Mock(), identity, Mock())
    with session.stop_on(lambda: True):
        assert stopped.wait(2)
        store.cleanup.assert_not_called()
    containers.remove.assert_called_once_with(identity, force=True)
    session.close()
    store.cleanup.assert_called_once()
    assert session.cleanup_confirmed


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_failed_predicate_stops_container_and_preserves_cleanup_precedence(
    cleanup_fails,
):
    """A predicate failure is safe and never hides unresolved owned cleanup."""
    containers, store, stopped = Mock(), MagicMock(), threading.Event()
    containers.remove.side_effect = lambda *args, **kwargs: stopped.set()
    if cleanup_fails:
        store.cleanup.side_effect = CleanupUnconfirmedError("internal cleanup")
    session = Session(containers, store, Mock(), Mock(), Mock())

    def fail():
        """Inject an internal callback failure without exposing its text."""
        raise ValueError("private callback payload")

    expected = CleanupUnconfirmedError if cleanup_fails else DockerOperationError
    with pytest.raises(expected) as caught:
        with session, session.stop_on(fail):
            assert stopped.wait(2)
    assert "private" not in str(caught.value)
    assert session.cleanup_confirmed is not cleanup_fails
    if cleanup_fails:
        assert isinstance(caught.value.primary, DockerOperationError)


def test_body_failure_is_preserved_and_monitor_start_failure_is_safe():
    """The monitor neither replaces application failures nor leaks thread errors."""
    session = Session(Mock(), MagicMock(), Mock(), Mock(), Mock())
    primary = ValueError("application failure")
    with pytest.raises(ValueError) as caught:
        with session.stop_on(lambda: False):
            raise primary
    assert caught.value is primary
    with patch(
        "threading.Thread.start", side_effect=RuntimeError("private thread detail")
    ):
        with pytest.raises(
            DockerOperationError, match="start container stop monitor"
        ) as caught:
            with session.stop_on(lambda: False):
                pytest.fail("monitor startup failed")
    assert "private" not in str(caught.value)
    session.close()
