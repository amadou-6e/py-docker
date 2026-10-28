"""Command outcomes; payload bytes are deliberately omitted from serialization."""

from pydantic import BaseModel, ConfigDict, Field


class CommandResult(BaseModel):
    """Exit status is confirmed by exec inspection after output EOF."""

    model_config = ConfigDict(frozen=True)
    exit_code: int = Field(
        description="Confirmed Docker exec process exit code; zero conventionally means success."
    )
    stdout: bytes = Field(
        repr=False,
        exclude=True,
        description="Captured undecoded stdout bytes, excluded from dumps and representation.",
    )
    stderr: bytes = Field(
        repr=False,
        exclude=True,
        description="Captured undecoded stderr bytes, excluded from dumps and representation.",
    )
