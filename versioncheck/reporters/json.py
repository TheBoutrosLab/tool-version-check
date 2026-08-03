"""JSON report rendering."""

from __future__ import annotations

import json as json_module
from datetime import datetime

from versioncheck.models import CheckReport, CheckResult, VersionCandidate


def render_json_report(report: CheckReport) -> str:
    """Render a check report as stable, machine-readable JSON."""

    return json_module.dumps(
        {"results": [_result_to_dict(result) for result in report.results]},
        indent=2,
        sort_keys=True,
    )


def _result_to_dict(result: CheckResult) -> dict[str, object]:
    return {
        "candidates": [
            _candidate_to_dict(candidate) for candidate in result.candidates
        ],
        "current_version": result.current_version,
        "latest_version": result.latest_version,
        "message": result.message,
        "name": result.name,
        "package": result.package,
        "source": result.source,
        "status": result.status,
    }


def _candidate_to_dict(candidate: VersionCandidate) -> dict[str, object]:
    return {
        "metadata": candidate.metadata,
        "normalized_version": candidate.normalized_version,
        "released_at": _datetime_to_string(candidate.released_at),
        "source": candidate.source,
        "url": candidate.url,
        "version": candidate.version,
    }


def _datetime_to_string(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
