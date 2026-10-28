"""Resolve Docker CLI precedence once without reading login material."""

import json
import os
import shutil
import subprocess
from collections.abc import Mapping

from py_docker.connection.models import ResolvedConnection
from py_docker.connection.settings import ConnectionSettings
from py_docker.errors import ConnectionConfigurationError


class ConnectionResolver:
    """Use explicit settings, DOCKER_CONTEXT, DOCKER_HOST, then active context."""

    def resolve(self, settings: ConnectionSettings, environment: Mapping[str, str] | None = None) -> ResolvedConnection:
        env = dict(os.environ if environment is None else environment)
        # TLS/SSH support requires a future explicit, tested contract. Never ignore it.
        if any(env.get(key) for key in ("DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_TLS")):
            raise ConnectionConfigurationError("resolve TLS configuration")
        context = settings.context or env.get("DOCKER_CONTEXT")
        if settings.endpoint:
            endpoint, source = settings.endpoint, "explicit"
        elif context:
            endpoint, source = self._context_endpoint(context, env), "context"
        elif env.get("DOCKER_HOST"):
            endpoint, source = env["DOCKER_HOST"], "environment"
        elif shutil.which("docker", path=env.get("PATH")):
            endpoint, source = self._context_endpoint(None, env), "active-context"
        else:
            endpoint = "npipe:////./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock"
            source = "platform-default"
        local = endpoint.startswith(("unix:///", "npipe:////./pipe/"))
        if not local and not (settings.allow_remote and endpoint.startswith("tcp://")):
            raise ConnectionConfigurationError("select supported Docker endpoint")
        return ResolvedConnection(endpoint=endpoint, source=source, local=local)

    def _context_endpoint(self, context: str | None, environment: dict[str, str]) -> str:
        command = ["docker", "context", "inspect"]
        if context is not None:
            command.append(context)
        try:
            result = subprocess.run(command, env=environment, capture_output=True, timeout=10, check=True)
            value = json.loads(result.stdout)
            endpoint = value[0]["Endpoints"]["docker"]["Host"]
            if not isinstance(endpoint, str):
                raise ValueError("invalid endpoint")
            return endpoint
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
            raise ConnectionConfigurationError("resolve Docker context") from None
