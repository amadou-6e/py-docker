"""Command outcomes; payload bytes are deliberately omitted from serialization."""

from pydantic import BaseModel, ConfigDict, Field


class CommandResult(BaseModel):
    """Process exit is confirmed by exec inspection or an owned container wait."""

    model_config = ConfigDict(frozen=True)
    exit_code: int = Field(
        description="Confirmed process exit code from exec inspection or container wait; zero conventionally means success."
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
