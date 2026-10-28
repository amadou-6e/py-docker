"""Resolve Docker CLI precedence once without reading login material."""

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from py_docker.connection import settings as connection_settings
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
        """Select one supported endpoint without relaxing remote-access policy.

        Parameters
        ----------
        settings : ConnectionSettings
            Validated connection settings supplied by the caller.
        environment : Mapping[str, str] or None
            Complete caller environment snapshot; None captures the process environment.
        allow_remote : bool
            Explicit permission for supported remote endpoints; never inferred from environment.

        Returns
        -------
        ResolvedConnection
            Selected daemon endpoint, selection source and local-transport status.

        Raises
        ------
        ConnectionConfigurationError
            The endpoint or selected context is unsupported; no resource mutation is sent.
        """
        env = ConnectionSettings.environment_snapshot(environment)
        # TLS/SSH support requires a future explicit, tested contract. Never ignore it.
        if any(env.get(key) for key in connection_settings.DOCKER_TLS_ENVIRONMENT_KEYS):
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
                connection_settings.WINDOWS_DEFAULT_ENDPOINT
                if os.name == "nt"
                else connection_settings.UNIX_DEFAULT_ENDPOINT
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
        """Read Docker context metadata through the absolute CLI executable.

        Parameters
        ----------
        context : str or None
            Explicit CLI context name, or None for the active context.
        environment : Mapping[str, str]
            Complete supplied snapshot; ambient values are not added.

        Returns
        -------
        str
            Selected Docker endpoint; no authentication material is returned.

        Raises
        ------
        ConnectionConfigurationError
            The endpoint or selected context is unsupported; no resource mutation is sent.
        """
        executable = self._executable(environment)
        if executable is None:
            raise ConnectionConfigurationError("find Docker CLI for context selection")
        command = [executable, "context", "inspect"]
        if context is not None:
            command.append(context)
        try:
            result = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                timeout=connection_settings.CONTEXT_INSPECTION_TIMEOUT_SECONDS,
                check=True,
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
        """Find Docker only in explicit absolute PATH directories.

        Parameters
        ----------
        environment : Mapping[str, str]
            Complete supplied snapshot; ambient values are not added.

        Returns
        -------
        str | None
            Absolute executable path, or None when no supported PATH entry contains Docker.

        Raises
        ------
        ConnectionConfigurationError
            The endpoint or selected context is unsupported; no resource mutation is sent.
        """
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
