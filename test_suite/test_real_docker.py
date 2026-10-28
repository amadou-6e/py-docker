"""Opt-in real Docker checks with no credentials, pulling or shared resources."""

import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest

from py_docker import Client
from py_docker.containers.models import ContainerReceipt, ContainerSpec, Mount
from py_docker.errors import (
    CreationUnconfirmedError,
    DeadlineError,
    OutputLimitError,
    OwnershipConflictError,
)
from py_docker.jobs.models import ContainerJob
from py_docker.sessions.models import ContainerSession
from py_docker.streams.models import StreamLimits


@pytest.mark.integration
def test_real_receipt_survives_client_exit_and_external_removal(tmp_path):
    """Recover an observed ID after a real client exit and independent removal."""
    if not os.environ.get("PY_DOCKER_TEST_IMAGE"):
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to an existing Python image")
    receipt = tmp_path.joinpath("crash-session.json")
    child_code = """
import os,sys,uuid
from pathlib import Path
from py_docker import Client
from py_docker.containers.models import ContainerSpec
from py_docker.sessions.models import ContainerSession
from py_docker.streams.models import StreamLimits
client=Client()
client.sessions.open(ContainerSession(
    spec=ContainerSpec(image=client.images.resolve(os.environ['PY_DOCKER_TEST_IMAGE']),
        name='py-docker-crash-'+uuid.uuid4().hex,stdin_open=True,
        command=['python3','-c','import time;time.sleep(60)']),
    limits=StreamLimits(seconds=30,max_bytes=1024),receipt_path=Path(sys.argv[1])))
os._exit(0)
"""
    child = subprocess.run(
        [sys.executable, "-c", child_code, str(receipt)],
        capture_output=True,
        timeout=40,
        check=False,
    )
    assert child.returncode == 0
    observed = ContainerReceipt.from_private_record(json.loads(receipt.read_text()))
    assert observed.identity is not None
    with Client() as client:
        try:
            client.containers.remove(observed.identity, force=True)
            assert client.containers.inspect(observed.identity) is None
            client.sessions.recover(receipt)
            assert not receipt.exists()
        finally:
            client.containers.remove(observed.identity, force=True)


@pytest.mark.integration
def test_real_interactive_stdin_binary_channels_and_blocked_reader_cleanup(tmp_path):
    """Exercise real stdin and cross-thread removal while a binary read blocks."""
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to an existing Python image")
    with Client() as client:
        request = ContainerSession(
            spec=ContainerSpec(
                image=client.images.resolve(image),
                name="py-docker-session-" + uuid.uuid4().hex,
                stdin_open=True,
                command=[
                    "python3",
                    "-u",
                    "-c",
                    "import sys;sys.stdout.buffer.write(b'ready\\n');data=sys.stdin.buffer.readline();sys.stdout.buffer.write(data);sys.stderr.buffer.write(b'err\\n');sys.stdin.buffer.read(1)",
                ],
            ),
            limits=StreamLimits(seconds=20, max_bytes=65536),
            receipt_path=tmp_path.joinpath("session.json"),
        )
        session = client.sessions.open(request)
        worker = None
        try:
            frame = session.read_frame()
            assert frame.channel == "stdout" and frame.data == b"ready\n"
            session.write(b"\x00\xff\n")
            output = {"stdout": bytearray(), "stderr": bytearray()}
            while not (output["stdout"] and output["stderr"]):
                frame = session.read_frame()
                assert frame is not None
                output[frame.channel].extend(frame.data)
            assert bytes(output["stdout"]) == b"\x00\xff\n"
            assert bytes(output["stderr"]) == b"err\n"
            reader_started = threading.Event()
            terminal = []

            def blocked_read():
                """Record safe EOF/error categories without retaining raw output."""
                reader_started.set()
                try:
                    terminal.append(session.read_frame())
                except Exception as error:
                    terminal.append(type(error).__name__)

            worker = threading.Thread(target=blocked_read, daemon=True)
            worker.start()
            assert reader_started.wait(timeout=2)
            terminator = threading.Thread(target=session.terminate)
            terminator.start()
            terminator.join(timeout=10)
            assert not terminator.is_alive()
            worker.join(timeout=5)
            assert not worker.is_alive()
            assert request.receipt_path.exists()
            assert session.state().removed
        finally:
            session.close()
            if worker is not None:
                worker.join(timeout=5)
        assert not request.receipt_path.exists()
        assert session.state().removed


@pytest.mark.integration
def test_real_explicit_mount_refuses_missing_bind_source(tmp_path):
    """The SDK must preserve --mount refusal rather than creating a host path."""
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to an existing Python image")
    missing = tmp_path.joinpath("missing")
    with Client() as client:
        spec = ContainerSpec(
            image=client.images.resolve(image),
            name="py-docker-session-" + uuid.uuid4().hex,
            stdin_open=True,
            command=["python3", "-c", "pass"],
            mounts=[Mount(type="bind", source=str(missing), target="/missing")],
        )
        request = ContainerSession(
            spec=spec,
            limits=StreamLimits(seconds=5, max_bytes=1024),
            receipt_path=tmp_path.joinpath("receipt.json"),
        )
        from py_docker.errors import DockerOperationError

        with pytest.raises(
            DockerOperationError, match="verify local bind mount source exists"
        ):
            client.sessions.open(request)
        assert not missing.exists()
        assert not request.receipt_path.exists()


@pytest.mark.integration
def test_real_one_shot_job_preserves_binary_result_and_cleans_owned_id(tmp_path):
    """Use a real local image for a one-shot job with no mounts or credentials."""
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to a local image containing python3")
    with Client() as client:
        image_id = client.images.resolve(image)
        name = "py-docker-job-" + uuid.uuid4().hex
        job = ContainerJob(
            spec=ContainerSpec(
                image=image_id,
                name=name,
                command=[
                    "python3",
                    "-c",
                    "import sys;sys.stdout.buffer.write(bytes([0,255,10]));sys.stderr.buffer.write(b'separate');sys.exit(7)",
                ],
            ),
            limits=StreamLimits(seconds=10, max_bytes=65536),
            receipt_path=tmp_path.joinpath("job-receipt.json"),
            wait_timeout_seconds=10,
        )
        result = client.jobs.run(job)
        assert (result.exit_code, result.stdout, result.stderr) == (
            7,
            bytes([0, 255, 10]),
            b"separate",
        )
        assert not job.receipt_path.exists()
        assert not any(
            container.name == name
            for container in client.sdk.containers.list(
                all=True, filters={"name": name}
            )
        )


@pytest.mark.integration
def test_real_binary_exec_and_exact_cleanup():
    """Exercise real binary output, deadlines and exact owned-container cleanup."""
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
    """Exercise real entrypoint and mount behavior plus an internal recovery fault."""
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
                    """Inject an internal verification failure without simulating a Docker provider."""
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
