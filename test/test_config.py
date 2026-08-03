import pytest

from versioncheck.config import load_config
from versioncheck.errors import ConfigError


def test_load_config_merges_defaults_provider_options_and_tool_metadata(tmp_path):
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
    assert loaded_config.provider_options["conda"]["channels"] == ["conda-forge"]

    github_tool = loaded_config.tools[0]
    assert github_tool.name == "samtools-github"
    assert github_tool.source == "github"
    assert github_tool.package == "samtools/samtools"
    assert github_tool.current_version == "1.20"
    assert github_tool.include_prereleases is True
    assert github_tool.version_pattern == "^v?(.*)$"
    assert github_tool.metadata["platform"] == "linux"
    assert github_tool.metadata["timeout_seconds"] == 5
    assert github_tool.metadata["use_cache"] is True

    conda_tool = loaded_config.tools[1]
    assert conda_tool.name == "bwa"
    assert conda_tool.source == "conda"
    assert conda_tool.include_prereleases is False
    assert conda_tool.metadata["platform"] == "linux"
    assert conda_tool.metadata["channels"] == ["bioconda"]
    assert conda_tool.metadata["subdirs"] == ["linux-64"]
    assert conda_tool.metadata["timeout_seconds"] == 30
    assert conda_tool.metadata["note"] == "tool-level"


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
