# Releasify

**Semantic versioning and release automation for GitLab and GitHub projects.**

[![CI](https://github.com/Edgelabsolutions/releasify/actions/workflows/ci.yml/badge.svg)](https://github.com/Edgelabsolutions/releasify/actions/workflows/ci.yml)
[![Docker](https://github.com/Edgelabsolutions/releasify/actions/workflows/docker.yml/badge.svg)](https://github.com/Edgelabsolutions/releasify/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/Edgelabsolutions/releasify/pkgs/container/releasify)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)

---

## Highlights

- **Conventional Commits** - Parses commit messages to determine version bumps
- **Semantic Versioning** - Handles major.minor.patch versioning based on your commits
- **Prerelease Support** - Branch-specific prerelease tags (dev.1, alpha.2, beta.3)
- **Changelog Generation** - Generates CHANGELOG.md with grouped changes
- **Multi-Platform** - Works with both GitLab and GitHub out of the box
- **Slack Notifications** - Optional notifications for release success/failure
- **Commit Validation** - Built-in commit message linting
- **Docker Ready** - Lightweight Alpine-based image for CI/CD
- **Simple Configuration** - Single YAML file, no complex plugin chains

---

## How Does It Work?

### Commit Message Format

Releasify uses [Conventional Commits](https://www.conventionalcommits.org/) to determine the type of version bump:

| Commit Message | Release Type | Example |
|----------------|--------------|---------|
| `fix: description` | Patch (1.0.0 → 1.0.1) | Bug fixes |
| `feat: description` | Minor (1.0.0 → 1.1.0) | New features |
| `feat!: description` | Major (1.0.0 → 2.0.0) | Breaking changes |
| `BREAKING CHANGE:` in body | Major (1.0.0 → 2.0.0) | Breaking changes |

### CI/CD Integration

Releasify works with GitLab CI and GitHub Actions. On each push to your release branch, it:

1. Analyzes commits since the last release
2. Calculates the next semantic version
3. Updates CHANGELOG.md
4. Creates a git tag
5. Publishes a release (GitLab or GitHub)
6. Sends Slack notification (optional)

The platform is detected automatically from the CI environment, or you can set it explicitly with `--platform github` or `--platform gitlab`.

---

## Quick Start

### Docker

```bash
docker pull ghcr.io/edgelabsolutions/releasify:latest
```

```bash
# Generate version (dry run)
docker run --rm -v $(pwd):/repo -w /repo \
  -e DRY_RUN=true \
  ghcr.io/edgelabsolutions/releasify:latest

# Create release on GitHub
docker run --rm -v $(pwd):/repo -w /repo \
  -e RELEASE_ACTION=release \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e PLATFORM=github \
  ghcr.io/edgelabsolutions/releasify:latest

# Create release on GitLab
docker run --rm -v $(pwd):/repo -w /repo \
  -e RELEASE_ACTION=release \
  -e GITLAB_TOKEN=$GITLAB_TOKEN \
  -e PLATFORM=gitlab \
  ghcr.io/edgelabsolutions/releasify:latest
```

### GitHub Actions

```yaml
release:
  runs-on: ubuntu-latest
  container:
    image: ghcr.io/edgelabsolutions/releasify:latest
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Create Release
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        git config --global --add safe.directory $GITHUB_WORKSPACE
        python3 /app/release.py release --platform github
```

### GitLab CI

```yaml
release:
  image: ghcr.io/edgelabsolutions/releasify:latest
  variables:
    RELEASE_ACTION: release
    PLATFORM: gitlab
  script:
    - /usr/local/bin/entrypoint.sh
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

---

## Documentation

### Getting Started

- [Installation](docs/USER_GUIDE.md#installation)
- [Quick Start](docs/USER_GUIDE.md#quick-start)
- [Configuration](docs/USER_GUIDE.md#configuration)

### Usage

- [CLI Commands](docs/USER_GUIDE.md#commands)
- [GitHub Actions Integration](docs/USER_GUIDE.md#github-actions-integration)
- [GitLab CI Integration](docs/USER_GUIDE.md#gitlab-ci-integration)
- [Examples](docs/USER_GUIDE.md#examples)

### Developer Guide

- [Architecture](docs/DEVELOPER_GUIDE.md#architecture-overview)
- [Module Reference](docs/DEVELOPER_GUIDE.md#module-reference)
- [Extending the Code](docs/DEVELOPER_GUIDE.md#extending-the-code)

### Support

- [Troubleshooting](docs/USER_GUIDE.md#troubleshooting)
- [GitHub Issues](https://github.com/Edgelabsolutions/releasify/issues)

---

## Requirements

- Git repository hosted on GitHub or GitLab
- API token with write access:
  - **GitHub**: `GITHUB_TOKEN` with `contents: write` permission
  - **GitLab**: `GITLAB_TOKEN` with `api` and `write_repository` scopes
- Commits following [Conventional Commits](https://conventionalcommits.org) format

---

## Configuration

Create `config.yaml` in your project root:

```yaml
# Platform: auto, github, or gitlab
platform: auto

branches:
  - name: main
    type: release
    prerelease: null
  - name: dev
    type: prerelease
    prerelease: dev

commit_types:
  feat:
    bump: minor
  fix:
    bump: patch
    aliases: [bugfix, hotfix]

tag_format: "${version}"

changelog:
  file: CHANGELOG.md
  include_types: [feat, fix, perf, revert, breaking]
```

See [Configuration Reference](docs/USER_GUIDE.md#configuration) for all options.

---

## Why Releasify?

| Feature | semantic-release | release-please | Releasify |
|---------|------------------|----------------|-----------|
| Language | Node.js | Node.js | Python |
| Platforms | Multi | GitHub only | GitLab + GitHub |
| Config | JSON + plugins | YAML | Single YAML |
| Dependencies | ~20 packages | ~15 packages | 3 packages |
| Prerelease | Plugin required | Limited | Built-in per-branch |

---

## Badge

Show that your project uses Releasify:

```markdown
[![Releasify](https://img.shields.io/badge/release-releasify-blue)](https://github.com/Edgelabsolutions/releasify)
```

[![Releasify](https://img.shields.io/badge/release-releasify-blue)](https://github.com/Edgelabsolutions/releasify)

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

Before contributing, please read our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Team

### Maintainer

| [![Oleh Hordon](https://github.com/ohordon-eslua.png?size=100)](https://github.com/ohordon-eslua) |
|:---:|
| [Oleh Hordon](https://github.com/ohordon-eslua) |
| Edge Solutions Lab |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2024-2026 Oleh Hordon, Edge Solutions Lab
