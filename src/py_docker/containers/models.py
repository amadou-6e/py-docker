"""Typed container policy and exact resource identities."""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from py_docker.containers import settings


class BindMount(BaseModel):
    """Preserve Docker bind options, including SELinux and propagation modes.

    The host path remains the enclosing map key. Unknown string options retain
    the prior dictionary boundary behavior; the Docker SDK interprets them.
    """

    model_config = ConfigDict(extra="allow", frozen=True, hide_input_in_errors=True)
    __pydantic_extra__: dict[str, str] = Field(
        init=False,
        description="Additional string-valued bind options retained at the SDK boundary.",
    )
    bind: str = Field(description="Destination path inside the container.")
    mode: str = Field(
        default="rw",
        description="Docker mount mode, including supported comma-separated suffixes.",
    )
    propagation: str | None = Field(
        default=None,
        description="Optional Linux bind propagation option passed unchanged to the SDK.",
    )

    def to_sdk(self) -> dict[str, str]:
        """Project only supplied bind options, preserving absent SDK defaults.

        Returns
        -------
        dict[str, str]
            Original string-valued options without implicit mode additions.
        """
        return self.model_dump(exclude_unset=True, exclude_none=True)


class ContainerSpec(BaseModel):
    """Explicit Docker options; images are resolved locally before creation."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    image: str = Field(
        min_length=1,
        description="Locally installed image reference resolved to an immutable image ID.",
    )
    name: str = Field(
        min_length=1,
        description="Exact Docker name; an existing named container is never replaced.",
    )
    command: list[str] | None = Field(
        default=None,
        description="Argument vector overriding the image command; None inherits Docker defaults.",
    )
    entrypoint: list[str] | None = Field(
        default=None,
        description="Entrypoint argument vector; None retains the image entrypoint.",
    )
    user: str | None = Field(
        default=None,
        description="Container user or UID/GID; None retains the image user.",
    )
    working_dir: str | None = Field(
        default=None,
        description="Container working directory; None retains the image default.",
    )
    environment: dict[str, SecretStr] = Field(
        default_factory=dict,
        repr=False,
        exclude=True,
        description="Private environment overrides; Docker config proxies are not injected.",
    )
    labels: dict[str, SecretStr] = Field(
        default_factory=dict,
        repr=False,
        exclude=True,
        description="Private labels augmented with the generated library ownership token.",
    )
    volumes: dict[str, BindMount] = Field(
        default_factory=dict,
        description="Host paths mapped to typed container bind-mount records.",
    )
    network_mode: str = Field(
        default=settings.DEFAULT_NETWORK_MODE,
        description="Docker network mode; the default disables container networking.",
    )
    cap_drop: list[str] = Field(
        default_factory=lambda: list(settings.DEFAULT_CAP_DROP),
        description="Linux capabilities removed from the container; defaults to all.",
    )
    cap_add: list[str] = Field(
        default_factory=list,
        description="Explicit Linux capabilities added after capability dropping.",
    )
    security_opt: list[str] = Field(
        default_factory=lambda: list(settings.DEFAULT_SECURITY_OPTIONS),
        description="Docker security options; defaults to no-new-privileges.",
    )
    read_only: bool = Field(
        default=settings.DEFAULT_READ_ONLY,
        description="Whether the container root filesystem is mounted read-only.",
    )
    tmpfs: dict[str, str] = Field(
        default_factory=dict,
        description="Container paths mapped to Docker tmpfs option strings.",
    )
    mem_limit: str | int = Field(
        default=settings.DEFAULT_MEMORY_LIMIT,
        description="Docker memory limit in bytes or a Docker size string such as 1g.",
    )
    pids_limit: int = Field(
        default=settings.DEFAULT_PIDS_LIMIT,
        gt=0,
        description="Maximum number of processes permitted inside the container.",
    )
    stdin_open: bool = Field(
        default=False,
        description="Whether Docker keeps stdin open for interactive attachment.",
    )

    def sdk_volumes(self) -> dict[str, dict[str, str]]:
        """Project canonical bind models for creation and read-back verification.

        Returns
        -------
        dict[str, dict[str, str]]
            Host source paths and their explicitly supplied bind options.
        """
        return {source: mount.to_sdk() for source, mount in self.volumes.items()}


class ContainerIdentity(BaseModel):
    """Immutable ID and expected labels. Names alone never authorize deletion."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    id: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="Full immutable Docker container ID, never a name or prefix.",
    )
    name: str = Field(
        min_length=1,
        description="Expected exact name checked alongside the immutable ID.",
    )
    labels: dict[str, SecretStr] = Field(
        min_length=1,
        repr=False,
        exclude=True,
        description="Private expected ownership labels required before mutation.",
    )


class ContainerReservation(BaseModel):
    """Ownership intent retained before sending create, including unknown outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    name: str = Field(
        min_length=1,
        description="Reserved exact name used to reconcile an uncertain creation.",
    )
    labels: dict[str, SecretStr] = Field(
        min_length=1,
        repr=False,
        exclude=True,
        description="Private expected ownership labels retained before creation.",
    )

    @classmethod
    def from_private_record(
        cls, record: Mapping[str, object]
    ) -> "ContainerReservation":
        """Validate a private ownership record without exposing its input on errors.

        Parameters
        ----------
        record : Mapping[str, object]
            Private file data containing the exact name and plaintext ownership labels.

        Returns
        -------
        ContainerReservation
            Canonical validated ownership intent, with labels protected as secrets.

        Raises
        ------
        ValueError
            The private record does not satisfy the ownership schema.
        """
        return cls.model_validate(record)

    def to_private_record(self) -> dict[str, object]:
        """Expose ownership secrets solely for an explicitly private local file.

        Returns
        -------
        dict[str, object]
            Exact name and plaintext ownership labels. Never log, publish or use
            this conversion as a public serialization; normal dumps omit labels.
        """
        return {
            "name": self.name,
            "labels": {
                key: value.get_secret_value() for key, value in self.labels.items()
            },
        }
