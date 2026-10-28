"""Validated interactive lifecycle requests."""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
