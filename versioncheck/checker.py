"""High-level checker for running many version checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from versioncheck.config import LoadedConfig, load_config
from versioncheck.errors import ConfigError, VersionCheckError
from versioncheck.models import CheckReport, CheckResult, SourceName, ToolSpec
from versioncheck.providers import CondaProvider, GitHubProvider, VersionProvider

ProviderMap = Mapping[SourceName, VersionProvider]


class VersionChecker:
    """Run version checks for a collection of tool specifications."""

    def __init__(
        self,
        tools: list[ToolSpec],
        *,
        providers: ProviderMap | None = None,
        provider_options: Mapping[SourceName, Mapping[str, object]] | None = None,
    ) -> None:
        self._tools = list(tools)
        self._providers = (
            dict(providers)
            if providers is not None
            else _build_providers(provider_options or {})
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        providers: ProviderMap | None = None,
    ) -> VersionChecker:
        """Create a checker from a YAML config file."""

        loaded_config = load_config(path)
        return cls.from_config(loaded_config, providers=providers)

    @classmethod
    def from_config(
        cls,
        config: LoadedConfig,
        *,
        providers: ProviderMap | None = None,
    ) -> VersionChecker:
        """Create a checker from an already loaded config."""

        return cls(
            config.tools,
            providers=providers,
            provider_options=config.provider_options,
        )

    def check_all(self) -> CheckReport:
        """Check every configured tool and return a report."""

        results: list[CheckResult] = []
        for tool in self._tools:
            provider = self._providers.get(tool.source)
            if provider is None:
                results.append(
                    _failure_result(tool, f"No provider for source {tool.source!r}")
                )
                continue

            try:
                results.append(provider.check(tool))
            except VersionCheckError as exc:
                results.append(_failure_result(tool, str(exc)))
            except Exception as exc:
                results.append(
                    _failure_result(
                        tool,
                        f"Unexpected error checking {tool.name!r}: {exc}",
                    )
                )

        return CheckReport(results=results)


def _build_providers(
    provider_options: Mapping[SourceName, Mapping[str, object]]
) -> dict[SourceName, VersionProvider]:
    return {
        "github": GitHubProvider(
            **_github_provider_kwargs(provider_options.get("github", {}))
        ),
        "conda": CondaProvider(
            **_conda_provider_kwargs(provider_options.get("conda", {}))
        ),
    }


def _github_provider_kwargs(options: Mapping[str, object]) -> dict[str, object]:
    kwargs: dict[str, object] = {}

    token = options.get("token")
    if token is not None:
        if not isinstance(token, str):
            raise ConfigError("provider_options.github.token must be a string")
        kwargs["token"] = token

    api_base_url = options.get("api_base_url")
    if api_base_url is not None:
        if not isinstance(api_base_url, str):
            raise ConfigError("provider_options.github.api_base_url must be a string")
        kwargs["api_base_url"] = api_base_url

    timeout_seconds = options.get("timeout_seconds")
    if timeout_seconds is not None:
        kwargs["timeout_seconds"] = _number_option(
            timeout_seconds, "provider_options.github.timeout_seconds"
        )

    return kwargs


def _conda_provider_kwargs(options: Mapping[str, object]) -> dict[str, object]:
    kwargs: dict[str, object] = {}

    channels = options.get("channels")
    if channels is not None:
        kwargs["channels"] = _string_sequence_option(
            channels, "provider_options.conda.channels"
        )

    subdirs = options.get("subdirs")
    if subdirs is not None:
        kwargs["subdirs"] = _string_sequence_option(
            subdirs, "provider_options.conda.subdirs"
        )

    base_url = options.get("base_url")
    if base_url is not None:
        if not isinstance(base_url, str):
            raise ConfigError("provider_options.conda.base_url must be a string")
        kwargs["base_url"] = base_url

    timeout_seconds = options.get("timeout_seconds")
    if timeout_seconds is not None:
        kwargs["timeout_seconds"] = _number_option(
            timeout_seconds, "provider_options.conda.timeout_seconds"
        )

    return kwargs


def _string_sequence_option(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ConfigError(f"{name} must be a string or list of strings")

    values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"{name} entries must be strings")
        values.append(item)
    return tuple(values)


def _number_option(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number")
    return float(value)


def _failure_result(tool: ToolSpec, message: str) -> CheckResult:
    return CheckResult(
        name=tool.name,
        source=tool.source,
        package=tool.package,
        current_version=tool.current_version,
        latest_version=None,
        status="unknown",
        candidates=[],
        message=message,
    )
