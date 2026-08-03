import pytest

from versioncheck.config import load_config
from versioncheck.errors import ConfigError


def test_load_config_keeps_provider_options_separate_from_tool_metadata(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
defaults:
  include_prereleases: true
  version_pattern: '^v?(.*)$'
  metadata:
    platform: linux

provider_options:
  github:
    timeout_seconds: 5
    use_cache: true
  conda:
    channels: ["conda-forge"]
    subdirs: ["linux-64"]
    timeout_seconds: 30

tools:
  - name: samtools-github
    source: github
    package: samtools/samtools
    current_version: "1.20"

  - name: bwa
    source: conda
    package: bwa
    current_version: "0.7.17"
    include_prereleases: false
    metadata:
      channels: ["bioconda"]
      note: tool-level
""",
        encoding="utf-8",
    )

    loaded_config = load_config(path)

    assert loaded_config.path == path
    assert loaded_config.provider_options["github"]["timeout_seconds"] == 5
    assert loaded_config.provider_options["github"]["use_cache"] is True
    assert loaded_config.provider_options["conda"]["channels"] == ["conda-forge"]
    assert loaded_config.provider_options["conda"]["subdirs"] == ["linux-64"]
    assert loaded_config.provider_options["conda"]["timeout_seconds"] == 30

    github_tool = loaded_config.tools[0]
    assert github_tool.name == "samtools-github"
    assert github_tool.source == "github"
    assert github_tool.package == "samtools/samtools"
    assert github_tool.current_version == "1.20"
    assert github_tool.include_prereleases is True
    assert github_tool.version_pattern == "^v?(.*)$"
    assert github_tool.metadata == {"platform": "linux"}

    conda_tool = loaded_config.tools[1]
    assert conda_tool.name == "bwa"
    assert conda_tool.source == "conda"
    assert conda_tool.include_prereleases is False
    assert conda_tool.metadata == {
        "channels": ["bioconda"],
        "note": "tool-level",
        "platform": "linux",
    }


def test_load_config_does_not_copy_provider_token_into_tool_metadata(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
provider_options:
  github:
    token: secret-token

tools:
  - name: samtools
    source: github
    package: samtools/samtools
""",
        encoding="utf-8",
    )

    loaded_config = load_config(path)

    assert loaded_config.provider_options["github"]["token"] == "secret-token"
    assert "token" not in loaded_config.tools[0].metadata


def test_load_config_requires_tools_list(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text("defaults: {}\n", encoding="utf-8")

    with pytest.raises(ConfigError) as error:
        load_config(path)

    assert str(path) in str(error.value)
    assert "missing required field 'tools'" in str(error.value)


def test_load_config_reports_missing_required_field_with_tool_name(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
tools:
  - name: bwa
    source: conda
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as error:
        load_config(path)

    message = str(error.value)
    assert str(path) in message
    assert "tool 'bwa'" in message
    assert "missing required field 'package'" in message


def test_load_config_reports_invalid_source_with_tool_index(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
tools:
  - name: tool
    source: pypi
    package: tool
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as error:
        load_config(path)

    assert "tool 'tool'" in str(error.value)
    assert "source must be one of github, conda" in str(error.value)


def test_load_config_requires_tool_metadata_to_be_mapping(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
tools:
  - name: bwa
    source: conda
    package: bwa
    metadata: ["not", "a", "mapping"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as error:
        load_config(path)

    assert "tool 'bwa'" in str(error.value)
    assert "metadata must be an object" in str(error.value)


def test_load_config_rejects_unknown_provider_options_source(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        """
provider_options:
  pypi:
    timeout_seconds: 5
tools:
  - name: bwa
    source: conda
    package: bwa
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as error:
        load_config(path)

    assert str(path) in str(error.value)
    assert "provider_options source must be one of github, conda" in str(error.value)
