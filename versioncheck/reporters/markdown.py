"""Markdown report rendering."""

from __future__ import annotations

from versioncheck.models import CheckReport, CheckResult

_BASE_COLUMNS = ("tool", "source", "current", "latest", "status", "package")


def render_markdown_report(report: CheckReport) -> str:
    """Render a check report as a Markdown table."""

    rows = [_result_to_row(result) for result in report.results]
    columns = _columns(rows)
    table_rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    table_rows.extend(_format_row(row, columns) for row in rows)
    return "\n".join(table_rows)


def _result_to_row(result: CheckResult) -> dict[str, str]:
    row = {
        "tool": result.name,
        "source": result.source,
        "current": _display(result.current_version),
        "latest": _display(result.latest_version),
        "status": result.status,
        "package": result.package,
    }
    if result.message:
        row["message"] = result.message
    return row


def _columns(rows: list[dict[str, str]]) -> tuple[str, ...]:
    if any("message" in row for row in rows):
        return (*_BASE_COLUMNS, "message")
    return _BASE_COLUMNS


def _format_row(row: dict[str, str], columns: tuple[str, ...]) -> str:
    return "| " + " | ".join(_escape(row.get(column, "")) for column in columns) + " |"


def _display(value: str | None) -> str:
    return value if value is not None else "-"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")
