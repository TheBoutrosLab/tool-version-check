import json
from datetime import datetime, timezone

from versioncheck.models import CheckReport, CheckResult, VersionCandidate
from versioncheck.reporters import (
    render_json_report,
    render_markdown_report,
    render_table_report,
)


def test_render_json_report_preserves_result_and_candidate_fields():
    report = CheckReport(
        results=[
            CheckResult(
                name="samtools",
                source="github",
                package="samtools/samtools",
                current_version="1.20",
                latest_version="1.21",
                status="outdated",
                candidates=[
                    VersionCandidate(
                        version="v1.21",
                        normalized_version="1.21",
                        source="github",
                        url="https://example.test/release",
                        released_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                        metadata={"kind": "release"},
                    )
                ],
            )
        ]
    )

    payload = json.loads(render_json_report(report))

    assert payload == {
        "results": [
            {
                "candidates": [
                    {
                        "metadata": {"kind": "release"},
                        "normalized_version": "1.21",
                        "released_at": "2026-01-02T00:00:00+00:00",
                        "source": "github",
                        "url": "https://example.test/release",
                        "version": "v1.21",
                    }
                ],
                "current_version": "1.20",
                "latest_version": "1.21",
                "message": None,
                "name": "samtools",
                "package": "samtools/samtools",
                "source": "github",
                "status": "outdated",
            }
        ]
    }


def test_render_table_report_outputs_stable_compact_columns():
    report = _sample_report(include_failure=False)

    assert render_table_report(report) == "\n".join(
        [
            "tool      source  current  latest  status    package",
            "--------  ------  -------  ------  --------  -----------------",
            "bwa       conda   0.7.18   0.7.18  current   bwa",
            "samtools  github  1.20     1.21    outdated  samtools/samtools",
        ]
    )


def test_render_table_report_includes_message_when_failures_exist():
    report = _sample_report(include_failure=True)

    assert render_table_report(report) == "\n".join(
        [
            "tool      source  current  latest  status    package            message",
            (
                "--------  ------  -------  ------  --------  -----------------  "
                "-----------------"
            ),
            "bwa       conda   0.7.18   0.7.18  current   bwa",
            "samtools  github  1.20     1.21    outdated  samtools/samtools",
            "missing   conda   1.0      -       unknown   missing            "
            "package not found",
        ]
    )


def test_render_markdown_report_outputs_stable_table():
    report = _sample_report(include_failure=False)

    assert render_markdown_report(report) == "\n".join(
        [
            "| tool | source | current | latest | status | package |",
            "| --- | --- | --- | --- | --- | --- |",
            "| bwa | conda | 0.7.18 | 0.7.18 | current | bwa |",
            "| samtools | github | 1.20 | 1.21 | outdated | samtools/samtools |",
        ]
    )


def test_render_markdown_report_includes_and_escapes_messages():
    report = CheckReport(
        results=[
            CheckResult(
                name="bad",
                source="github",
                package="bad/repo",
                current_version="1.0",
                latest_version=None,
                status="unknown",
                message="bad | message",
            )
        ]
    )

    assert render_markdown_report(report) == "\n".join(
        [
            "| tool | source | current | latest | status | package | message |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            "| bad | github | 1.0 | - | unknown | bad/repo | bad \\| message |",
        ]
    )


def _sample_report(*, include_failure: bool) -> CheckReport:
    results = [
        CheckResult(
            name="bwa",
            source="conda",
            package="bwa",
            current_version="0.7.18",
            latest_version="0.7.18",
            status="current",
        ),
        CheckResult(
            name="samtools",
            source="github",
            package="samtools/samtools",
            current_version="1.20",
            latest_version="1.21",
            status="outdated",
        ),
    ]

    if include_failure:
        results.append(
            CheckResult(
                name="missing",
                source="conda",
                package="missing",
                current_version="1.0",
                latest_version=None,
                status="unknown",
                message="package not found",
            )
        )

    return CheckReport(results=results)
