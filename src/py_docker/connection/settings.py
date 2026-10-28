"""Caller-supplied Docker connection settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectionSettings(BaseSettings):
    """Library settings; Docker CLI environment is resolved separately."""

    model_config = SettingsConfigDict(env_prefix="PY_DOCKER_", extra="forbid", frozen=True)
    endpoint: str | None = None
    context: str | None = None
    allow_remote: bool = False
    timeout_seconds: float = Field(default=30, gt=0, allow_inf_nan=False)
