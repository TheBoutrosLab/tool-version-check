"""Command-line interface for versioncheck."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Any, NoReturn, TextIO

from versioncheck import __version__
from versioncheck.checker import ProviderMap, VersionChecker
from versioncheck.errors import VersionCheckError
from versioncheck.models import CheckReport, SourceName, ToolSpec
from versioncheck.reporters import (
    render_json_report,
    render_markdown_report,
    render_table_report,
)

_FORMATS = ("table", "json", "markdown")
_Renderer = Callable[[CheckReport], str]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    providers: ProviderMap | None = None,
) -> int:
    """Run the versioncheck CLI."""

    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    parser = _build_parser(stdout, stderr)

    try:
        args = parser.parse_args(argv)
        report = _run_command(args, providers=providers)
    except _ParserExit as exc:
        return exc.status
    except VersionCheckError as exc:
        print(str(exc), file=stderr)
        return 2

    print(_render_report(report, args.output_format), file=stdout)
    _print_result_errors(report, stderr)
    return _exit_code(report)


def _build_parser(stdout: TextIO, stderr: TextIO) -> argparse.ArgumentParser:
    parser_class: Any = partial(_ArgumentParser, stdout=stdout, stderr=stderr)
    parser = parser_class(
        prog="versioncheck",
        description="Check latest available versions of software tools.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"versioncheck {__version__}",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=parser_class,
    )

    check_parser = subparsers.add_parser(
        "check",
        help="check all tools from a config file",
    )
    check_parser.add_argument("config_path", type=Path)
    _add_format_argument(check_parser)

    github_parser = subparsers.add_parser(
        "github",
        help="check one GitHub repository",
    )
    github_parser.add_argument("repository", help="GitHub repository as owner/name")
    github_parser.add_argument("--current", dest="current_version")
    github_parser.add_argument(
        "--include-prereleases",
        action="store_true",
        help="include prerelease versions",
    )
    github_parser.add_argument(
        "--version-pattern",
        help="regular expression used to extract the version label",
    )
    _add_format_argument(github_parser)

    conda_parser = subparsers.add_parser(
        "conda",
        help="check one conda package",
    )
    conda_parser.add_argument("package")
    conda_parser.add_argument("--current", dest="current_version")
    conda_parser.add_argument(
        "--channel",
        action="append",
        dest="channels",
        help="conda channel to query; may be supplied multiple times",
    )
    conda_parser.add_argument(
        "--subdir",
        action="append",
        dest="subdirs",
        help="conda subdir/platform to query; may be supplied multiple times",
    )
    conda_parser.add_argument(
        "--include-prereleases",
        action="store_true",
        help="include prerelease versions",
    )
    conda_parser.add_argument(
        "--version-pattern",
        help="regular expression used to extract the version label",
    )
    _add_format_argument(conda_parser)

    return parser


def _add_format_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=_FORMATS,
        default="table",
        dest="output_format",
        help="report format",
    )


def _run_command(
    args: argparse.Namespace,
    *,
    providers: ProviderMap | None,
) -> CheckReport:
    command = _namespace_string(args, "command")
    if command == "check":
        return VersionChecker.from_file(
            _namespace_path(args, "config_path"),
            providers=providers,
        ).check_all()

    if command == "github":
        return _check_single_tool(
            _github_spec(args),
            providers=providers,
        )

    if command == "conda":
        return _check_single_tool(
            _conda_spec(args),
            providers=providers,
        )

    raise VersionCheckError(f"Unknown command: {command}")


def _check_single_tool(
    spec: ToolSpec,
    *,
    providers: ProviderMap | None,
) -> CheckReport:
    return VersionChecker([spec], providers=providers).check_all()


def _github_spec(args: argparse.Namespace) -> ToolSpec:
    repository = _namespace_string(args, "repository")
    return ToolSpec(
        name=repository,
        source="github",
        package=repository,
        current_version=_namespace_optional_string(args, "current_version"),
        include_prereleases=_namespace_bool(args, "include_prereleases"),
        version_pattern=_namespace_optional_string(args, "version_pattern"),
    )


def _conda_spec(args: argparse.Namespace) -> ToolSpec:
    package = _namespace_string(args, "package")
    metadata: dict[str, object] = {}
    channels = _namespace_optional_string_list(args, "channels")
    subdirs = _namespace_optional_string_list(args, "subdirs")

    if channels is not None:
        metadata["channels"] = channels
    if subdirs is not None:
        metadata["subdirs"] = subdirs

    return ToolSpec(
        name=package,
        source="conda",
        package=package,
        current_version=_namespace_optional_string(args, "current_version"),
        include_prereleases=_namespace_bool(args, "include_prereleases"),
        version_pattern=_namespace_optional_string(args, "version_pattern"),
        metadata=metadata,
    )


def _render_report(report: CheckReport, output_format: str) -> str:
    renderers: Mapping[str, _Renderer] = {
        "json": render_json_report,
        "markdown": render_markdown_report,
        "table": render_table_report,
    }

    return renderers[output_format](report)


def _print_result_errors(report: CheckReport, stderr: TextIO) -> None:
    for result in report.results:
        if result.message:
            print(f"{result.name}: {result.message}", file=stderr)


def _exit_code(report: CheckReport) -> int:
    if any(result.message for result in report.results):
        return 2
    if report.has_outdated:
        return 1
    return 0


def _namespace_string(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if not isinstance(value, str):
        raise VersionCheckError(f"Expected {name} to be a string")
    return value


def _namespace_optional_string(args: argparse.Namespace, name: str) -> str | None:
    value = getattr(args, name)
    if value is None or isinstance(value, str):
        return value
    raise VersionCheckError(f"Expected {name} to be a string")


def _namespace_optional_string_list(
    args: argparse.Namespace,
    name: str,
) -> list[str] | None:
    value = getattr(args, name)
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise VersionCheckError(f"Expected {name} to be a list of strings")


def _namespace_bool(args: argparse.Namespace, name: str) -> bool:
    value = getattr(args, name)
    if isinstance(value, bool):
        return value
    raise VersionCheckError(f"Expected {name} to be a boolean")


def _namespace_path(args: argparse.Namespace, name: str) -> Path:
    value = getattr(args, name)
    if isinstance(value, Path):
        return value
    raise VersionCheckError(f"Expected {name} to be a path")


class _ParserExit(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(
        self,
        *args: Any,
        stdout: TextIO,
        stderr: TextIO,
        **kwargs: Any,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        super().__init__(*args, **kwargs)

    def _print_message(self, message: str, file: TextIO | None = None) -> None:
        if not message:
            return

        if file is self._stderr or file is sys.stderr:
            output = self._stderr
        elif file is None or file is self._stdout or file is sys.stdout:
            output = self._stdout
        else:
            output = file
        output.write(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._stderr.write(message)
        raise _ParserExit(status)

    def error(self, message: str) -> NoReturn:
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
