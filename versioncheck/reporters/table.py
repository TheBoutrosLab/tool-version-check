"""Plain text table report rendering."""

from __future__ import annotations

from versioncheck.models import CheckReport, CheckResult

_BASE_COLUMNS = ("tool", "source", "current", "latest", "status", "package")


def render_table_report(report: CheckReport) -> str:
    """Render a check report as a compact plain text table."""

    rows = [_result_to_row(result) for result in report.results]
    columns = _columns(rows)
    widths = _column_widths(rows, columns)
    table_rows = [_header_row(columns, widths), _separator_row(columns, widths)]
    table_rows.extend(_format_row(row, columns, widths) for row in rows)
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


def _header_row(columns: tuple[str, ...], widths: dict[str, int]) -> str:
    return "  ".join(column.ljust(widths[column]) for column in columns).rstrip()


def _separator_row(columns: tuple[str, ...], widths: dict[str, int]) -> str:
    return "  ".join("-" * widths[column] for column in columns).rstrip()


def _format_row(
    row: dict[str, str], columns: tuple[str, ...], widths: dict[str, int]
) -> str:
    return "  ".join(
        row.get(column, "").ljust(widths[column]) for column in columns
    ).rstrip()


def _column_widths(
    rows: list[dict[str, str]], columns: tuple[str, ...]
) -> dict[str, int]:
    return {
        column: max([len(column), *(len(row.get(column, "")) for row in rows)])
        for column in columns
    }


def _display(value: str | None) -> str:
    return value if value is not None else "-"
