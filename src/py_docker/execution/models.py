"""Command outcomes; payload bytes are deliberately omitted from serialization."""

from pydantic import BaseModel, ConfigDict, Field


class CommandResult(BaseModel):
    """Exit status is confirmed by exec inspection after output EOF."""

    model_config = ConfigDict(frozen=True)
    exit_code: int
    stdout: bytes = Field(repr=False, exclude=True)
    stderr: bytes = Field(repr=False, exclude=True)
