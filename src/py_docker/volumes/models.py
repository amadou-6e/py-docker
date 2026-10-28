"""Named volume receipts with private ownership labels."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class VolumeIdentity(BaseModel):
    """Volumes have no immutable ID; deletion requires external serialization."""

    model_config = ConfigDict(frozen=True)
    name: str = Field(min_length=1)
    labels: dict[str, SecretStr] = Field(min_length=1, repr=False, exclude=True)
