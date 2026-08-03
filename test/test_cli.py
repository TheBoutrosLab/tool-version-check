import json
from io import StringIO

from versioncheck import __version__
from versioncheck.cli import main
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


class FailingProvider(VersionProvider):
    source_name: SourceName = "github"

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        raise ProviderError("known provider failure")


def test_cli_version_option_prints_version_and_returns_zero():
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["--version"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stdout.getvalue() == f"versioncheck {__version__}\n"
    assert stderr.getvalue() == ""


def test_cli_check_outputs_table_and_returns_zero_for_current_tools(tmp_path):
    config_path = tmp_path / "tools.yaml"
    config_path.write_text(
        """
tools:
  - name: samtools
    source: github
    package: samtools/samtools
    current_version: "1.20"
""",
        encoding="utf-8",
    )
    provider = RecordingProvider("github", {"samtools/samtools": ["v1.20"]})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["check", str(config_path)],
        stdout=stdout,
        stderr=stderr,
        providers={"github": provider},
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue() == "\n".join(
        [
            "tool      source  current  latest  status   package",
            "--------  ------  -------  ------  -------  -----------------",
            "samtools  github  1.20     1.20    current  samtools/samtools",
            "",
        ]
    )


def test_cli_check_outputs_json_and_returns_one_for_outdated_tools(tmp_path):
    config_path = tmp_path / "tools.yaml"
    config_path.write_text(
        """
tools:
  - name: bwa
    source: conda
    package: bwa
    current_version: "0.7.17"
""",
        encoding="utf-8",
    )
    provider = RecordingProvider("conda", {"bwa": ["0.7.18"]})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["check", str(config_path), "--format", "json"],
        stdout=stdout,
        stderr=stderr,
        providers={"conda": provider},
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 1
    assert stderr.getvalue() == ""
    assert payload["results"][0]["latest_version"] == "0.7.18"
    assert payload["results"][0]["status"] == "outdated"


def test_cli_check_outputs_markdown():
    provider = RecordingProvider("github", {"samtools/samtools": ["v1.20"]})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        [
            "github",
            "samtools/samtools",
            "--current",
            "1.20",
            "--format",
            "markdown",
        ],
        stdout=stdout,
        stderr=stderr,
        providers={"github": provider},
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue() == "\n".join(
        [
            "| tool | source | current | latest | status | package |",
            "| --- | --- | --- | --- | --- | --- |",
            "| samtools/samtools | github | 1.20 | 1.20 | current | samtools/samtools |",
            "",
        ]
    )


def test_cli_check_invalid_config_returns_two_and_prints_to_stderr(tmp_path):
    config_path = tmp_path / "tools.yaml"
    config_path.write_text("defaults: {}\n", encoding="utf-8")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["check", str(config_path)],
        stdout=stdout,
        stderr=stderr,
        providers={},
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "missing required field 'tools'" in stderr.getvalue()


def test_cli_direct_github_command_checks_one_repository():
    provider = RecordingProvider("github", {"samtools/samtools": ["v1.21"]})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["github", "samtools/samtools", "--current", "1.20"],
        stdout=stdout,
        stderr=stderr,
        providers={"github": provider},
    )

    assert exit_code == 1
    assert stderr.getvalue() == ""
    assert provider.seen_specs[0].source == "github"
    assert provider.seen_specs[0].package == "samtools/samtools"
    assert "outdated" in stdout.getvalue()


def test_cli_direct_conda_command_passes_channel_and_subdir_metadata():
    provider = RecordingProvider("conda", {"samtools": ["1.21"]})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        [
            "conda",
            "samtools",
            "--current",
            "1.20",
            "--channel",
            "bioconda",
            "--channel",
            "conda-forge",
            "--subdir",
            "linux-64",
        ],
        stdout=stdout,
        stderr=stderr,
        providers={"conda": provider},
    )

    assert exit_code == 1
    assert stderr.getvalue() == ""
    assert provider.seen_specs[0].metadata["channels"] == [
        "bioconda",
        "conda-forge",
    ]
    assert provider.seen_specs[0].metadata["subdirs"] == ["linux-64"]


def test_cli_provider_errors_return_two_and_print_to_stderr():
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["github", "bad/repo", "--current", "1.0"],
        stdout=stdout,
        stderr=stderr,
        providers={"github": FailingProvider()},
    )

    assert exit_code == 2
    assert "known provider failure" in stdout.getvalue()
    assert stderr.getvalue() == "bad/repo: known provider failure\n"
