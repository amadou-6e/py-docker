"""Resolved connection identity, independent of mutable process environment."""

import math

from pydantic import BaseModel, ConfigDict, Field

from py_docker.errors import DeadlineError, DockerOperationError


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


class RequestBudget(BaseModel):
    """Keep one private monotonic deadline and conservative create witness."""

    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    deadline: float = Field(
        allow_inf_nan=False,
        exclude=True,
        repr=False,
        description="Absolute monotonic-clock deadline for Engine send admission.",
    )
    create_dispatched: bool = Field(
        default=False,
        exclude=True,
        repr=False,
        description="Whether this lifecycle admitted its container-create POST.",
    )

    def remaining_seconds(self, now: float) -> float:
        """Return remaining seconds or raise DeadlineError before new work."""
        remaining = self.deadline - now
        if remaining <= 0:
            raise DeadlineError("admit Engine request")
        return remaining

    def timeout_seconds(self, supplied: object, configured: float, now: float) -> float:
        """Clamp a scalar SDK timeout; unsupported forms fail before sending."""
        remaining = min(configured, self.remaining_seconds(now))
        if supplied is None:
            return remaining
        if (
            type(supplied) not in (int, float)
            or not math.isfinite(supplied)
            or supplied <= 0
        ):
            raise DockerOperationError("validate scoped request timeout")
        return min(remaining, supplied)
