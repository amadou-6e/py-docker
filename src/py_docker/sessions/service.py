"""Open one owned interactive container, with no retry or CLI fallback."""

from pathlib import Path

from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import (
    CleanupUnconfirmedError,
    CreationUnconfirmedError,
    DockerOperationError,
)
from py_docker.execution.service import Execution
from py_docker.sessions.models import ContainerSession
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

    def open(self, request: ContainerSession) -> Session:
        """Persist intent, create, observe ID, attach stdin, then start once.

        Parameters
        ----------
        request : ContainerSession
            Validated immutable launch with explicit stream limits and private state.

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
        store = ReceiptStore(request.receipt_path)
        store.__enter__()
        reservation = None
        identity = None
        stream = None
        pending = False
        try:
            store.recover(self._containers)
            reservation = self._containers.reserve(request.spec)
            store.save(reservation)
            pending = True
            try:
                identity = self._containers.create(request.spec, reservation)
            except CreationUnconfirmedError:
                raise
            except DockerOperationError as error:
                try:
                    store.discard_unstarted(reservation)
                    pending = False
                except CleanupUnconfirmedError as failure:
                    failure.primary = error
                    raise
                raise
            store.observe(reservation, identity)
            stream = self._execution.attach(
                identity, request.limits, stdin=request.spec.stdin_open
            )
            self._containers.start(identity)
            return Session(self._containers, store, reservation, identity, stream)
        except Exception as failure:
            primary = (
                failure
                if isinstance(failure, DockerOperationError)
                else DockerOperationError("open interactive session")
            )
            error = primary
            if pending:
                try:
                    store.cleanup(self._containers, reservation, identity)
                except CleanupUnconfirmedError as cleanup:
                    cleanup.primary = primary
                    error = cleanup
            if stream is not None:
                try:
                    stream.close()
                except DockerOperationError:
                    pass
            store.__exit__(type(error), error, None)
            raise error from None
