"""Version checking utilities for external software tools."""

try:
    from versioncheck._version import version as __version__
except ModuleNotFoundError:
    __version__ = "0+unknown"

from versioncheck.models import (
    CheckReport,
    CheckResult,
    SourceName,
    ToolSpec,
    VersionCandidate,
    VersionStatus,
)

__all__ = [
    "CheckReport",
    "CheckResult",
    "SourceName",
    "ToolSpec",
    "VersionCandidate",
    "VersionStatus",
    "__version__",
]
