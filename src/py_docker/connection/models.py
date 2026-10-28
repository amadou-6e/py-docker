"""Resolved connection identity, independent of mutable process environment."""

from pydantic import BaseModel, ConfigDict, Field


class ResolvedConnection(BaseModel):
    """The exact selected daemon; local means Unix socket or Windows named pipe."""

    model_config = ConfigDict(frozen=True)
    endpoint: str = Field(
        description="Exact selected daemon endpoint, pinned independently of later environment changes."
    )
    source: str = Field(
        description="Diagnostic selection source, such as explicit, context or platform-default."
    )
    local: bool = Field(
        description="Whether the endpoint is a local Unix socket or Windows named pipe."
    )
