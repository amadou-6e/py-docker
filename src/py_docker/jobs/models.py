"""Explicit one-shot job policy, stream bounds and private receipt location."""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from py_docker.containers.models import ContainerSpec
from py_docker.streams.models import StreamLimits


class ContainerJob(BaseModel):
    """Create one noninteractive container from an already verified immutable image."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    spec: ContainerSpec = Field(
        description="Explicit noninteractive launch policy using an immutable sha256 image ID."
    )
    limits: StreamLimits = Field(
        description="Combined stdout/stderr byte allowance and acquired-stream lifetime."
    )
    receipt_path: Path = Field(
        exclude=True,
        repr=False,
        description="Caller-owned private local receipt path used for recovery and exclusive execution.",
    )
    wait_timeout_seconds: float = Field(
        gt=0,
        allow_inf_nan=False,
        strict=True,
        description="Positive finite exit-status request timeout in seconds, separate from stream lifetime.",
    )

    @field_validator("spec")
    @classmethod
    def _supported_spec(cls, value: ContainerSpec) -> ContainerSpec:
        """Reject tags and interactive modes before any Docker or filesystem action.

        Parameters
        ----------
        value : ContainerSpec
            Validated canonical container launch request.

        Returns
        -------
        ContainerSpec
            The same immutable-image, noninteractive policy.

        Raises
        ------
        ValueError
            The image is mutable or the request requires unsupported stdin/TTY behavior.
        """
        if value.stdin_open or getattr(value, "tty", False):
            raise ValueError("One-shot jobs do not support interactive stdin or TTY")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value.image):
            raise ValueError("One-shot jobs require an immutable sha256 image ID")
        return value
