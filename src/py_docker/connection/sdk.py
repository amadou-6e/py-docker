"""SDK extension isolates Docker connections from ambient HTTP proxy settings."""

import re
import time
from typing import Any
from urllib.parse import urlsplit

from docker import APIClient, DockerClient
from requests import PreparedRequest, Response

from py_docker.connection.deadline import RequestDeadlineScope
from py_docker.errors import CreateNotSentDeadlineError, DeadlineError


class DirectAPIClient(APIClient):
    """Disable environment proxy/netrc discovery before the first API request."""

    def request(self, *args: Any, **kwargs: Any) -> Response:
        """Send the SDK request without ambient HTTP proxy or netrc discovery.

        Parameters
        ----------
        args : tuple
            Positional arguments forwarded unchanged to the third-party SDK contract.
        kwargs : dict
            Keyword arguments forwarded unchanged to the third-party SDK contract.

        Returns
        -------
        Response
            The SDK response using the caller-selected daemon and request options.
        """
        self.trust_env = False
        return super().request(*args, **kwargs)

    def send(self, request: PreparedRequest, **kwargs: Any) -> Response:
        """Admit each scoped send, including direct attach and redirect requests.

        Parameters
        ----------
        request : PreparedRequest
            SDK-prepared request; contents are never retained in diagnostics.
        kwargs : dict
            Per-call options, with scalar inactivity timeout clamped when scoped.

        Returns
        -------
        Response
            SDK response; inactivity limits do not prove a wall-time bound.
        """
        budget = RequestDeadlineScope.current(self)
        if budget is not None:
            create = request.method == "POST" and bool(
                re.fullmatch(
                    r"/(?:v[0-9.]+/)?containers/create", urlsplit(request.url).path
                )
            )
            try:
                kwargs["timeout"] = budget.timeout_seconds(
                    kwargs.get("timeout"), self.timeout, time.monotonic()
                )
            except DeadlineError:
                if create and not budget.create_dispatched:
                    raise CreateNotSentDeadlineError("admit container create") from None
                raise
            if create:
                budget.create_dispatched = True
        return super().send(request, **kwargs)


class DirectDockerClient(DockerClient):
    """Use the normal SDK collections with a direct low-level HTTP session.

    Parameters
    ----------
    args : tuple
        Positional arguments forwarded unchanged to the third-party SDK contract.
    kwargs : dict
        Keyword arguments forwarded unchanged to the third-party SDK contract.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build standard SDK collections around a direct low-level session."""
        self.api = DirectAPIClient(*args, **kwargs)
