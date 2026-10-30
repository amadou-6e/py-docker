"""Validated interactive lifecycle requests."""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from py_docker.connection.models import RequestBudget
from py_docker.containers.models import ContainerSpec
from py_docker.streams.models import StreamLimits


class ContainerSession(BaseModel):
    """Launch an immutable-image non-TTY container with optional attached stdin."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    spec: ContainerSpec = Field(
        description="Explicit launch policy; stdin may be disabled for output-only services."
    )
    limits: StreamLimits = Field(
        description="Caller-owned lifetime and combined binary output budget."
    )
    receipt_path: Path = Field(
        repr=False,
        exclude=True,
        description="Private per-session durable receipt in an existing caller-owned directory.",
    )

    @model_validator(mode="after")
    def validate_interactive_image(self) -> "ContainerSession":
        """Reject mutable images before opening a lifecycle.

        Returns
        -------
        ContainerSession
            This validated request.

        Raises
        ------
        ValueError
            The image is mutable.
        """
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.spec.image):
            raise ValueError("A container session requires an immutable image ID")
        return self


class SessionDeadline(BaseModel):
    """Group normal admission and one distinct cleanup reserve, never reset."""

    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    normal: RequestBudget = Field(
        description="Canonical normal-phase deadline and witness."
    )
    cleanup_seconds: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Independent cleanup admission reserve in seconds, allocated once.",
    )
    _cleanup_deadline: float | None = PrivateAttr(default=None)

    @classmethod
    def from_options(
        cls, deadline: float | None, cleanup_seconds: float | None
    ) -> "SessionDeadline | None":
        """Validate paired explicit options; both None retain the legacy path."""
        if deadline is None and cleanup_seconds is None:
            return None
        return cls(
            normal=RequestBudget(deadline=deadline), cleanup_seconds=cleanup_seconds
        )

    def cleanup_budget(self, now: float) -> RequestBudget:
        """Allocate once under the lifecycle lock and reuse the absolute limit."""
        if self._cleanup_deadline is None:
            self._cleanup_deadline = now + self.cleanup_seconds
        return RequestBudget(deadline=self._cleanup_deadline)
