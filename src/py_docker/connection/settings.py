"""Caller-supplied Docker connection settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectionSettings(BaseSettings):
    """Library settings; Docker CLI environment is resolved separately."""

    model_config = SettingsConfigDict(env_prefix="PY_DOCKER_", extra="forbid", frozen=True)
    endpoint: str | None = None
    context: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, allow_inf_nan=False)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        """Use explicit values only; environment snapshots are parsed below."""
        return (init_settings,)

    @classmethod
    def from_environment(cls, environment):
        """Read supported settings from the caller's environment snapshot only."""
        values = {}
        for name in ("endpoint", "context", "timeout_seconds"):
            key = "PY_DOCKER_" + name.upper()
            if key in environment:
                values[name] = environment[key]
        return cls(**values)
