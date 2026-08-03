from versioncheck.checker import VersionChecker
from versioncheck.errors import ProviderError
from versioncheck.models import SourceName, ToolSpec, VersionCandidate
from versioncheck.providers import VersionProvider
from versioncheck.versioning import make_version_candidate


class RecordingProvider(VersionProvider):
    def __init__(
        self,
        source_name: SourceName,
        versions_by_package: dict[str, list[str]],
    ) -> None:
        self.source_name = source_name
        self.seen_specs: list[ToolSpec] = []
        self._versions_by_package = versions_by_package

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        self.seen_specs.append(spec)
        candidates: list[VersionCandidate] = []
        for version in self._versions_by_package.get(spec.package, []):
            candidate = make_version_candidate(
                version,
                spec.source,
                version_pattern=spec.version_pattern,
            )
            assert candidate is not None
            candidates.append(candidate)
        return candidates


class ProviderErrorProvider(VersionProvider):
    source_name: SourceName = "github"

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        raise ProviderError("known provider failure")


class UnexpectedErrorProvider(VersionProvider):
    source_name: SourceName = "github"

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        raise RuntimeError("boom")


def test_version_checker_from_file_checks_github_and_conda_with_mocked_providers(
    tmp_path,
):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
defaults:
  include_prereleases: false

provider_options:
  conda:
    channels: ["conda-forge"]
    subdirs: ["linux-64"]

tools:
  - name: samtools-github
    source: github
    package: samtools/samtools
    current_version: "1.20"

  - name: bwa
    source: conda
    package: bwa
    current_version: "0.7.17"
    metadata:
      channels: ["bioconda"]
""",
        encoding="utf-8",
    )
    github_provider = RecordingProvider("github", {"samtools/samtools": ["v1.21"]})
    conda_provider = RecordingProvider("conda", {"bwa": ["0.7.18"]})

    checker = VersionChecker.from_file(
        path,
        providers={"github": github_provider, "conda": conda_provider},
    )
    report = checker.check_all()

    assert len(report.results) == 2
    assert report.results[0].name == "samtools-github"
    assert report.results[0].latest_version == "1.21"
    assert report.results[0].status == "outdated"
    assert report.results[1].name == "bwa"
    assert report.results[1].latest_version == "0.7.18"
    assert report.results[1].status == "outdated"
    assert report.has_outdated is True
    assert conda_provider.seen_specs[0].metadata["channels"] == ["bioconda"]
    assert conda_provider.seen_specs[0].metadata["subdirs"] == ["linux-64"]


def test_version_checker_continues_after_known_provider_failure():
    failed_tool = ToolSpec(
        name="bad",
        source="github",
        package="bad/bad",
        current_version="1.0.0",
    )
    checked_tool = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )
    conda_provider = RecordingProvider("conda", {"bwa": ["0.7.18"]})

    report = VersionChecker(
        [failed_tool, checked_tool],
        providers={"github": ProviderErrorProvider(), "conda": conda_provider},
    ).check_all()

    assert [result.status for result in report.results] == ["unknown", "outdated"]
    assert report.results[0].message == "known provider failure"
    assert report.results[1].latest_version == "0.7.18"


def test_version_checker_continues_after_unexpected_provider_failure():
    failed_tool = ToolSpec(
        name="bad",
        source="github",
        package="bad/bad",
        current_version="1.0.0",
    )
    checked_tool = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )
    conda_provider = RecordingProvider("conda", {"bwa": ["0.7.18"]})

    report = VersionChecker(
        [failed_tool, checked_tool],
        providers={"github": UnexpectedErrorProvider(), "conda": conda_provider},
    ).check_all()

    assert [result.status for result in report.results] == ["unknown", "outdated"]
    assert report.results[0].message == "Unexpected error checking 'bad': boom"
    assert report.results[1].latest_version == "0.7.18"


def test_version_checker_reports_missing_provider():
    tool = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    report = VersionChecker([tool], providers={}).check_all()

    assert report.results[0].status == "unknown"
    assert report.results[0].message == "No provider for source 'conda'"
