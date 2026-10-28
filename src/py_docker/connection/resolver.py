"""Resolve Docker CLI precedence once without reading login material."""

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from py_docker.connection.models import ResolvedConnection
from py_docker.connection.settings import ConnectionSettings
from py_docker.errors import ConnectionConfigurationError


class ConnectionResolver:
    """Resolve explicit settings; reject ambiguous host/context environment."""

    def resolve(
        self,
        settings: ConnectionSettings,
        environment: Mapping[str, str] | None = None,
        *,
        allow_remote: bool = False,
    ) -> ResolvedConnection:
        env = dict(os.environ if environment is None else environment)
        # TLS/SSH support requires a future explicit, tested contract. Never ignore it.
        if any(
            env.get(key)
            for key in ("DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_TLS")
        ):
            raise ConnectionConfigurationError("resolve TLS configuration")
        context = settings.context or env.get("DOCKER_CONTEXT")
        if (
            not settings.endpoint
            and not settings.context
            and env.get("DOCKER_CONTEXT")
            and env.get("DOCKER_HOST")
        ):
            raise ConnectionConfigurationError(
                "choose either DOCKER_CONTEXT or DOCKER_HOST"
            )
        if settings.endpoint:
            endpoint, source = settings.endpoint, "explicit"
        elif context:
            endpoint, source = self._context_endpoint(context, env), "context"
        elif env.get("DOCKER_HOST"):
            endpoint, source = env["DOCKER_HOST"], "environment"
        elif self._executable(env):
            endpoint, source = self._context_endpoint(None, env), "active-context"
        else:
            endpoint = (
                "npipe:////./pipe/docker_engine"
                if os.name == "nt"
                else "unix:///var/run/docker.sock"
            )
            source = "platform-default"
        local = endpoint.startswith(("unix:///", "npipe:////./pipe/"))
        parsed = urlsplit(endpoint)
        if (
            parsed.username is not None
            or parsed.password is not None
            or any(character.isspace() for character in endpoint)
        ):
            raise ConnectionConfigurationError("select credential-free Docker endpoint")
        if not local and not (allow_remote and endpoint.startswith("tcp://")):
            raise ConnectionConfigurationError("select supported Docker endpoint")
        return ResolvedConnection(endpoint=endpoint, source=source, local=local)

    def _context_endpoint(
        self, context: str | None, environment: dict[str, str]
    ) -> str:
        executable = self._executable(environment)
        if executable is None:
            raise ConnectionConfigurationError("find Docker CLI for context selection")
        command = [executable, "context", "inspect"]
        if context is not None:
            command.append(context)
        try:
            result = subprocess.run(
                command, env=environment, capture_output=True, timeout=10, check=True
            )
            value = json.loads(result.stdout)
            if value[0].get("TLSMaterial") or value[0]["Endpoints"]["docker"].get(
                "SkipTLSVerify"
            ):
                raise ValueError("unsupported context TLS policy")
            endpoint = value[0]["Endpoints"]["docker"]["Host"]
            if not isinstance(endpoint, str):
                raise ValueError("invalid endpoint")
            return endpoint
        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ):
            raise ConnectionConfigurationError("resolve Docker context") from None

    def _executable(self, environment: Mapping[str, str]) -> str | None:
        """Search explicit absolute PATH entries, never implicit Windows cwd."""
        search = next(
            (value for key, value in environment.items() if key.upper() == "PATH"), ""
        )
        for directory in search.split(os.pathsep):
            parent = Path(directory.strip('"'))
            if not directory or not parent.is_absolute():
                continue
            candidate = Path(parent, "docker.exe" if os.name == "nt" else "docker")
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None
