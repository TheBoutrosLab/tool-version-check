import pytest

from versioncheck.errors import VersionParseError
from versioncheck.versioning import (
    calculate_status,
    compare_versions,
    is_prerelease_version,
    make_version_candidate,
    normalize_version,
    select_latest_candidate,
)


def test_normalize_version_trims_and_strips_leading_v():
    assert normalize_version(" v1.2.3 ") == "1.2.3"


def test_normalize_version_keeps_leading_v_when_not_followed_by_digit():
    assert normalize_version("v-beta") == "v-beta"


def test_normalize_version_uses_named_pattern_group():
    assert (
        normalize_version(
            "release-1.2.3", r"release-(?P<version>\d+\.\d+\.\d+)"
        )
        == "1.2.3"
    )


def test_normalize_version_uses_first_pattern_group():
    assert normalize_version("samtools-1.20.tar.bz2", r"samtools-(\d+\.\d+)") == "1.20"


def test_normalize_version_only_ignores_empty_versions():
    assert normalize_version("") is None
    assert normalize_version("latest") == "latest"
    assert normalize_version("deadbeef") == "deadbeef"


def test_normalize_version_rejects_invalid_pattern():
    with pytest.raises(VersionParseError):
        normalize_version("1.2.3", "[")


def test_compare_versions_uses_packaging_ordering():
    assert compare_versions("1.9", "1.10") < 0
    assert compare_versions("v2.0.0", "2.0") == 0


def test_compare_versions_has_predictable_fallback_ordering():
    assert compare_versions("tool-2", "tool-10") < 0


def test_compare_versions_accepts_arbitrary_version_strings():
    assert compare_versions("latest", "stable") < 0


def test_prerelease_detection_uses_pep440_versions():
    assert is_prerelease_version("1.0.0rc1") is True
    assert is_prerelease_version("1.0.0") is False


def test_select_latest_candidate_ignores_prereleases_by_default():
    stable = make_version_candidate("1.0.0", "github")
    prerelease = make_version_candidate("1.1.0rc1", "github")
    assert stable is not None
    assert prerelease is not None

    latest = select_latest_candidate([stable, prerelease])

    assert latest == stable


def test_select_latest_candidate_can_include_prereleases():
    stable = make_version_candidate("1.0.0", "github")
    prerelease = make_version_candidate("1.1.0rc1", "github")
    assert stable is not None
    assert prerelease is not None

    latest = select_latest_candidate([stable, prerelease], include_prereleases=True)

    assert latest == prerelease


def test_make_version_candidate_accepts_non_digit_values():
    candidate = make_version_candidate("deadbeef", "github")

    assert candidate is not None
    assert candidate.normalized_version == "deadbeef"


def test_calculate_status_values():
    assert calculate_status("1.0.0", "1.0.0") == "current"
    assert calculate_status("1.0.0", "1.0.1") == "outdated"
    assert calculate_status("1.0.1", "1.0.0") == "newer_than_source"
    assert calculate_status(None, "1.0.0") == "unknown"
    assert calculate_status("latest", "latest") == "current"
