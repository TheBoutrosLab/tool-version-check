"""Version normalization, comparison, and status helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from packaging.version import InvalidVersion, Version

from versioncheck.errors import VersionParseError
from versioncheck.models import SourceName, VersionCandidate, VersionStatus

_LEADING_V_RE = re.compile(r"^[vV](?=\d)")
_NATURAL_TOKEN_RE = re.compile(r"\d+|\D+")


def normalize_version(raw_version: str, version_pattern: str | None = None) -> str | None:
    """Normalize a raw version string or return None when it is empty."""

    value = raw_version.strip()
    if value == "":
        return None

    if version_pattern is not None:
        value = _extract_version(value, version_pattern)
        if value is None:
            return None

    value = _LEADING_V_RE.sub("", value.strip())
    if value == "":
        return None

    return value


def make_version_candidate(
    version: str,
    source: SourceName,
    *,
    url: str | None = None,
    released_at: datetime | None = None,
    metadata: Mapping[str, object] | None = None,
    version_pattern: str | None = None,
) -> VersionCandidate | None:
    """Create a candidate from a raw provider version string."""

    normalized_version = normalize_version(version, version_pattern)
    if normalized_version is None:
        return None

    return VersionCandidate(
        version=version,
        normalized_version=normalized_version,
        source=source,
        url=url,
        released_at=released_at,
        metadata=dict(metadata or {}),
    )


def is_prerelease_version(version: str) -> bool:
    """Return whether a version is a PEP 440 prerelease."""

    normalized_version = normalize_version(version)
    if normalized_version is None:
        return False

    parsed_version = _parse_packaging_version(normalized_version)
    if parsed_version is None:
        return False

    return parsed_version.is_prerelease


def compare_versions(left: str, right: str) -> int:
    """Compare two version strings.

    Returns a negative number when left is older, zero when they are equal, and
    a positive number when left is newer.
    """

    left_version = normalize_version(left)
    right_version = normalize_version(right)
    if left_version is None:
        raise VersionParseError(f"Could not parse version: {left!r}")
    if right_version is None:
        raise VersionParseError(f"Could not parse version: {right!r}")

    return compare_normalized_versions(left_version, right_version)


def compare_normalized_versions(left: str, right: str) -> int:
    """Compare two already-normalized version strings."""

    left_packaging_version = _parse_packaging_version(left)
    right_packaging_version = _parse_packaging_version(right)

    if left_packaging_version is not None and right_packaging_version is not None:
        return _compare_packaging_versions(left_packaging_version, right_packaging_version)

    return _compare_fallback_keys(_fallback_key(left), _fallback_key(right))


def select_latest_candidate(
    candidates: Sequence[VersionCandidate], *, include_prereleases: bool = False
) -> VersionCandidate | None:
    """Select the latest candidate after applying prerelease filtering."""

    latest_candidate: VersionCandidate | None = None

    for candidate in candidates:
        if normalize_version(candidate.normalized_version) is None:
            continue
        if not include_prereleases and is_prerelease_version(candidate.normalized_version):
            continue
        if latest_candidate is None:
            latest_candidate = candidate
            continue
        if compare_normalized_versions(
            candidate.normalized_version, latest_candidate.normalized_version
        ) > 0:
            latest_candidate = candidate

    return latest_candidate


def calculate_status(
    current_version: str | None, latest_version: str | None
) -> VersionStatus:
    """Calculate the status for a current version and latest source version."""

    if current_version is None or latest_version is None:
        return "unknown"

    current_normalized = normalize_version(current_version)
    latest_normalized = normalize_version(latest_version)
    if current_normalized is None or latest_normalized is None:
        return "unknown"

    comparison = compare_normalized_versions(current_normalized, latest_normalized)
    if comparison == 0:
        return "current"
    if comparison < 0:
        return "outdated"
    return "newer_than_source"


def _extract_version(raw_version: str, version_pattern: str) -> str | None:
    try:
        match = re.search(version_pattern, raw_version)
    except re.error as exc:
        raise VersionParseError(
            f"Invalid version pattern {version_pattern!r}: {exc}"
        ) from exc

    if match is None:
        return None

    named_version = match.groupdict().get("version")
    if named_version is not None:
        return named_version.strip()

    if match.lastindex is not None and match.lastindex > 0:
        return match.group(1).strip()

    return match.group(0).strip()


def _parse_packaging_version(version: str) -> Version | None:
    try:
        return Version(version)
    except InvalidVersion:
        return None


def _fallback_key(version: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(_fallback_token_key(token) for token in _NATURAL_TOKEN_RE.findall(version))


def _fallback_token_key(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        return (0, int(token))
    return (1, token.casefold())


def _compare_packaging_versions(left: Version, right: Version) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _compare_fallback_keys(
    left: tuple[tuple[int, int | str], ...],
    right: tuple[tuple[int, int | str], ...],
) -> int:
    for left_part, right_part in zip(left, right):
        part_comparison = _compare_fallback_token_keys(left_part, right_part)
        if part_comparison != 0:
            return part_comparison

    return _compare_ints(len(left), len(right))


def _compare_fallback_token_keys(
    left: tuple[int, int | str], right: tuple[int, int | str]
) -> int:
    left_kind, left_value = left
    right_kind, right_value = right

    kind_comparison = _compare_ints(left_kind, right_kind)
    if kind_comparison != 0:
        return kind_comparison

    if isinstance(left_value, int) and isinstance(right_value, int):
        return _compare_ints(left_value, right_value)

    return _compare_strings(str(left_value), str(right_value))


def _compare_ints(left: int, right: int) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _compare_strings(left: str, right: str) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0
