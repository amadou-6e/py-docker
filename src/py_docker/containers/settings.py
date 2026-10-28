"""Own fixed launch defaults; process environment cannot relax this policy."""

DEFAULT_NETWORK_MODE = "none"
DEFAULT_CAP_DROP = ("ALL",)
DEFAULT_SECURITY_OPTIONS = ("no-new-privileges:true",)
DEFAULT_READ_ONLY = True
DEFAULT_MEMORY_LIMIT = "1g"
DEFAULT_PIDS_LIMIT = 128
