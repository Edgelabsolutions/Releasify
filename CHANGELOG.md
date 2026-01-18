# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [0.0.2](https://github.com/Edgelabsolutions/Releasify/compare/0.0.1...0.0.2) (2026-01-18)

### Bug Fixes

* ruff format issues and upd actions version ([cebd98d](https://github.com/Edgelabsolutions/Releasify/commit/cebd98d72e3f96270d883cf0dd6615e62f7778e6))

# [0.0.1](https://github.com/Edgelabsolutions/Releasify/compare/1.0.0...0.0.1) (2026-01-17)

### Bug Fixes

* issue with CI ([7906a97](https://github.com/Edgelabsolutions/Releasify/commit/7906a97301a91f3d7637c638b491ff9dcf47d2f9))

## [1.0.0] - 2025-12-17

### Features

- **core:** Initial release of Python-based release automation
- **parser:** Conventional commit parsing with custom type support
- **versioning:** Semantic versioning with prerelease support
- **changelog:** Automatic CHANGELOG.md generation
- **gitlab:** GitLab API integration for releases
- **config:** Flexible YAML-based configuration
- **docker:** Lightweight Docker image with Python 3.12 Alpine

### Improvements Over Semantic-Release

- Simple single-file YAML configuration
- Custom prerelease tags per branch
- No Node.js dependency
- Transparent, maintainable Python code
- Full control over versioning logic
- Smaller Docker image size (~150MB vs 500MB+)
