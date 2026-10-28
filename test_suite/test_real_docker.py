"""Opt-in real Docker checks with no credentials, pulling or shared resources."""

import os
import uuid
from pathlib import Path

import pytest

from py_docker import Client
from py_docker.containers.models import ContainerSpec
from py_docker.errors import (
    CreationUnconfirmedError,
    DeadlineError,
    OutputLimitError,
    OwnershipConflictError,
)
from py_docker.streams.models import StreamLimits


@pytest.mark.integration
def test_real_binary_exec_and_exact_cleanup():
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to a local image containing python3")
    with Client() as client:
        identity = client.containers.create(
            ContainerSpec(
                image=image,
                name="py-docker-test-" + uuid.uuid4().hex,
                command=["python3", "-c", "import time;time.sleep(60)"],
            )
        )
        try:
            client.containers.start(identity)
            result = client.execution.run(
                identity,
                [
                    "python3",
                    "-c",
                    "import sys;sys.stdout.buffer.write(bytes([0,255,10]));sys.stderr.write('stderr')",
                ],
                StreamLimits(max_bytes=1024, seconds=10),
            )
            assert result.exit_code == 0
            assert result.stdout == bytes([0, 255, 10])
            assert result.stderr == b"stderr"
            with pytest.raises(DeadlineError):
                client.execution.run(
                    identity,
                    ["python3", "-c", "import time;time.sleep(5)"],
                    StreamLimits(max_bytes=1024, seconds=0.2),
                )
            with pytest.raises(OutputLimitError):
                client.execution.run(
                    identity,
                    ["python3", "-c", "print('x'*4096)"],
                    StreamLimits(max_bytes=8, seconds=2),
                )
        finally:
            client.containers.remove(identity, force=True)
        assert client.containers.inspect(identity) is None


@pytest.mark.integration
def test_real_custom_entrypoint_bind_and_receipt_recovery(monkeypatch, tmp_path):
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to a local image containing python3")
    Path(tmp_path, "message.txt").write_text("real-bind-ok", encoding="utf-8")
    with Client() as client:
        spec = ContainerSpec(
            image=image,
            name="py-docker-test-" + uuid.uuid4().hex,
            entrypoint=["python3", "-c", "print('custom-entrypoint-ok')"],
            volumes={str(tmp_path): {"bind": "/input", "mode": "ro"}},
        )
        reservation = client.containers.reserve(spec)
        identity = None
        try:
            identity = client.containers.create(spec, reservation)
            client.containers.start(identity)
            container = client.containers.inspect(identity)
            assert container.wait(timeout=10)["StatusCode"] == 0
            assert b"custom-entrypoint-ok" in container.logs()
        finally:
            identity = identity or client.containers.reconcile(reservation)
            if identity is not None:
                client.containers.remove(identity, force=True)
        reservation = client.containers.reserve(spec)
        try:
            with monkeypatch.context() as scoped:
                # Internal fault injection at readback; the Docker resource is real.
                # This verifies recovery only, not a live daemon misconfiguration.
                def reject_readback(*_):
                    raise OwnershipConflictError("injected verification failure")

                scoped.setattr(client.containers, "_verify_launch", reject_readback)
                with pytest.raises(CreationUnconfirmedError) as raised:
                    client.containers.create(spec, reservation)
            assert raised.value.receipt is reservation
            assert client.containers.reconcile(reservation) is not None
        finally:
            recovered = client.containers.reconcile(reservation)
            if recovered is not None:
                client.containers.remove(recovered, force=True)
        assert client.containers.reconcile(reservation) is None
