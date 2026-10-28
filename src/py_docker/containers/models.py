"""Typed container policy and exact resource identities."""

from collections.abc import Mapping
from pathlib import PureWindowsPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from py_docker.containers import settings


class CleanupResult(BaseModel):
    """Safe outcome of reservation cleanup, including late-create uncertainty."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    verified: bool = Field(description="Whether exact cleanup was confirmed.")
    detail: str = Field(
        description="Safe stable cleanup category, never daemon output."
    )


class Mount(BaseModel):
    """Explicit mounts preserve Docker --mount missing-source semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    source: str = Field(
        min_length=1, description="Existing host bind source or named Docker volume."
    )
    target: str = Field(
        min_length=1, description="Absolute destination inside the container."
    )
    type: Literal["bind", "volume"] = Field(
        description="Docker mount category; bind sources are never created implicitly."
    )
    read_only: bool = Field(
        default=False,
        description="Whether the mounted data is read-only in the container.",
    )

    def to_sdk(self) -> dict[str, object]:
        """Return the exact explicit mount request accepted by the Docker SDK.

        Returns
        -------
        dict[str, object]
            Docker Mounts entry, with no host-directory creation option.
        """
        return {
            "Source": self.source,
            "Target": self.target,
            "Type": self.type,
            "ReadOnly": self.read_only,
        }

    def matches_readback(
        self, record: Mapping[str, object], *, local_npipe: bool
    ) -> bool:
        """Compare exact mount policy with narrowly recognized daemon normalization.

        Parameters
        ----------
        record : Mapping[str, object]
            HostConfig.Mounts entry returned for the exact owned container.
        local_npipe : bool
            Whether this client uses the local Windows named-pipe adapter.

        Returns
        -------
        bool
            True only for exact fields, omitted false ReadOnly, and the known
            Docker Desktop Linux-host translation of this same Windows source.
        """
        actual = dict(record)
        actual.setdefault("ReadOnly", False)
        if local_npipe and self.type == "bind":
            path = PureWindowsPath(self.source)
            if path.is_absolute() and len(path.drive) == 2 and path.drive[1] == ":":
                translated = settings.DESKTOP_BIND_ROOT + "/" + path.drive[0].lower()
                translated += "/" + "/".join(path.parts[1:])
                if actual.get("Source") == translated:
                    actual["Source"] = self.source
        return actual == self.to_sdk()


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
    mounts: list[Mount] = Field(
        default_factory=list,
        description="Explicit bind/named-volume mounts retaining --mount source validation.",
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
    init: bool = Field(
        default=False,
        description="Whether Docker supplies an init process to reap children.",
    )
    nano_cpus: int = Field(
        default=0,
        ge=0,
        strict=True,
        description="CPU quota in billionths of a CPU; zero retains Docker's unlimited default.",
    )
    extra_hosts: dict[str, str] = Field(
        default_factory=dict,
        description="Explicit container host aliases, including Docker host-gateway.",
    )
    ports: dict[str, Annotated[int, Field(strict=True, ge=1, le=65535)] | None] = Field(
        default_factory=dict,
        description="Container ports such as 4096/tcp published only on IPv4 loopback; None requests an ephemeral host port.",
    )

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, value: dict[str, int | None]) -> dict[str, int | None]:
        """Reject ambiguous port keys before any resource is created."""
        for key in value:
            port, separator, protocol = key.partition("/")
            if (
                not separator
                or protocol not in {"tcp", "udp"}
                or not port.isascii()
                or not port.isdecimal()
                or not 1 <= int(port) <= 65535
            ):
                raise ValueError(
                    "Published ports require an explicit port/protocol key"
                )
        return value

    def sdk_ports(self) -> dict[str, tuple[str, int | None]]:
        """Return Docker bindings restricted to the local IPv4 loopback interface."""
        return {port: ("127.0.0.1", host) for port, host in self.ports.items()}

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


class ContainerObservation(BaseModel):
    """Canonical endpoint-scoped observation without exposing ownership labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    state: Literal["absent", "owned", "conflict", "unknown"] = Field(
        description="Confirmed ownership observation or conservative failure category."
    )
    identity: ContainerIdentity | None = Field(
        default=None,
        repr=False,
        exclude=True,
        description="Verified private immutable identity, present only for owned observations.",
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


class ContainerReceipt(BaseModel):
    """Private durable intent optionally bound to an observed immutable ID."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    reservation: ContainerReservation = Field(
        repr=False,
        exclude=True,
        description="Canonical private ownership intent saved before dispatch.",
    )
    observed_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Immutable ID returned and ownership-verified by a completed create.",
    )
    endpoint: str | None = Field(
        default=None,
        min_length=1,
        repr=False,
        exclude=True,
        description="Original resolved daemon endpoint; legacy records without it cannot be recovered automatically.",
    )

    @property
    def identity(self) -> ContainerIdentity | None:
        """Return the observed identity, or None while create remains uncertain."""
        if self.observed_id is None:
            return None
        return ContainerIdentity(
            id=self.observed_id,
            name=self.reservation.name,
            labels=self.reservation.labels,
        )

    @classmethod
    def from_private_record(cls, record: Mapping[str, object]) -> "ContainerReceipt":
        """Read current records and legacy intent-only records.

        Parameters
        ----------
        record : Mapping[str, object]
            Private local record; never log this input.

        Returns
        -------
        ContainerReceipt
            Validated ownership intent and optional observed ID.
        """
        value = dict(record)
        observed = value.pop("observed_id", None)
        endpoint = value.pop("endpoint", None)
        return cls(
            reservation=ContainerReservation.from_private_record(value),
            observed_id=observed,
            endpoint=endpoint,
        )

    def to_private_record(self) -> dict[str, object]:
        """Project secrets only into the caller-owned private receipt file.

        Returns
        -------
        dict[str, object]
            Backward-compatible name/labels plus an observed ID when known.
        """
        value = self.reservation.to_private_record()
        if self.observed_id is not None:
            value["observed_id"] = self.observed_id
        if self.endpoint is not None:
            value["endpoint"] = self.endpoint
        return value


class ContainerState(BaseModel):
    """Confirmed lifecycle state without confusing removal with successful exit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    running: bool = Field(
        description="Whether the owned container is confirmed running."
    )
    exit_code: int | None = Field(
        default=None,
        description="Confirmed integer exit code, never inferred from absence.",
    )
    removed: bool = Field(
        description="Whether the immutable observed ID is confirmed absent."
    )
