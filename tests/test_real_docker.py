"""Opt-in real Docker checks with no credentials, pulling or shared resources."""

import os
import uuid

import pytest

from py_docker import Client
from py_docker.containers.models import ContainerSpec
from py_docker.streams.models import StreamLimits


@pytest.mark.integration
def test_real_binary_exec_and_exact_cleanup():
    image = os.environ.get("PY_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("Set PY_DOCKER_TEST_IMAGE to a local image containing python3")
    with Client() as client:
        identity = client.containers.create(ContainerSpec(image=image, name="py-docker-test-" + uuid.uuid4().hex, command=["python3", "-c", "import time;time.sleep(60)"]))
        try:
            client.containers.start(identity)
            result = client.execution.run(identity, ["python3", "-c", "import sys;sys.stdout.buffer.write(bytes([0,255,10]));sys.stderr.write('stderr')"], StreamLimits(max_bytes=1024, seconds=10))
            assert result.exit_code == 0
            assert result.stdout == bytes([0, 255, 10])
            assert result.stderr == b"stderr"
        finally:
            client.containers.remove(identity, force=True)
        assert client.containers.inspect(identity) is None
