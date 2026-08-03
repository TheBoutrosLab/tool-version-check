from __future__ import annotations

import requests

from versioncheck.models import ToolSpec
from versioncheck.providers.github import GitHubProvider


class FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self) -> object:
        return self._payload


class InvalidJsonResponse(FakeResponse):
    def json(self) -> object:
        raise ValueError("invalid json")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.requests: list[tuple[str, float]] = []
        self._responses = responses

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.requests.append((url, timeout))
        if not self._responses:
            raise AssertionError(f"Unexpected request: {url}")
        return self._responses.pop(0)


class FailingSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        raise requests.RequestException("connection failed")


def test_list_versions_reads_github_releases():
    session = FakeSession(
        [
            FakeResponse(
                [
                    {
                        "tag_name": "v1.2.0",
                        "html_url": (
                            "https://github.com/samtools/samtools/releases/v1.2.0"
                        ),
                        "published_at": "2024-01-02T03:04:05Z",
                        "draft": False,
                        "prerelease": False,
                    }
                ]
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    candidates = provider.list_versions(spec)

    assert len(candidates) == 1
    assert candidates[0].version == "v1.2.0"
    assert candidates[0].normalized_version == "1.2.0"
    assert candidates[0].url == "https://github.com/samtools/samtools/releases/v1.2.0"
    assert candidates[0].released_at is not None
    assert candidates[0].released_at.year == 2024
    assert candidates[0].metadata["kind"] == "release"
    assert session.requests == [
        ("https://api.example/repos/samtools/samtools/releases", 20.0)
    ]


def test_check_uses_mocked_github_release_end_to_end():
    session = FakeSession(
        [
            FakeResponse(
                [
                    {
                        "tag_name": "v1.2.0",
                        "html_url": (
                            "https://github.com/samtools/samtools/releases/v1.2.0"
                        ),
                        "published_at": "2024-01-02T03:04:05Z",
                        "draft": False,
                        "prerelease": False,
                    }
                ]
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.latest_version == "1.2.0"
    assert result.status == "outdated"
    assert result.message is None


def test_list_versions_ignores_drafts_and_prereleases_by_default():
    session = FakeSession(
        [
            FakeResponse(
                [
                    {
                        "tag_name": "v3.0.0",
                        "draft": True,
                        "prerelease": False,
                    },
                    {
                        "tag_name": "v2.0.0rc1",
                        "draft": False,
                        "prerelease": True,
                    },
                    {
                        "tag_name": "v1.0.0",
                        "draft": False,
                        "prerelease": False,
                    },
                ]
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(name="samtools", source="github", package="samtools/samtools")

    candidates = provider.list_versions(spec)

    assert [candidate.normalized_version for candidate in candidates] == ["1.0.0"]


def test_list_versions_can_include_github_prereleases():
    session = FakeSession(
        [
            FakeResponse(
                [
                    {
                        "tag_name": "v2.0.0rc1",
                        "draft": False,
                        "prerelease": True,
                    },
                    {
                        "tag_name": "v1.0.0",
                        "draft": False,
                        "prerelease": False,
                    },
                ]
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        include_prereleases=True,
    )

    candidates = provider.list_versions(spec)

    assert [candidate.normalized_version for candidate in candidates] == [
        "2.0.0rc1",
        "1.0.0",
    ]


def test_list_versions_falls_back_to_tags_when_releases_are_empty():
    session = FakeSession(
        [
            FakeResponse([]),
            FakeResponse(
                [
                    {
                        "name": "v1.2.0",
                        "zipball_url": "https://api.example/zips/v1.2.0",
                        "commit": {"sha": "abc123"},
                    }
                ]
            ),
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(name="samtools", source="github", package="samtools/samtools")

    candidates = provider.list_versions(spec)

    assert len(candidates) == 1
    assert candidates[0].normalized_version == "1.2.0"
    assert candidates[0].url == "https://api.example/zips/v1.2.0"
    assert candidates[0].metadata == {"kind": "tag", "commit_sha": "abc123"}
    assert session.requests == [
        ("https://api.example/repos/samtools/samtools/releases", 20.0),
        ("https://api.example/repos/samtools/samtools/tags", 20.0),
    ]


def test_list_versions_handles_github_pagination():
    session = FakeSession(
        [
            FakeResponse(
                [{"tag_name": "v1.0.0"}],
                headers={
                    "Link": '<https://api.example/page2>; rel="next", '
                    '<https://api.example/page2>; rel="last"'
                },
            ),
            FakeResponse([{"tag_name": "v1.1.0"}]),
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(name="samtools", source="github", package="samtools/samtools")

    candidates = provider.list_versions(spec)

    assert [candidate.normalized_version for candidate in candidates] == [
        "1.0.0",
        "1.1.0",
    ]
    assert session.requests == [
        ("https://api.example/repos/samtools/samtools/releases", 20.0),
        ("https://api.example/page2", 20.0),
    ]


def test_provider_uses_github_token_from_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    session = FakeSession([FakeResponse([]), FakeResponse([])])

    GitHubProvider(session=session)

    assert session.headers["Accept"] == "application/vnd.github+json"
    assert session.headers["Authorization"] == "Bearer secret-token"


def test_provider_can_use_explicit_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    session = FakeSession([FakeResponse([]), FakeResponse([])])

    GitHubProvider(session=session, token="explicit-token")

    assert session.headers["Authorization"] == "Bearer explicit-token"


def test_check_returns_structured_rate_limit_error():
    session = FakeSession(
        [
            FakeResponse(
                {"message": "API rate limit exceeded"},
                status_code=403,
                headers={"X-RateLimit-Remaining": "0"},
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.latest_version is None
    assert result.message == "GitHub API rate limit exceeded for samtools/samtools"


def test_check_returns_structured_http_error():
    session = FakeSession(
        [
            FakeResponse(
                {"message": "Not Found"},
                status_code=404,
            )
        ]
    )
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "GitHub API request failed for samtools/samtools: HTTP 404: Not Found"
    )


def test_check_returns_structured_network_error():
    provider = GitHubProvider(
        session=FailingSession(), api_base_url="https://api.example"
    )
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "GitHub request failed for samtools/samtools: connection failed"
    )


def test_check_returns_structured_malformed_payload_error():
    session = FakeSession([FakeResponse({"not": "a list"})])
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Malformed GitHub payload for samtools/samtools: expected a list"
    )


def test_check_returns_structured_invalid_json_error():
    session = FakeSession([InvalidJsonResponse(None)])
    provider = GitHubProvider(session=session, api_base_url="https://api.example")
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools/samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Malformed GitHub response for samtools/samtools: invalid JSON"
    )


def test_check_returns_structured_invalid_package_error():
    provider = GitHubProvider(
        session=FakeSession([FakeResponse([])]),
        api_base_url="https://api.example",
    )
    spec = ToolSpec(
        name="samtools",
        source="github",
        package="samtools",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "GitHub package must be formatted as 'owner/repository': 'samtools'"
    )
