# versioncheck

[![GitHub release](https://img.shields.io/github/v/release/TheBoutrosLab/tool-version-check)](https://github.com/TheBoutrosLab/tool-version-check/actions/workflows/prepare-release.yaml)

Tool for checking and reporting the latest available versions of tools.

## Description

`versioncheck` is a Python package and command-line tool for checking whether software tools have newer versions available from upstream package sources.

Current implemented sources:

- GitHub releases and tags
- Conda-compatible package channels such as conda-forge and bioconda

The package is intended to support release audits, pipeline maintenance, CI checks, and local developer workflows where pinned tool versions need to be compared against the latest available upstream versions.

## Installation

Install the package from the repository root:

```bash
python3 -m pip install -e .
```

For development and test dependencies:

```bash
python3 -m pip install -e '.[dev-dependencies]'
```

## Usage

Check tools from a YAML config file:

```bash
versioncheck check tools.yaml
versioncheck check tools.yaml --format json
versioncheck check tools.yaml --format markdown
```

Check one GitHub repository:

```bash
versioncheck github samtools/samtools --current 1.20
```

Check one conda package:

```bash
versioncheck conda samtools --current 1.20 --channel bioconda --subdir linux-64
```

The CLI exits with `0` when all checked tools are current, `1` when one or more
tools are outdated, and `2` for configuration or provider errors.

Use the Python API directly when integrating with other tooling.

Check a GitHub repository:

```python
from versioncheck.models import ToolSpec
from versioncheck.providers.github import GitHubProvider

provider = GitHubProvider()
spec = ToolSpec(
    name="samtools",
    source="github",
    package="samtools/samtools",
    current_version="1.20",
)

result = provider.check(spec)
print(result.latest_version)
print(result.status)
```

Set `GITHUB_TOKEN` in your environment to increase GitHub API rate limits:

```bash
export GITHUB_TOKEN=your_token_here
```

Check a conda package:

```python
from versioncheck.models import ToolSpec
from versioncheck.providers.conda import CondaProvider

provider = CondaProvider(
    channels=["bioconda"],
    subdirs=["linux-64"],
)
spec = ToolSpec(
    name="samtools",
    source="conda",
    package="samtools",
    current_version="1.20",
)

result = provider.check(spec)
print(result.latest_version)
print(result.status)
```

`result.status` is one of `unknown`, `current`, `outdated`, or
`newer_than_source`.

## License

Author: Yash Patel

tool-version-check is licensed under the GNU General Public License version 2. See the file LICENSE for the terms of the GNU GPL license.

tool-version-check identifies the latest available versions of tools.

Copyright (C) 2026 Sanford Burnham Prebys Medical Discovery Institute ("Boutros Lab")

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
