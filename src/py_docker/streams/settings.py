"""Own fixed Docker framing and Windows pipe protocol values."""

HEADER_SIZE = 8
HEADER_FORMAT = ">BxxxI"
STDOUT_CHANNEL = 1
STDERR_CHANNEL = 2
WINDOWS_BROKEN_PIPE = 109
