"""Open one owned interactive container, with no retry or CLI fallback."""

import time
from contextlib import nullcontext
from pathlib import Path

from py_docker.connection.deadline import RequestDeadlineScope
from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import (
    CleanupUnconfirmedError,
    CreationUnconfirmedError,
    DockerOperationError,
)
from py_docker.execution.service import Execution
from py_docker.sessions.models import ContainerSession, SessionDeadline
from py_docker.sessions.session import Session


class Sessions:
    """Reuse a client's container and attachment services.

    Parameters
    ----------
    containers : Containers
        Existing operations scoped to one explicit Docker endpoint.
    execution : Execution
        Binary attachment service sharing that same client.
    """

    def __init__(self, containers: Containers, execution: Execution) -> None:
        """Retain services; the caller continues to own the client lifetime."""
        self._containers = containers
        self._execution = execution

    def recover(self, receipt_path: Path) -> None:
        """Reconcile one previous private session receipt before another dispatch.

        Parameters
        ----------
        receipt_path : Path
            Existing private receipt location on its original endpoint.
        """
        with ReceiptStore(receipt_path) as store:
            store.recover(self._containers)

    def open(
        self,
        request: ContainerSession,
        *,
        deadline: float | None = None,
        cleanup_seconds: float | None = None,
    ) -> Session:
        """Persist intent, create, observe ID, attach stdin, then start once.

        Parameters
        ----------
        request : ContainerSession
            Validated immutable launch with explicit stream limits and private state.
        deadline : float or None
            Absolute monotonic send-admission deadline; None retains current behavior.
        cleanup_seconds : float or None
            Positive separate cleanup reserve, required with an explicit deadline.

        Returns
        -------
        Session
            Caller-owned interactive session; close it on this same thread.

        Raises
        ------
        CleanupUnconfirmedError
            Failure cleanup cannot be confirmed; durable intent is retained.
        DockerOperationError
            Launch, attachment or start failed; there is no automatic retry.
        """
        limits = SessionDeadline.from_options(deadline, cleanup_seconds)
        if limits is not None:
            limits.normal.remaining_seconds(time.monotonic())
        if (
            not isinstance(self._containers.endpoint, str)
            or not self._containers.endpoint
        ):
            raise DockerOperationError("record original container endpoint")
        store = ReceiptStore(request.receipt_path)
        store.__enter__()
        reservation = None
        identity = None
        stream = None
        pending = False
        try:
            with (
                RequestDeadlineScope(self._containers.sdk.api, limits.normal)
                if limits
                else nullcontext()
            ):
                store.recover(self._containers)
                reservation = self._containers.reserve(request.spec)
                store.save(reservation, endpoint=self._containers.endpoint)
                pending = True
                try:
                    identity = self._containers.create(request.spec, reservation)
                except CreationUnconfirmedError:
                    raise
                except DockerOperationError as error:
                    pending = False
                    try:
                        store.discard_unstarted(reservation)
                    except CleanupUnconfirmedError as failure:
                        failure.primary = error
                        raise
                    raise
                store.observe(reservation, identity)
                stream = self._execution.attach(
                    identity, request.limits, stdin=request.spec.stdin_open
                )
                self._containers.start(identity)
                if limits:
                    limits.normal.remaining_seconds(time.monotonic())
                return Session(
                    self._containers, store, reservation, identity, stream, limits
                )
        except Exception as failure:
            primary = (
                failure
                if isinstance(failure, DockerOperationError)
                else DockerOperationError("open interactive session")
            )
            error = primary
            try:
                if pending:
                    try:
                        with (
                            RequestDeadlineScope(
                                self._containers.sdk.api,
                                limits.cleanup_budget(time.monotonic()),
                            )
                            if limits
                            else nullcontext()
                        ):
                            store.cleanup(self._containers, reservation, identity)
                    except Exception as failure:
                        error = (
                            failure
                            if isinstance(failure, CleanupUnconfirmedError)
                            else CleanupUnconfirmedError(
                                "bind or complete failed-session cleanup", reservation
                            )
                        )
                        error.primary = primary
            finally:
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass  # Preserve the primary or stronger cleanup uncertainty.
                finally:
                    try:
                        store.__exit__(type(error), error, None)
                    except Exception:
                        if not isinstance(error, CleanupUnconfirmedError):
                            error = CleanupUnconfirmedError(
                                "release failed-session receipt", reservation, primary
                            )
            raise error from None
