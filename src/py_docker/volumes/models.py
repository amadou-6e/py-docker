"""Named volume receipts with private ownership labels."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class VolumeIdentity(BaseModel):
    """Volumes have no immutable ID; deletion requires external serialization."""

    model_config = ConfigDict(frozen=True)
    name: str = Field(
        min_length=1,
        description="Exact Docker volume name; deletion requires external lifecycle serialization.",
    )
    labels: dict[str, SecretStr] = Field(
        min_length=1,
        repr=False,
        exclude=True,
        description="Private ownership labels checked before returning a named volume.",
    )
