"""Shared provider contract and result-building logic."""

from __future__ import annotations

from abc import ABC, abstractmethod

from versioncheck.errors import VersionCheckError
from versioncheck.models import CheckResult, SourceName, ToolSpec, VersionCandidate
from versioncheck.versioning import calculate_status, select_latest_candidate


class VersionProvider(ABC):
    """Base class for sources that can list available tool versions."""

    source_name: SourceName

    @abstractmethod
    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        """Return available version candidates for a tool."""

    def check(self, spec: ToolSpec) -> CheckResult:
        """Fetch candidates, select the latest version, and compare status."""

        try:
            candidates = self.list_versions(spec)
        except VersionCheckError as exc:
            return CheckResult(
                name=spec.name,
                source=spec.source,
                package=spec.package,
                current_version=spec.current_version,
                latest_version=None,
                status="unknown",
                candidates=[],
                message=str(exc),
            )

        latest_candidate = select_latest_candidate(
            candidates,
            include_prereleases=spec.include_prereleases,
        )

        latest_version = (
            latest_candidate.normalized_version if latest_candidate is not None else None
        )

        return CheckResult(
            name=spec.name,
            source=spec.source,
            package=spec.package,
            current_version=spec.current_version,
            latest_version=latest_version,
            status=calculate_status(spec.current_version, latest_version),
            candidates=candidates,
        )
