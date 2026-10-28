"""Typed container policy and exact resource identities."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ContainerSpec(BaseModel):
    """Explicit Docker options; images are resolved locally before creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    image: str = Field(min_length=1)
    name: str = Field(min_length=1)
    command: list[str] | None = None
    entrypoint: list[str] | None = None
    user: str | None = None
    working_dir: str | None = None
    environment: dict[str, SecretStr] = Field(default_factory=dict, repr=False, exclude=True)
    labels: dict[str, SecretStr] = Field(default_factory=dict, repr=False, exclude=True)
    volumes: dict[str, dict[str, str]] = Field(default_factory=dict)
    network_mode: str = "none"
    cap_drop: list[str] = Field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = Field(default_factory=list)
    security_opt: list[str] = Field(default_factory=lambda: ["no-new-privileges:true"])
    read_only: bool = True
    tmpfs: dict[str, str] = Field(default_factory=dict)
    mem_limit: str | int = "1g"
    pids_limit: int = Field(default=128, gt=0)
    stdin_open: bool = False


class ContainerIdentity(BaseModel):
    """Immutable ID and expected labels. Names alone never authorize deletion."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str = Field(min_length=1)
    labels: dict[str, SecretStr] = Field(min_length=1, repr=False, exclude=True)


class ContainerReservation(BaseModel):
    """Ownership intent retained before sending create, including unknown outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    labels: dict[str, SecretStr] = Field(min_length=1, repr=False, exclude=True)
