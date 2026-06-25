"""Version source provider interfaces and implementations."""

from versioncheck.providers.base import VersionProvider
from versioncheck.providers.github import GitHubProvider

__all__ = ["GitHubProvider", "VersionProvider"]
