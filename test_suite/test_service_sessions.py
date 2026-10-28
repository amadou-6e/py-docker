"""Internal service-policy controls; real Docker checks are recorded separately."""

from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from py_docker.containers.models import ContainerIdentity, ContainerSpec
from py_docker.containers.service import Containers
from py_docker.errors import DockerOperationError
from py_docker.volumes.service import Volumes


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1", ""])
def test_public_binding_is_never_accepted(host):
    """A correct owned ID does not excuse an externally exposed endpoint."""
    sdk = Mock()
    identity = ContainerIdentity(id="a" * 64, name="owned", labels={"owner": "secret"})
    sdk.containers.get.return_value.attrs = {
        "Id": identity.id,
        "Name": "/owned",
        "Config": {"Labels": {"owner": "secret"}},
        "NetworkSettings": {
            "Ports": {"4096/tcp": [{"HostIp": host, "HostPort": "4321"}]}
        },
    }
    with pytest.raises(DockerOperationError):
        Containers(sdk).published_port(identity, "4096/tcp")


def test_loopback_binding_and_typed_policy():
    """Explicit ephemeral ports cannot broaden the interface or accept bool ports."""
    spec = ContainerSpec(image="local", name="service", ports={"4096/tcp": None})
    assert spec.sdk_ports() == {"4096/tcp": ("127.0.0.1", None)}
    for ports in ({"4096": None}, {"4096/tcp": True}, {"0/tcp": None}):
        with pytest.raises(ValidationError):
            ContainerSpec(image="local", name="service", ports=ports)


def test_legacy_volume_label_check_grants_no_mutation():
    """Application labels permit read-only profile selection, never deletion."""
    sdk = Mock()
    sdk.volumes.get.return_value.attrs = {"Labels": {"provider": "selected"}}
    volumes = Volumes(sdk)
    assert volumes.has_labels("profile", {"provider": "selected"})
    assert not volumes.has_labels("profile", {"provider": "other"})
    with pytest.raises(DockerOperationError):
        volumes.has_labels("profile", {})
    sdk.volumes.remove.assert_not_called()
