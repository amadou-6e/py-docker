"""Own fixed launch defaults; process environment cannot relax this policy."""

DEFAULT_NETWORK_MODE = "none"
DEFAULT_CAP_DROP = ("ALL",)
DEFAULT_SECURITY_OPTIONS = ("no-new-privileges:true",)
DEFAULT_READ_ONLY = True
DEFAULT_MEMORY_LIMIT = "1g"
DEFAULT_PIDS_LIMIT = 128

# Docker's create contract: bad parameter, missing image or name conflict.
# Timeouts, throttling, server errors and undocumented responses stay uncertain.
DEFINITIVE_CREATE_REJECTIONS = frozenset({400, 404, 409})
