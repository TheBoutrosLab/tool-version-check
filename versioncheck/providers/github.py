"""GitHub version provider."""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from datetime import datetime
from typing import Protocol

import requests

from versioncheck.errors import NetworkError, ProviderError
from versioncheck.models import SourceName, ToolSpec, VersionCandidate
from versioncheck.providers.base import VersionProvider
from versioncheck.versioning import make_version_candidate

_GITHUB_API_BASE_URL = "https://api.github.com"
_GITHUB_ACCEPT_HEADER = "application/vnd.github+json"


class _ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]
    text: str

    def json(self) -> object:
        """Return the decoded JSON response body."""


class _SessionLike(Protocol):
    headers: MutableMapping[str, str]

    def get(self, url: str, *, timeout: float) -> _ResponseLike:
        """Fetch a URL."""


class GitHubProvider(VersionProvider):
    """Provider that reads available versions from GitHub releases and tags."""

    source_name: SourceName = "github"

    def __init__(
        self,
        *,
        session: _SessionLike | None = None,
        token: str | None = None,
        api_base_url: str = _GITHUB_API_BASE_URL,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._session: _SessionLike = (
            session if session is not None else requests.Session()
        )
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

        self._session.headers.update({"Accept": _GITHUB_ACCEPT_HEADER})

        github_token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        if github_token:
            self._session.headers.update({"Authorization": f"Bearer {github_token}"})

    def list_versions(self, spec: ToolSpec) -> list[VersionCandidate]:
        """Return GitHub release candidates, falling back to tags if needed."""

        if spec.source != self.source_name:
            raise ProviderError(
                f"GitHubProvider cannot check source {spec.source!r} for {spec.name!r}"
            )

        owner, repository = _parse_repository(spec.package)
        releases = self._list_release_candidates(owner, repository, spec)
        if releases:
            return releases

        return self._list_tag_candidates(owner, repository, spec)

    def _list_release_candidates(
        self, owner: str, repository: str, spec: ToolSpec
    ) -> list[VersionCandidate]:
        release_payloads = self._get_paginated_json(
            f"/repos/{owner}/{repository}/releases", spec.package
        )
        candidates: list[VersionCandidate] = []

        for payload in release_payloads:
            if not isinstance(payload, Mapping):
                raise ProviderError(
                    f"Malformed GitHub release payload for {spec.package}: "
                    "expected an object"
                )

            if payload.get("draft") is True:
                continue
            if payload.get("prerelease") is True and not spec.include_prereleases:
                continue

            tag_name = payload.get("tag_name")
            if not isinstance(tag_name, str):
                raise ProviderError(
                    f"Malformed GitHub release payload for {spec.package}: "
                    "missing tag_name"
                )

            candidate = make_version_candidate(
                tag_name,
                self.source_name,
                url=_string_or_none(payload.get("html_url")),
                released_at=_parse_datetime(payload.get("published_at"), spec.package),
                metadata={
                    "kind": "release",
                    "draft": payload.get("draft") is True,
                    "prerelease": payload.get("prerelease") is True,
                },
                version_pattern=spec.version_pattern,
            )
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _list_tag_candidates(
        self, owner: str, repository: str, spec: ToolSpec
    ) -> list[VersionCandidate]:
        tag_payloads = self._get_paginated_json(
            f"/repos/{owner}/{repository}/tags", spec.package
        )
        candidates: list[VersionCandidate] = []

        for payload in tag_payloads:
            if not isinstance(payload, Mapping):
                raise ProviderError(
                    f"Malformed GitHub tag payload for {spec.package}: "
                    "expected an object"
                )

            tag_name = payload.get("name")
            if not isinstance(tag_name, str):
                raise ProviderError(
                    f"Malformed GitHub tag payload for {spec.package}: missing name"
                )

            candidate = make_version_candidate(
                tag_name,
                self.source_name,
                url=_string_or_none(payload.get("zipball_url")),
                metadata=_tag_metadata(payload),
                version_pattern=spec.version_pattern,
            )
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _get_paginated_json(self, path: str, package: str) -> list[object]:
        url: str | None = self._url(path)
        items: list[object] = []

        while url is not None:
            payload, response = self._get_json(url, package)
            if not isinstance(payload, list):
                raise ProviderError(
                    f"Malformed GitHub payload for {package}: expected a list"
                )

            items.extend(payload)
            url = _next_link(response.headers)

        return items

    def _get_json(self, url: str, package: str) -> tuple[object, _ResponseLike]:
        try:
            response = self._session.get(url, timeout=self._timeout_seconds)
        except requests.RequestException as exc:
            raise NetworkError(f"GitHub request failed for {package}: {exc}") from exc

        if response.status_code >= 400:
            raise _http_error(response, package)

        try:
            return response.json(), response
        except ValueError as exc:
            raise ProviderError(
                f"Malformed GitHub response for {package}: invalid JSON"
            ) from exc

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self._api_base_url}/{path.lstrip('/')}"


def _parse_repository(package: str) -> tuple[str, str]:
    parts = package.split("/")
    if len(parts) != 2 or parts[0] == "" or parts[1] == "":
        raise ProviderError(
            f"GitHub package must be formatted as 'owner/repository': {package!r}"
        )

    return parts[0], parts[1]


def _parse_datetime(value: object, package: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderError(
            f"Malformed GitHub release payload for {package}: published_at "
            "must be a string"
        )
    if value == "":
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderError(
            f"Malformed GitHub release payload for {package}: invalid published_at"
        ) from exc


def _tag_metadata(payload: Mapping[object, object]) -> dict[str, object]:
    metadata: dict[str, object] = {"kind": "tag"}
    commit = payload.get("commit")
    if isinstance(commit, Mapping):
        sha = commit.get("sha")
        if isinstance(sha, str):
            metadata["commit_sha"] = sha
    return metadata


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _next_link(headers: Mapping[str, str]) -> str | None:
    link_header = _header(headers, "Link")
    if link_header is None:
        return None

    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue

        start = section.find("<")
        end = section.find(">", start + 1)
        if start == -1 or end == -1:
            return None
        return section[start + 1 : end]

    return None


def _http_error(response: _ResponseLike, package: str) -> NetworkError:
    message = _response_message(response)
    rate_limit_remaining = _header(response.headers, "X-RateLimit-Remaining")
    if response.status_code == 403 and rate_limit_remaining == "0":
        return NetworkError(f"GitHub API rate limit exceeded for {package}")

    suffix = f": {message}" if message else ""
    return NetworkError(
        f"GitHub API request failed for {package}: HTTP {response.status_code}{suffix}"
    )


def _response_message(response: _ResponseLike) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or None

    if isinstance(payload, Mapping):
        message = payload.get("message")
        if isinstance(message, str):
            return message

    return response.text.strip() or None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for header_name, value in headers.items():
        if header_name.casefold() == name.casefold():
            return value
    return None
