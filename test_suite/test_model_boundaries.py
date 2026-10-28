"""Check typed projections against the existing SDK and environment contracts."""

from unittest.mock import patch

import pytest
from docker.utils import convert_volume_binds

from py_docker import Client
from py_docker.containers.models import BindMount, ContainerSpec
from py_docker.streams.models import StreamBudget, StreamLimits


def test_bind_mount_projection_preserves_windows_paths_and_docker_modes():
    """Retain Windows source keys, SELinux suffixes and propagation at the SDK edge."""
    original = {
        "C:\\work\\repo": {"bind": "/input", "mode": "ro,z", "propagation": "rshared"}
    }
    spec = ContainerSpec(image="local", name="example", volumes=original)
    assert isinstance(spec.volumes["C:\\work\\repo"], BindMount)
    assert spec.sdk_volumes() == original
    assert convert_volume_binds(spec.sdk_volumes()) == convert_volume_binds(original)


def test_unspecified_bind_mode_keeps_sdk_default_and_extra_string_options():
    """Do not silently add mode or remove previously accepted SDK-boundary options."""
    original = {"/source": {"bind": "/input", "unused-option": "kept"}}
    spec = ContainerSpec(image="local", name="example", volumes=original)
    assert spec.sdk_volumes() == original
    assert convert_volume_binds(spec.sdk_volumes()) == convert_volume_binds(original)


def test_client_ignores_ambient_library_settings_when_snapshot_supplied(monkeypatch):
    """An explicit empty snapshot must not inherit host endpoint or remote permission."""
    monkeypatch.setenv("PY_DOCKER_ENDPOINT", "tcp://unrelated:2375")
    monkeypatch.setenv("PY_DOCKER_ALLOW_REMOTE", "true")
    with patch("py_docker.client.DirectDockerClient") as sdk:
        with Client(environment={}):
            assert sdk.call_args.kwargs["base_url"].startswith(
                ("unix:///", "npipe:////./pipe/")
            )


def test_stream_budget_cannot_gain_bytes_from_invalid_consumption():
    """Reject invalid state transitions without increasing the private allowance."""
    budget = StreamBudget.from_limits(StreamLimits(max_bytes=5, seconds=1), now=100)
    with pytest.raises(ValueError):
        budget.consume(-1)
    assert budget.remaining_bytes == 5
    assert budget.model_dump() == {}
