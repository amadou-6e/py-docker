"""Internal regression controls; these do not establish live Docker acceptance."""

import ast
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from docker.errors import DockerException, NotFound
from pydantic import ValidationError

from py_docker.connection.resolver import ConnectionResolver
from py_docker.connection.settings import ConnectionSettings
from py_docker.containers.models import ContainerIdentity, ContainerSpec
from py_docker.containers.service import Containers
from py_docker.errors import (
    ConnectionConfigurationError,
    DockerOperationError,
    OwnershipConflictError,
)


def test_named_volume_does_not_adopt_a_racing_existing_name():
    """Docker's idempotent volume create cannot transfer someone else's ownership."""
    from py_docker.errors import CreationUnconfirmedError
    from py_docker.volumes.service import Volumes

    sdk = Mock()
    sdk.volumes.create.return_value.attrs = {"Labels": {"owner": "someone-else"}}
    with pytest.raises(CreationUnconfirmedError) as error:
        Volumes(sdk).create(name="explicit-profile")
    assert error.value.receipt.name == "explicit-profile"
    sdk.volumes.remove.assert_not_called()


def test_selected_volume_lookup_distinguishes_absence_from_uncertainty():
    """Only an actual NotFound is absence; daemon errors remain safe failures."""
    from py_docker.volumes.service import Volumes

    sdk = Mock()
    sdk.volumes.get.side_effect = [NotFound("private"), DockerException("private")]
    volumes = Volumes(sdk)
    assert not volumes.exists("selected")
    with pytest.raises(DockerOperationError) as error:
        volumes.exists("selected")
    assert "private" not in str(error.value)


def test_explicit_context_precedes_environment_host():
    """Keep explicit context selection independent of an ambient Docker host."""
    with patch.object(
        ConnectionResolver, "_context_endpoint", return_value="unix:///context.sock"
    ) as lookup:
        result = ConnectionResolver().resolve(
            ConnectionSettings(context="chosen"), {"DOCKER_HOST": "tcp://wrong:2375"}
        )
    assert result.endpoint == "unix:///context.sock"
    assert lookup.call_args.args[0] == "chosen"


def test_ambiguous_host_and_context_environment_is_rejected():
    """Fail closed rather than guess when both Docker selectors are supplied."""
    with pytest.raises(ConnectionConfigurationError):
        ConnectionResolver().resolve(
            ConnectionSettings(),
            {"DOCKER_HOST": "tcp://wrong:2375", "DOCKER_CONTEXT": "chosen"},
        )


def test_explicit_endpoint_precedes_environment():
    """Honor the caller-selected endpoint over environment context defaults."""
    result = ConnectionResolver().resolve(
        ConnectionSettings(endpoint="unix:///chosen.sock"), {"DOCKER_CONTEXT": "other"}
    )
    assert result.endpoint == "unix:///chosen.sock"


@pytest.mark.parametrize(
    "endpoint", ["tcp://localhost:2375", "ssh://host", "http://host"]
)
def test_remote_is_not_implicitly_allowed(endpoint):
    """Reject remote transports unless the caller explicitly grants permission."""
    with pytest.raises(ConnectionConfigurationError):
        ConnectionResolver().resolve(ConnectionSettings(endpoint=endpoint), {})


def test_tls_is_not_silently_ignored():
    """Reject unsupported TLS policy instead of silently using plain transport."""
    with pytest.raises(ConnectionConfigurationError):
        ConnectionResolver().resolve(
            ConnectionSettings(endpoint="unix:///docker.sock"),
            {"DOCKER_TLS_VERIFY": "1"},
        )


def test_credentials_are_excluded_from_model_serialization():
    """Keep request secrets out of model dumps, repr and validation messages."""
    spec = ContainerSpec(
        image="image",
        name="job",
        environment={"TOKEN": "sentinel-secret"},
        labels={"owner": "secret-label"},
    )
    assert "sentinel-secret" not in spec.model_dump_json()
    assert "secret-label" not in repr(spec)
    with pytest.raises(ValidationError) as raised:
        ContainerSpec(environment={"TOKEN": "sentinel-secret"})
    assert "sentinel-secret" not in str(raised.value)


def test_unrecognized_launch_options_are_rejected():
    """Reject unsupported security flags at the strict request boundary."""
    with pytest.raises(ValidationError):
        ContainerSpec(image="image", name="job", privileged=True)


def test_ownership_conflict_never_removes():
    """Never issue removal when the inspected ownership labels differ."""
    sdk = Mock()
    sdk.containers.get.return_value.attrs = {
        "Id": "a" * 64,
        "Name": "/job",
        "Config": {"Labels": {"owner": "someone-else"}},
    }
    identity = ContainerIdentity(id="a" * 64, name="job", labels={"owner": "expected"})
    with pytest.raises(OwnershipConflictError):
        Containers(sdk).remove(identity, force=True)
    sdk.containers.get.return_value.remove.assert_not_called()


def test_daemon_failure_is_not_absence_and_is_redacted():
    """Keep daemon failures distinct from absence without leaking response text."""
    sdk = Mock()
    sdk.containers.get.side_effect = DockerException("private-response-token")
    identity = ContainerIdentity(id="a" * 64, name="job", labels={"owner": "expected"})
    with pytest.raises(DockerOperationError) as raised:
        Containers(sdk).remove(identity)
    assert "private-response-token" not in str(raised.value)


def test_only_not_found_means_absent():
    """Treat only a typed Docker NotFound response as proven absence."""
    sdk = Mock()
    sdk.containers.get.side_effect = NotFound("missing")
    identity = ContainerIdentity(id="a" * 64, name="job", labels={"owner": "expected"})
    assert Containers(sdk).inspect(identity) is None


def test_class_function_cohesion():
    """Prevent implementation modules mixing classes and standalone functions."""
    for path in Path(Path(__file__).parents[1], "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = any(isinstance(node, ast.ClassDef) for node in tree.body)
        functions = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in tree.body
        )
        assert not (classes and functions), str(path)


def test_remote_opt_in_cannot_come_from_ambient_environment(monkeypatch):
    """Prevent environment variables from granting remote Docker permission."""
    monkeypatch.setenv("PY_DOCKER_ALLOW_REMOTE", "true")
    monkeypatch.setenv("PY_DOCKER_ENDPOINT", "tcp://remote:2375")
    settings = ConnectionSettings.from_environment({})
    assert settings.endpoint is None
    with pytest.raises(ConnectionConfigurationError):
        ConnectionResolver().resolve(
            ConnectionSettings(endpoint="tcp://remote:2375"), {}
        )


def test_create_disables_implicit_proxy_injection_and_retains_receipt_on_timeout():
    """Retain recovery ownership and disable proxy injection across unknown creates."""
    from requests.exceptions import ReadTimeout

    from py_docker.errors import CreationUnconfirmedError

    sdk = Mock()
    sdk.images.get.return_value.id = "sha256:" + "a" * 64
    sdk.containers.create.side_effect = ReadTimeout("private-external-error")
    service = Containers(sdk)
    spec = ContainerSpec(image="local", name="owned")
    reservation = service.reserve(spec)
    with pytest.raises(CreationUnconfirmedError) as raised:
        service.create(spec, reservation)
    assert raised.value.receipt is reservation
    assert sdk.containers.create.call_args.kwargs["use_config_proxy"] is False
    assert "private-external-error" not in str(raised.value)
