from __future__ import annotations

import json
from pathlib import Path

import requests

from versioncheck.models import ToolSpec
from versioncheck.providers.conda import CondaProvider

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "conda"


class FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
        text: str = "",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> object:
        return self._payload


class InvalidJsonResponse(FakeResponse):
    def json(self) -> object:
        raise ValueError("invalid json")


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.requests: list[tuple[str, float]] = []
        self._responses = responses

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.requests.append((url, timeout))
        if url not in self._responses:
            raise AssertionError(f"Unexpected request: {url}")
        return self._responses[url]


class FailingSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        raise requests.RequestException("connection failed")


def test_list_versions_reads_packages_and_packages_conda_sections():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: FakeResponse(_fixture("repodata.json"))})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(name="bwa", source="conda", package="bwa")

    candidates = provider.list_versions(spec)

    assert [candidate.normalized_version for candidate in candidates] == [
        "0.7.17",
        "0.7.18",
    ]
    assert candidates[0].metadata == {
        "channel": "bioconda",
        "subdir": "linux-64",
        "build": "h7132678_9",
        "build_number": 9,
        "filename": "bwa-0.7.17-h7132678_9.tar.bz2",
        "package_format": "packages",
    }
    assert candidates[1].metadata["package_format"] == "packages.conda"
    assert session.requests == [
        ("https://conda.example/bioconda/linux-64/repodata.json", 30.0)
    ]


def test_check_selects_latest_across_multiple_channels():
    conda_forge_url = "https://conda.example/conda-forge/linux-64/repodata.json"
    bioconda_url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession(
        {
            conda_forge_url: FakeResponse(
                _repodata("bwa-0.7.17-h7132678_9.tar.bz2", "bwa", "0.7.17")
            ),
            bioconda_url: FakeResponse(
                _repodata("bwa-0.7.18-h577a1d6_1.tar.bz2", "bwa", "0.7.18")
            ),
        }
    )
    provider = CondaProvider(
        channels=["conda-forge", "bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.latest_version == "0.7.18"
    assert result.status == "outdated"
    assert [request[0] for request in session.requests] == [
        conda_forge_url,
        bioconda_url,
    ]


def test_list_versions_uses_tool_metadata_channel_and_noarch_overrides():
    url = "https://conda.example/conda-forge/noarch/repodata.json"
    session = FakeSession({url: FakeResponse(_fixture("noarch-repodata.json"))})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="multiqc",
        source="conda",
        package="multiqc",
        metadata={"channels": ["conda-forge"], "subdirs": ["noarch"]},
    )

    candidates = provider.list_versions(spec)

    assert len(candidates) == 1
    assert candidates[0].normalized_version == "1.25"
    assert candidates[0].metadata["channel"] == "conda-forge"
    assert candidates[0].metadata["subdir"] == "noarch"
    assert session.requests == [(url, 30.0)]


def test_list_versions_returns_empty_list_when_package_is_missing():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: FakeResponse(_fixture("repodata.json"))})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(name="missing", source="conda", package="missing")

    assert provider.list_versions(spec) == []


def test_check_returns_unknown_when_package_is_missing():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: FakeResponse(_fixture("repodata.json"))})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="missing",
        source="conda",
        package="missing",
        current_version="1.0.0",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.latest_version is None
    assert result.candidates == []


def test_check_returns_structured_network_error():
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=FailingSession(),
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Conda repodata request failed for bwa from bioconda/linux-64: "
        "connection failed"
    )


def test_check_returns_structured_http_error():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: FakeResponse({}, status_code=404)})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Conda repodata request failed for bwa from bioconda/linux-64: HTTP 404"
    )


def test_check_returns_structured_invalid_json_error():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: InvalidJsonResponse(None)})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Malformed conda repodata for bioconda/linux-64: invalid JSON"
    )


def test_check_returns_structured_malformed_repodata_error():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession({url: FakeResponse({"packages": []})})
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Malformed conda repodata for bioconda/linux-64: packages must be an object"
    )


def test_check_returns_structured_malformed_record_error():
    url = "https://conda.example/bioconda/linux-64/repodata.json"
    session = FakeSession(
        {
            url: FakeResponse(
                {
                    "packages": {
                        "bwa-unknown.tar.bz2": {
                            "name": "bwa",
                            "version": 123,
                        }
                    }
                }
            )
        }
    )
    provider = CondaProvider(
        channels=["bioconda"],
        subdirs=["linux-64"],
        session=session,
        base_url="https://conda.example",
    )
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == (
        "Malformed conda package record for bwa from bioconda/linux-64: "
        "version must be a string"
    )


def test_check_returns_structured_metadata_error():
    provider = CondaProvider(base_url="https://conda.example")
    spec = ToolSpec(
        name="bwa",
        source="conda",
        package="bwa",
        current_version="0.7.17",
        metadata={"channels": [1]},
    )

    result = provider.check(spec)

    assert result.status == "unknown"
    assert result.message == "Conda channels entries must be strings"


def _fixture(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text())


def _repodata(filename: str, name: str, version: str) -> dict[str, object]:
    return {
        "packages": {
            filename: {
                "name": name,
                "version": version,
                "build": "h123_0",
                "build_number": 0,
            }
        },
        "packages.conda": {},
    }
