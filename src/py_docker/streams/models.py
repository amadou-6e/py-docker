"""Stream budgets and demultiplexed binary frames."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StreamLimits(BaseModel):
    """Limits apply from stream acquisition, not preceding Docker API calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_bytes: int = Field(gt=0)
    seconds: float = Field(gt=0, allow_inf_nan=False)


class Frame(BaseModel):
    """Docker non-TTY stream frame; bytes remain undecoded."""

    model_config = ConfigDict(frozen=True)
    channel: Literal["stdout", "stderr"]
    data: bytes = Field(repr=False, exclude=True)
