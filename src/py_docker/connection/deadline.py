"""Lexical per-client Engine admission without shared SDK timeout mutation."""

from contextvars import ContextVar
from typing import ClassVar

from docker import APIClient

from py_docker.connection.models import RequestBudget
from py_docker.errors import DockerOperationError


class RequestDeadlineScope:
    """Bind one budget to a held API client; same-client nesting is refused.

    Parameters
    ----------
    api : APIClient
        Existing client, held and compared by object identity.
    budget : RequestBudget
        Lifecycle-owned deadline and create-dispatch witness.
    """

    _active: ClassVar[ContextVar[tuple["RequestDeadlineScope", ...]]] = ContextVar(
        "py_docker_request_deadlines", default=()
    )

    def __init__(self, api: APIClient, budget: RequestBudget) -> None:
        """Retain the existing client without acquiring another connection."""
        self._api, self._budget, self._token = api, budget, None

    def __enter__(self) -> None:
        """Bind even an expired budget; send admission owns expiry failure."""
        active = self._active.get()
        if any(scope._api is self._api for scope in active):
            raise DockerOperationError("nest same-client request deadline")
        self._token = self._active.set((*active, self))

    def __exit__(self, *_: object) -> None:
        """Restore exactly this context's previous bindings after any failure."""
        if self._token is not None:
            self._active.reset(self._token)
            self._token = None

    @classmethod
    def current(cls, api: APIClient) -> RequestBudget | None:
        """Return only the budget bound to this actual APIClient object."""
        return next(
            (
                scope._budget
                for scope in reversed(cls._active.get())
                if scope._api is api
            ),
            None,
        )
