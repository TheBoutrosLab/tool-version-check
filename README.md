# versioncheck

[![GitHub release](https://img.shields.io/github/v/release/TheBoutrosLab/tool-version-check)](https://github.com/TheBoutrosLab/tool-version-check/actions/workflows/prepare-release.yaml)

Tool for checking and reporting the latest available versions of tools.

## Description

`versioncheck` is a Python package and command-line tool for checking whether software tools have newer versions available from upstream package sources.

Current implemented sources:

- GitHub releases and tags
- Conda-compatible package channels such as conda-forge and bioconda

The package is intended to support release audits, pipeline maintenance, CI checks, and local developer workflows where pinned tool versions need to be compared against the latest available upstream versions.

## License

Author: Yash Patel

tool-version-check is licensed under the GNU General Public License version 2. See the file LICENSE for the terms of the GNU GPL license.

tool-version-check identifies the latest available versions of tools.

Copyright (C) 2026 Sanford Burnham Prebys Medical Discovery Institute ("Boutros Lab")

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
