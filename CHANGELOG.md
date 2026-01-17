# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
