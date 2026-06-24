from versioncheck.errors import ProviderError
from versioncheck.models import ToolSpec, VersionCandidate
from versioncheck.providers import VersionProvider
from versioncheck.versioning import make_version_candidate


class FakeProvider(VersionProvider):
    source_name = "github"

    def __init__(self, candidates: list[VersionCandidate]) -> None:
        self._candidates = candidates

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        return self._candidates


class FailingProvider(VersionProvider):
    source_name = "github"

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        raise ProviderError("provider failed")


def test_check_selects_latest_candidate_and_builds_result():
    older = make_version_candidate("1.0.0", "github")
    newer = make_version_candidate("v1.2.0", "github")
    assert older is not None
    assert newer is not None

    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = FakeProvider([older, newer]).check(spec)

    assert result.name == "samtools"
    assert result.source == "github"
    assert result.package == "samtools/samtools"
    assert result.current_version == "1.0.0"
    assert result.latest_version == "1.2.0"
    assert result.status == "outdated"
    assert result.candidates == [older, newer]
    assert result.message is None


def test_check_reports_current_when_current_matches_latest():
    candidate = make_version_candidate("v1.2.0", "github")
    assert candidate is not None

    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.2.0",
    )

    result = FakeProvider([candidate]).check(spec)

    assert result.latest_version == "1.2.0"
    assert result.status == "current"


def test_check_returns_unknown_when_current_version_is_missing():
    candidate = make_version_candidate("1.2.0", "github")
    assert candidate is not None

    spec = ToolSpec(name="samtools", source="github", package="samtools/samtools")

    result = FakeProvider([candidate]).check(spec)

    assert result.latest_version == "1.2.0"
    assert result.status == "unknown"


def test_check_filters_prereleases_by_default():
    stable = make_version_candidate("1.0.0", "github")
    prerelease = make_version_candidate("1.1.0rc1", "github")
    assert stable is not None
    assert prerelease is not None

    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = FakeProvider([stable, prerelease]).check(spec)

    assert result.latest_version == "1.0.0"
    assert result.status == "current"


def test_check_can_include_prereleases():
    stable = make_version_candidate("1.0.0", "github")
    prerelease = make_version_candidate("1.1.0rc1", "github")
    assert stable is not None
    assert prerelease is not None

    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
        include_prereleases=True,
    )

    result = FakeProvider([stable, prerelease]).check(spec)

    assert result.latest_version == "1.1.0rc1"
    assert result.status == "outdated"


def test_check_returns_unknown_when_no_candidates_are_available():
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = FakeProvider([]).check(spec)

    assert result.latest_version is None
    assert result.status == "unknown"
    assert result.candidates == []
    assert result.message is None


def test_check_returns_structured_result_for_known_provider_failures():
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = FailingProvider().check(spec)

    assert result.latest_version is None
    assert result.status == "unknown"
    assert result.candidates == []
    assert result.message == "provider failed"
