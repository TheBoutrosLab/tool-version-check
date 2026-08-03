"""Configuration loading for versioncheck."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from versioncheck.errors import ConfigError
from versioncheck.models import SourceName, ToolSpec

_SOURCES: tuple[SourceName, ...] = ("github", "conda")


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    """A parsed versioncheck configuration file."""

    path: Path
    tools: list[ToolSpec]
    provider_options: dict[SourceName, dict[str, object]]


def load_config(path: str | Path) -> LoadedConfig:
    """Load a versioncheck YAML config file."""

    config_path = Path(path)
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw_config is None:
        raw_config = {}

    config = _as_mapping(raw_config, config_path, "configuration")
    defaults = _optional_mapping(config, "defaults", config_path)
    provider_options = _provider_options(config, config_path)
    raw_tools = _required_sequence(config, "tools", config_path)

    tools: list[ToolSpec] = []
    for index, raw_tool in enumerate(raw_tools):
        tool = _as_mapping(
            raw_tool,
            config_path,
            "tool entry",
            tool_index=index,
        )
        tools.append(_tool_spec(tool, defaults, provider_options, config_path, index))

    return LoadedConfig(
        path=config_path,
        tools=tools,
        provider_options=provider_options,
    )


def _tool_spec(
    tool: Mapping[str, object],
    defaults: Mapping[str, object],
    provider_options: Mapping[SourceName, Mapping[str, object]],
    config_path: Path,
    index: int,
) -> ToolSpec:
    merged = {**defaults, **tool}
    tool_name = _string_or_none(tool.get("name"))

    source = _required_source(merged, config_path, tool_name, index)
    metadata = _merged_metadata(
        defaults=defaults,
        provider_metadata=provider_options.get(source, {}),
        tool=tool,
        config_path=config_path,
        tool_name=tool_name,
        index=index,
    )

    return ToolSpec(
        name=_required_string(merged, "name", config_path, tool_name, index),
        source=source,
        package=_required_string(merged, "package", config_path, tool_name, index),
        current_version=_optional_string(
            merged, "current_version", config_path, tool_name, index
        ),
        include_prereleases=_optional_bool(
            merged, "include_prereleases", False, config_path, tool_name, index
        ),
        version_pattern=_optional_string(
            merged, "version_pattern", config_path, tool_name, index
        ),
        metadata=metadata,
    )


def _merged_metadata(
    *,
    defaults: Mapping[str, object],
    provider_metadata: Mapping[str, object],
    tool: Mapping[str, object],
    config_path: Path,
    tool_name: str | None,
    index: int,
) -> dict[str, object]:
    default_metadata = _optional_mapping(
        defaults, "metadata", config_path, tool_name, index
    )
    tool_metadata = _optional_mapping(tool, "metadata", config_path, tool_name, index)

    return {
        **default_metadata,
        **provider_metadata,
        **tool_metadata,
    }


def _provider_options(
    config: Mapping[str, object], config_path: Path
) -> dict[SourceName, dict[str, object]]:
    raw_provider_options = _optional_mapping(config, "provider_options", config_path)
    provider_options: dict[SourceName, dict[str, object]] = {}

    for raw_source, raw_options in raw_provider_options.items():
        if raw_source not in _SOURCES:
            raise ConfigError(
                f"{config_path}: provider_options source must be one of "
                f"{', '.join(_SOURCES)}: {raw_source!r}"
            )

        source = cast(SourceName, raw_source)
        provider_options[source] = dict(
            _as_mapping(
                raw_options,
                config_path,
                f"provider_options.{source}",
            )
        )

    return provider_options


def _required_source(
    mapping: Mapping[str, object],
    config_path: Path,
    tool_name: str | None,
    index: int,
) -> SourceName:
    source = _required_string(mapping, "source", config_path, tool_name, index)
    if source not in _SOURCES:
        raise _tool_config_error(
            config_path,
            f"source must be one of {', '.join(_SOURCES)}: {source!r}",
            tool_name,
            index,
        )
    return cast(SourceName, source)


def _required_string(
    mapping: Mapping[str, object],
    key: str,
    config_path: Path,
    tool_name: str | None,
    index: int,
) -> str:
    value = mapping.get(key)
    if value is None:
        raise _tool_config_error(
            config_path,
            f"missing required field {key!r}",
            tool_name,
            index,
        )
    if not isinstance(value, str):
        raise _tool_config_error(
            config_path,
            f"{key!r} must be a string",
            tool_name,
            index,
        )
    if value.strip() == "":
        raise _tool_config_error(
            config_path,
            f"{key!r} must not be empty",
            tool_name,
            index,
        )
    return value


def _optional_string(
    mapping: Mapping[str, object],
    key: str,
    config_path: Path,
    tool_name: str | None,
    index: int,
) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _tool_config_error(
            config_path,
            f"{key!r} must be a string",
            tool_name,
            index,
        )
    return value


def _optional_bool(
    mapping: Mapping[str, object],
    key: str,
    default: bool,
    config_path: Path,
    tool_name: str | None,
    index: int,
) -> bool:
    value = mapping.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise _tool_config_error(
            config_path,
            f"{key!r} must be a boolean",
            tool_name,
            index,
        )
    return value


def _optional_mapping(
    mapping: Mapping[str, object],
    key: str,
    config_path: Path,
    tool_name: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    value = mapping.get(key)
    if value is None:
        return {}
    return dict(_as_mapping(value, config_path, key, tool_name, index))


def _required_sequence(
    mapping: Mapping[str, object],
    key: str,
    config_path: Path,
) -> Sequence[object]:
    value = mapping.get(key)
    if value is None:
        raise ConfigError(f"{config_path}: missing required field {key!r}")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ConfigError(f"{config_path}: {key!r} must be a list")
    return value


def _as_mapping(
    value: object,
    config_path: Path,
    label: str,
    tool_name: str | None = None,
    tool_index: int | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        if tool_name is not None or tool_index is not None:
            raise _tool_config_error(
                config_path,
                f"{label} must be an object",
                tool_name,
                tool_index,
            )
        raise ConfigError(f"{config_path}: {label} must be an object")

    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigError(f"{config_path}: {label} keys must be strings")
        result[key] = item

    return result


def _tool_config_error(
    config_path: Path,
    message: str,
    tool_name: str | None,
    index: int | None,
) -> ConfigError:
    if tool_name is not None:
        return ConfigError(f"{config_path}: tool {tool_name!r}: {message}")
    if index is not None:
        return ConfigError(f"{config_path}: tool #{index}: {message}")
    return ConfigError(f"{config_path}: {message}")


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None
