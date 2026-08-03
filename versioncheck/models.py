"""Core data models for version checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

SourceName = Literal["github", "conda"]
VersionStatus = Literal["unknown", "current", "outdated", "newer_than_source"]
Metadata = dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A software tool whose latest available version should be checked."""

    name: str
    source: SourceName
    package: str
    current_version: str | None = None
    include_prereleases: bool = False
    version_pattern: str | None = None
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VersionCandidate:
    """A version discovered from an upstream source."""

    version: str
    normalized_version: str
    source: SourceName
    url: str | None = None
    released_at: datetime | None = None
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The outcome of checking one tool against one version source."""

    name: str
    source: SourceName
    package: str
    current_version: str | None
    latest_version: str | None
    status: VersionStatus
    candidates: list[VersionCandidate] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True, slots=True)
class CheckReport:
    """A collection of version check results."""

    results: list[CheckResult] = field(default_factory=list)

    @property
    def has_outdated(self) -> bool:
        """Return whether any checked tool is older than the source version."""

        return any(result.status == "outdated" for result in self.results)

    @property
    def outdated_results(self) -> list[CheckResult]:
        """Return results for tools with newer source versions available."""

        return [result for result in self.results if result.status == "outdated"]
