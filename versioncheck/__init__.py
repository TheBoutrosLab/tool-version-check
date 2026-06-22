"""Version checking utilities for external software tools."""

try:
    from versioncheck._version import version as __version__
except ModuleNotFoundError:
    __version__ = "0+unknown"

__all__: list[str] = []
