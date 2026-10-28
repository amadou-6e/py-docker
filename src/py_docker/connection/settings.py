"""Caller-supplied Docker connection settings."""

import os
from collections.abc import Mapping

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

CONTEXT_INSPECTION_TIMEOUT_SECONDS = 10
DOCKER_TLS_ENVIRONMENT_KEYS = ("DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_TLS")
UNIX_DEFAULT_ENDPOINT = "unix:///var/run/docker.sock"
WINDOWS_DEFAULT_ENDPOINT = "npipe:////./pipe/docker_engine"
SDK_API_VERSION = "auto"


class ConnectionSettings(BaseSettings):
    """Library settings; Docker CLI environment is resolved separately."""

    model_config = SettingsConfigDict(
        env_prefix="PY_DOCKER_", extra="forbid", frozen=True, hide_input_in_errors=True
    )
    endpoint: str | None = Field(
        default=None,
        description="Explicit Docker daemon endpoint; None follows the supplied Docker environment.",
    )
    context: str | None = Field(
        default=None,
        description="Explicit Docker CLI context; None follows the supplied environment or active context.",
    )
    timeout_seconds: float = Field(
        default=30,
        gt=0,
        allow_inf_nan=False,
        description="Positive per-request SDK timeout in seconds, separate from stream deadlines.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Disable ambient settings sources in favor of explicit constructor values.

        Parameters
        ----------
        settings_cls : type[BaseSettings]
            Settings class supplied by the pydantic-settings source hook.
        init_settings : PydanticBaseSettingsSource
            Explicit constructor source, the only enabled automatic source.
        env_settings : PydanticBaseSettingsSource
            Ambient environment source, intentionally disabled.
        dotenv_settings : PydanticBaseSettingsSource
            Dotenv source, intentionally disabled.
        file_secret_settings : PydanticBaseSettingsSource
            Filesystem secret source, intentionally disabled.

        Returns
        -------
        tuple[PydanticBaseSettingsSource, ...]
            The constructor source only; no ambient, dotenv or secret-file loading.
        """
        return (init_settings,)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "ConnectionSettings":
        """Validate library settings from only the supplied environment snapshot.

        Parameters
        ----------
        environment : Mapping[str, str]
            Complete supplied snapshot; no fallback to ambient process values.

        Returns
        -------
        'ConnectionSettings'
            Validated settings independent of unrelated ambient values.
        """
        values = {}
        for name in cls.model_fields:
            key = "PY_DOCKER_" + name.upper()
            if key in environment:
                values[name] = environment[key]
        return cls(**values)

    @staticmethod
    def environment_snapshot(
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Capture exactly the supplied environment or the current process.

        Parameters
        ----------
        environment : Mapping[str, str] or None
            Explicit complete environment; even an empty mapping is respected.

        Returns
        -------
        dict[str, str]
            Owned snapshot; later process changes cannot alter endpoint selection.
        """
        return dict(os.environ if environment is None else environment)
