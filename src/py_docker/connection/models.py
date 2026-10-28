"""Resolved connection identity, independent of mutable process environment."""

from pydantic import BaseModel, ConfigDict


class ResolvedConnection(BaseModel):
    """The exact selected daemon; local means Unix socket or Windows named pipe."""

    model_config = ConfigDict(frozen=True)
    endpoint: str
    source: str
    local: bool
