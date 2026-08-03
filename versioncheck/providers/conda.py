"""Conda repodata version provider."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Protocol

import requests

from versioncheck.errors import NetworkError, ProviderError
from versioncheck.models import SourceName, ToolSpec, VersionCandidate
from versioncheck.providers.base import VersionProvider
from versioncheck.versioning import make_version_candidate

_CONDA_BASE_URL = "https://conda.anaconda.org"
_DEFAULT_CHANNELS = ("conda-forge", "bioconda")
_DEFAULT_SUBDIRS = ("linux-64", "noarch")


class _ResponseLike(Protocol):
    status_code: int
    text: str

    def json(self) -> object:
        """Return the decoded JSON response body."""


class _SessionLike(Protocol):
    headers: MutableMapping[str, str]

    def get(self, url: str, *, timeout: float) -> _ResponseLike:
        """Fetch a URL."""


class CondaProvider(VersionProvider):
    """Provider that reads available versions from conda channel repodata."""

    source_name: SourceName = "conda"

    def __init__(
        self,
        *,
        channels: Sequence[str] = _DEFAULT_CHANNELS,
        subdirs: Sequence[str] = _DEFAULT_SUBDIRS,
        session: _SessionLike | None = None,
        base_url: str = _CONDA_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._channels = _validate_string_sequence(channels, "channels")
        self._subdirs = _validate_string_sequence(subdirs, "subdirs")
        self._session: _SessionLike = (
            session if session is not None else requests.Session()
        )
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        """Return conda package candidates across configured channels/subdirs."""

        if spec.source != self.source_name:
            raise ProviderError(
                f"CondaProvider cannot check source {spec.source!r} for {spec.name!r}"
            )

        channels = _metadata_string_sequence(
            spec.metadata, "channels", self._channels, spec.package
        )
        subdirs = _metadata_string_sequence(
            spec.metadata, "subdirs", self._subdirs, spec.package
        )
        candidates: list[VersionCandidate] = []

        for channel in channels:
            for subdir in subdirs:
                repodata = self._fetch_repodata(channel, subdir, spec.package)
                candidates.extend(
                    self._candidates_from_repodata(repodata, channel, subdir, spec)
                )

        return candidates

    def _fetch_repodata(
        self, channel: str, subdir: str, package: str
    ) -> Mapping[str, object]:
        url = f"{self._base_url}/{channel}/{subdir}/repodata.json"

        try:
            response = self._session.get(url, timeout=self._timeout_seconds)
        except requests.RequestException as exc:
            raise NetworkError(
                f"Conda repodata request failed for {package} "
                f"from {channel}/{subdir}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise NetworkError(
                f"Conda repodata request failed for {package} "
                f"from {channel}/{subdir}: HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(
                f"Malformed conda repodata for {channel}/{subdir}: invalid JSON"
            ) from exc

        if not isinstance(payload, Mapping):
            raise ProviderError(
                f"Malformed conda repodata for {channel}/{subdir}: "
                "expected an object"
            )

        return payload

    def _candidates_from_repodata(
        self,
        repodata: Mapping[str, object],
        channel: str,
        subdir: str,
        spec: ToolSpec,
    ) -> list[VersionCandidate]:
        candidates: list[VersionCandidate] = []

        for section_name in ("packages", "packages.conda"):
            section = repodata.get(section_name)
            if section is None:
                continue
            if not isinstance(section, Mapping):
                raise ProviderError(
                    f"Malformed conda repodata for {channel}/{subdir}: "
                    f"{section_name} must be an object"
                )

            for filename, record in section.items():
                if not isinstance(filename, str) or not isinstance(record, Mapping):
                    raise ProviderError(
                        f"Malformed conda repodata for {channel}/{subdir}: "
                        f"{section_name} entries must map filenames to objects"
                    )

                candidate = _candidate_from_record(
                    record,
                    filename=filename,
                    section_name=section_name,
                    channel=channel,
                    subdir=subdir,
                    spec=spec,
                )
                if candidate is not None:
                    candidates.append(candidate)

        return candidates


def _candidate_from_record(
    record: Mapping[object, object],
    *,
    filename: str,
    section_name: str,
    channel: str,
    subdir: str,
    spec: ToolSpec,
) -> VersionCandidate | None:
    name = record.get("name")
    if name != spec.package:
        return None

    version = record.get("version")
    if not isinstance(version, str):
        raise ProviderError(
            f"Malformed conda package record for {spec.package} "
            f"from {channel}/{subdir}: version must be a string"
        )

    return make_version_candidate(
        version,
        "conda",
        metadata={
            "channel": channel,
            "subdir": subdir,
            "build": _string_or_none(record.get("build")),
            "build_number": _object_or_none(record.get("build_number")),
            "filename": filename,
            "package_format": section_name,
        },
        version_pattern=spec.version_pattern,
    )


def _metadata_string_sequence(
    metadata: Mapping[str, object],
    key: str,
    default: tuple[str, ...],
    package: str,
) -> tuple[str, ...]:
    value = metadata.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return _validate_string_sequence((value,), key)
    if isinstance(value, Sequence):
        return _validate_string_sequence(value, key)

    raise ProviderError(
        f"Conda metadata {key!r} for {package} must be a string or sequence of strings"
    )


def _validate_string_sequence(values: Sequence[str], name: str) -> tuple[str, ...]:
    normalized_values: list[str] = []

    for value in values:
        if not isinstance(value, str):
            raise ProviderError(f"Conda {name} entries must be strings")

        normalized_value = value.strip()
        if normalized_value == "":
            raise ProviderError(f"Conda {name} entries must not be empty")

        normalized_values.append(normalized_value)

    if not normalized_values:
        raise ProviderError(f"Conda {name} must not be empty")

    return tuple(normalized_values)


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _object_or_none(value: object) -> object | None:
    return value
