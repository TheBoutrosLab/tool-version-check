# Changelog

All notable changes to tool-version-check.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-05

### Changed

- Pass GitHub ref metadata into Docker builds instead of copying Git history

### Security

- Reject cross-origin GitHub pagination links before sending authenticated requests

## [1.0.2] - 2026-08-03

### Fixed

- Use full repo to avoid false repo modification detection by git

## [1.0.1] - 2026-08-03

### Fixed

- Match version in image to git tag

## [1.0.0] - 2026-08-03

### Added

- Initial version of `versioncheck`

[1.0.0]: https://github.com/TheBoutrosLab/tool-version-check/releases/tag/v1.0.0
[1.0.1]: https://github.com/TheBoutrosLab/tool-version-check/compare/v1.0.0...v1.0.1
[1.0.2]: https://github.com/TheBoutrosLab/tool-version-check/compare/v1.0.1...v1.0.2
[1.1.0]: https://github.com/TheBoutrosLab/tool-version-check/compare/v1.0.2...v1.1.0
