"""SDK extension isolates Docker connections from ambient HTTP proxy settings."""

from docker import APIClient, DockerClient


class DirectAPIClient(APIClient):
    """Disable environment proxy/netrc discovery before the first API request."""

    def request(self, *args, **kwargs):
        self.trust_env = False
        return super().request(*args, **kwargs)


class DirectDockerClient(DockerClient):
    """Use the normal SDK collections with a direct low-level HTTP session."""

    def __init__(self, *args, **kwargs):
        self.api = DirectAPIClient(*args, **kwargs)
