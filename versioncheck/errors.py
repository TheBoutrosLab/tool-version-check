"""Exception types raised by versioncheck."""


class VersionCheckError(Exception):
    """Base class for versioncheck errors."""


class ConfigError(VersionCheckError):
    """Raised when a versioncheck configuration file is invalid."""


class ProviderError(VersionCheckError):
    """Raised when a version provider cannot return usable data."""


class NetworkError(ProviderError):
    """Raised when a provider request fails because of network behavior."""


class VersionParseError(VersionCheckError):
    """Raised when a version string or pattern cannot be parsed."""
