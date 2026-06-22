from versioncheck.models import CheckReport, CheckResult, ToolSpec


def test_tool_spec_metadata_defaults_are_independent():
    first = ToolSpec(name="samtools", source="github", package="samtools/samtools")
    second = ToolSpec(name="bwa", source="conda", package="bwa")

    first.metadata["note"] = "changed"

    assert second.metadata == {}


def test_check_report_tracks_outdated_results():
    current = CheckResult(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.20",
        latest_version="1.20",
        status="current",
    )
    outdated = CheckResult(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
        latest_version="0.7.18",
        status="outdated",
    )

    report = CheckReport(results=[current, outdated])

    assert report.has_outdated is True
    assert report.outdated_results == [outdated]
