"""Protocol controls using local socket pairs, not Docker acceptance evidence."""

import socket
import struct
import time

import pytest

from py_docker.errors import DeadlineError, DockerOperationError, OutputLimitError
from py_docker.streams.models import StreamLimits
from py_docker.streams.socket import AttachedStream


def test_binary_demux_and_clean_eof():
    """Preserve arbitrary bytes and separate stderr through clean frame EOF."""
    reader, writer = socket.socketpair()
    with (
        writer,
        AttachedStream(reader, StreamLimits(max_bytes=10, seconds=1)) as stream,
    ):
        writer.sendall(struct.pack(">BxxxI", 2, 3) + b"\0\xff\n")
        frame = stream.read_frame()
        assert frame.channel == "stderr"
        assert frame.data == b"\0\xff\n"
        writer.shutdown(socket.SHUT_WR)
        assert stream.read_frame() is None


def test_size_rejected_before_payload_read():
    """Reject oversized frame headers before reading or allocating their payload."""
    reader, writer = socket.socketpair()
    with writer, AttachedStream(reader, StreamLimits(max_bytes=2, seconds=1)) as stream:
        writer.sendall(struct.pack(">BxxxI", 1, 99999999))
        with pytest.raises(OutputLimitError):
            stream.read_frame()


def test_stalled_read_has_deadline():
    """Bound a stalled socket read by the original monotonic stream lifetime."""
    reader, writer = socket.socketpair()
    with (
        writer,
        AttachedStream(reader, StreamLimits(max_bytes=20, seconds=0.1)) as stream,
    ):
        started = time.monotonic()
        with pytest.raises(DeadlineError):
            stream.read_frame()
        assert time.monotonic() - started < 2


def test_truncated_frame_is_not_eof():
    """Reject a truncated payload instead of reporting successful stream completion."""
    reader, writer = socket.socketpair()
    with (
        writer,
        AttachedStream(reader, StreamLimits(max_bytes=20, seconds=1)) as stream,
    ):
        writer.sendall(struct.pack(">BxxxI", 1, 5) + b"xx")
        writer.shutdown(socket.SHUT_WR)
        with pytest.raises(DockerOperationError):
            stream.read_frame()


def test_close_failure_does_not_hide_primary_error():
    """Preserve the primary failure when transport cleanup also fails."""
    from unittest.mock import Mock

    raw = Mock()
    raw.close.side_effect = OSError("unsafe-close-detail")
    with pytest.raises(OutputLimitError):
        with AttachedStream(raw, StreamLimits(max_bytes=20, seconds=1)):
            raise OutputLimitError("read stream")
