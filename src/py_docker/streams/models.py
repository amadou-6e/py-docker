"""Stream budgets and demultiplexed binary frames."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from py_docker.errors import DeadlineError, OutputLimitError


class StreamLimits(BaseModel):
    """Limits apply from stream acquisition, not preceding Docker API calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_bytes: int = Field(
        gt=0,
        description="Maximum combined stdout/stderr payload bytes read from the stream.",
    )
    seconds: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Monotonic lifetime in seconds beginning when the stream is acquired.",
    )


class Frame(BaseModel):
    """Docker non-TTY stream frame; bytes remain undecoded."""

    model_config = ConfigDict(frozen=True)
    channel: Literal["stdout", "stderr"] = Field(
        description="Docker output channel identified by the non-TTY frame header."
    )
    data: bytes = Field(
        repr=False,
        exclude=True,
        description="Undecoded frame payload, excluded from representation and serialization.",
    )


class Line(Frame):
    """One channel's complete binary line, or its final unterminated bytes.

    Newline bytes are preserved. Decoding and application message parsing belong
    to the consumer; a line may span any number of Docker frames.
    """


class StreamBudget(BaseModel):
    """Keep private byte consumption and monotonic deadline state together."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    deadline: float = Field(
        exclude=True,
        repr=False,
        description="Private absolute monotonic-clock deadline in seconds.",
    )
    remaining_bytes: int = Field(
        ge=0,
        exclude=True,
        repr=False,
        description="Private remaining stdout/stderr payload allowance in bytes.",
    )

    @classmethod
    def from_limits(cls, limits: StreamLimits, now: float) -> "StreamBudget":
        """Initialize state from a validated request and a clock reading.

        Parameters
        ----------
        limits : StreamLimits
            Requested stream lifetime and combined payload allowance.
        now : float
            Monotonic-clock reading in seconds at stream acquisition.

        Returns
        -------
        StreamBudget
            Mutable state owned exclusively by the acquired stream.
        """
        return cls(deadline=now + limits.seconds, remaining_bytes=limits.max_bytes)

    def remaining_seconds(self, now: float) -> float:
        """Calculate remaining lifetime without extending the deadline.

        Parameters
        ----------
        now : float
            Current monotonic-clock reading in seconds.

        Returns
        -------
        float
            Positive duration until the acquired stream expires.

        Raises
        ------
        DeadlineError
            The lifetime has expired; remote work may still continue.
        """
        remaining = self.deadline - now
        if remaining <= 0:
            raise DeadlineError("read/write container stream")
        return remaining

    def consume(self, size: int) -> None:
        """Reserve a frame's payload allowance before allocating or reading.

        Parameters
        ----------
        size : int
            Unsigned payload length decoded from the Docker frame header.

        Raises
        ------
        ValueError
            A negative byte count is invalid and cannot increase the allowance.
        OutputLimitError
            The frame exceeds the remaining allowance; no payload is read.
        """
        if size < 0:
            raise ValueError("Payload byte count must be unsigned")
        if size > self.remaining_bytes:
            raise OutputLimitError("read container stream")
        self.remaining_bytes -= size
