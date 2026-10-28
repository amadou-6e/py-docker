"""SDK extension isolates Docker connections from ambient HTTP proxy settings."""

from typing import Any

from docker import APIClient, DockerClient
from requests import Response


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
