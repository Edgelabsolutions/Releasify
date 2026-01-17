# User Guide

This guide covers how to use Releasify for automating semantic versioning and releases in your GitLab or GitHub projects.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Commands](#commands)
- [GitHub Actions Integration](#github-actions-integration)
- [GitLab CI Integration](#gitlab-ci-integration)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Option 1: Docker (Recommended)

Pull the image from GitHub Container Registry:

```bash
docker pull ghcr.io/Edgelabsolutions/releasify:latest
```

### Option 2: Local Installation

```bash
git clone https://github.com/Edgelabsolutions/releasify.git
cd releasify
pip install -r requirements.txt
```

---

## Quick Start

### 1. Create a Configuration File

Create `config.yaml` in your project root:

```yaml
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

### 2. Generate Version

```bash
# Using Docker
docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  -e RELEASE_ACTION=generate-version \
  ghcr.io/Edgelabsolutions/releasify:latest

# Using local installation
python3 release.py generate-version
```

### 3. Create Release

```bash
# Using Docker (GitHub)
docker run --rm \
  -v $(pwd):/repo \
  -w /repo \
  -e RELEASE_ACTION=release \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e PLATFORM=github \
  ghcr.io/edgelabsolutions/releasify:latest

# Using Docker (GitLab)
docker run --rm \
  -v $(pwd):/repo \
  -w /repo \
  -e RELEASE_ACTION=release \
  -e GITLAB_TOKEN=$GITLAB_TOKEN \
  -e PLATFORM=gitlab \
  ghcr.io/edgelabsolutions/releasify:latest

# Using local installation
export GITHUB_TOKEN=your-token  # or GITLAB_TOKEN
python3 release.py release --platform github  # or gitlab
```

---

## Configuration

### Branch Configuration

Define how each branch handles versioning:

```yaml
branches:
  # Release branch - creates stable versions (1.0.0, 1.1.0)
  - name: main
    type: release
    prerelease: null

  # Prerelease branch - creates dev versions (1.0.0-dev.1)
  - name: dev
    type: prerelease
    prerelease: dev

  # Pattern matching - matches alpha/*, beta/*, etc.
  - name: alpha/*
    type: prerelease
    prerelease: alpha

  - name: feature/*
    type: prerelease
    prerelease: feature
```

### Commit Types

Configure which commit types trigger version bumps:

```yaml
commit_types:
  # Breaking changes - major bump (1.0.0 -> 2.0.0)
  breaking:
    bump: major
    keywords:
      - "BREAKING CHANGE"
      - "BREAKING-CHANGE"

  # New features - minor bump (1.0.0 -> 1.1.0)
  feat:
    bump: minor
    aliases: [feature]

  # Bug fixes - patch bump (1.0.0 -> 1.0.1)
  fix:
    bump: patch
    aliases: [bugfix, hotfix]

  # Performance improvements - patch bump
  perf:
    bump: patch

  # Reverts - patch bump
  revert:
    bump: patch
```

### Tag Format

Customize how version tags are created:

```yaml
# Standard: 1.0.0
tag_format: "${version}"

# With prefix: v1.0.0
tag_format: "v${version}"

# Custom prefix: release-1.0.0
tag_format: "release-${version}"
```

### Changelog Settings

Configure changelog generation:

```yaml
changelog:
  file: CHANGELOG.md
  include_types:
    - feat
    - fix
    - perf
    - revert
    - breaking
```

### Commit Validation

Configure commit message validation rules:

```yaml
validation:
  subject_min_length: 3
  subject_max_length: 100
  header_max_length: 100
  subject_lowercase: true
  allowed_scopes: []  # Empty means all scopes allowed
  # allowed_scopes: [api, ui, db, auth]  # Whitelist specific scopes
```

### Slack Notifications (Optional)

Enable release notifications:

```yaml
slack:
  enabled: true
  # Token and channel should be set via environment variables
  # SLACK_TOKEN and SLACK_CHANNEL
```

### Platform Configuration

Set which platform to use for creating releases:

```yaml
# auto: detect from CI environment (default)
# github: use GitHub API
# gitlab: use GitLab API
platform: auto
```

When set to `auto`, Releasify checks:
1. `GITHUB_ACTIONS` environment variable (GitHub Actions)
2. `GITLAB_CI` environment variable (GitLab CI)
3. Git remote URL (looks for github.com or gitlab)
4. Falls back to GitLab if nothing detected

You can override this with the `--platform` CLI flag or `PLATFORM` environment variable.

---

## Commands

### generate-version

Calculates the next version without creating any tags or releases.

```bash
python3 release.py generate-version [options]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--config PATH` | Path to configuration file |
| `--output PATH` | Output file for version info (dotenv format) |

**Output:**
```bash
NEXT_RELEASE_VERSION=1.2.0
LAST_RELEASE_VERSION=1.1.0
```

**Example:**
```bash
python3 release.py generate-version --output version.env
source version.env
echo "Next version: $NEXT_RELEASE_VERSION"
```

### release

Creates a full release: updates changelog, creates tag, and publishes a release on GitHub or GitLab.

```bash
python3 release.py release [options]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--config PATH` | Path to configuration file |
| `--platform PLATFORM` | Platform to use: `auto`, `github`, or `gitlab` |
| `--dry-run` | Simulate release without making changes |

**Required Environment Variables:**
- For GitHub: `GITHUB_TOKEN` with `contents: write` permission
- For GitLab: `GITLAB_TOKEN` with `api` and `write_repository` scopes

**Example:**
```bash
# Dry run first
python3 release.py release --dry-run

# Release on GitHub
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
python3 release.py release --platform github

# Release on GitLab
export GITLAB_TOKEN=glpat-xxxxxxxxxxxx
python3 release.py release --platform gitlab
```

### validate

Validates commit messages against conventional commit format.

```bash
python3 release.py validate [options]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--message TEXT` | Commit message to validate |
| `--message-file PATH` | File containing commit message |
| `--config PATH` | Path to configuration file |

**Example:**
```bash
# Validate a message
python3 release.py validate --message "feat(api): add user endpoint"

# Validate from file
python3 release.py validate --message-file .git/COMMIT_EDITMSG
```

---

## GitHub Actions Integration

### Basic Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/edgelabsolutions/releasify:latest
    permissions:
      contents: write

    # Skip release commits to avoid loops
    if: "!startsWith(github.event.head_commit.message, 'chore(release)')"

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

### Using Version in Other Jobs

```yaml
jobs:
  version:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/edgelabsolutions/releasify:latest
    outputs:
      version: ${{ steps.version.outputs.NEXT_RELEASE_VERSION }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get Version
        id: version
        run: |
          git config --global --add safe.directory $GITHUB_WORKSPACE
          python3 /app/release.py generate-version --platform github --output version.env
          if [ -f version.env ]; then
            cat version.env >> $GITHUB_OUTPUT
          fi

  build:
    needs: version
    runs-on: ubuntu-latest
    steps:
      - run: echo "Building version ${{ needs.version.outputs.version }}"
```

---

## GitLab CI Integration

### Basic Setup

Add to your `.gitlab-ci.yml`:

```yaml
stages:
  - version
  - release

variables:
  RELEASE_IMAGE: ghcr.io/Edgelabsolutions/releasify:latest

generate-version:
  stage: version
  image: $RELEASE_IMAGE
  variables:
    RELEASE_ACTION: generate-version
    OUTPUT_FILE: version.env
  script:
    - /usr/local/bin/entrypoint.sh
  artifacts:
    reports:
      dotenv: version.env
    expire_in: 1 hour
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_BRANCH == "dev"

create-release:
  stage: release
  image: $RELEASE_IMAGE
  variables:
    RELEASE_ACTION: release
  script:
    - /usr/local/bin/entrypoint.sh
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Using Version in Downstream Jobs

```yaml
build-docker:
  stage: build
  needs:
    - job: generate-version
      artifacts: true
  script:
    - echo "Building version $NEXT_RELEASE_VERSION"
    - docker build -t myapp:$NEXT_RELEASE_VERSION .
```

### Commit Validation in Merge Requests

```yaml
validate-commits:
  stage: .pre
  image: $RELEASE_IMAGE
  script:
    - |
      git log origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME..HEAD --format=%H | while read sha; do
        git log -1 --format=%B $sha > /tmp/msg.txt
        python3 /app/release.py validate --message-file /tmp/msg.txt
      done
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Complete Example

```yaml
stages:
  - validate
  - version
  - build
  - release

variables:
  RELEASE_IMAGE: ghcr.io/Edgelabsolutions/releasify:latest

# Validate commits in MRs
validate-commits:
  stage: validate
  image: $RELEASE_IMAGE
  script:
    - python3 /app/release.py validate --message "$CI_COMMIT_MESSAGE"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  allow_failure: true

# Generate version
generate-version:
  stage: version
  image: $RELEASE_IMAGE
  variables:
    RELEASE_ACTION: generate-version
    OUTPUT_FILE: version.env
  script:
    - /usr/local/bin/entrypoint.sh
  artifacts:
    reports:
      dotenv: version.env
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_BRANCH == "dev"

# Build using version
build:
  stage: build
  needs:
    - job: generate-version
      artifacts: true
  script:
    - echo "Version is $NEXT_RELEASE_VERSION"
    - docker build -t myapp:$NEXT_RELEASE_VERSION .
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_BRANCH == "dev"

# Create release (main only)
release:
  stage: release
  image: $RELEASE_IMAGE
  needs:
    - job: build
  variables:
    RELEASE_ACTION: release
  script:
    - /usr/local/bin/entrypoint.sh
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

---

## Examples

### Example 1: Standard Project

A typical project with main and dev branches:

**config.yaml:**
```yaml
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

tag_format: "v${version}"
```

**Workflow:**
```
dev branch:  v1.0.0-dev.1 → v1.0.0-dev.2 → v1.0.0-dev.3
                    ↓ merge to main
main branch: v1.0.0
```

### Example 2: Multiple Prerelease Stages

For projects with alpha → beta → RC workflow:

**config.yaml:**
```yaml
branches:
  - name: main
    type: release
    prerelease: null
  - name: rc
    type: prerelease
    prerelease: rc
  - name: beta
    type: prerelease
    prerelease: beta
  - name: alpha
    type: prerelease
    prerelease: alpha

tag_format: "v${version}"
```

**Workflow:**
```
alpha:  v1.0.0-alpha.1 → v1.0.0-alpha.2
            ↓ merge
beta:   v1.0.0-beta.1 → v1.0.0-beta.2
            ↓ merge
rc:     v1.0.0-rc.1 → v1.0.0-rc.2
            ↓ merge
main:   v1.0.0
```

### Example 3: Feature Branch Releases

For teams that want versioned feature branches:

**config.yaml:**
```yaml
branches:
  - name: main
    type: release
    prerelease: null
  - name: dev
    type: prerelease
    prerelease: dev
  - name: feature/*
    type: prerelease
    prerelease: feature

tag_format: "${version}"
```

**Workflow:**
```
feature/user-auth:  1.0.0-feature.1 → 1.0.0-feature.2
                        ↓ merge
dev:                1.0.0-dev.1
                        ↓ merge
main:               1.0.0
```

### Example 4: Monorepo with Custom Tags

For monorepos with multiple packages:

**config.yaml:**
```yaml
branches:
  - name: main
    type: release
    prerelease: null

tag_format: "mypackage-v${version}"
```

**Result:** Tags like `mypackage-v1.0.0`, `mypackage-v1.1.0`

---

## Troubleshooting

### No Version Bump

**Problem:** Running `generate-version` returns the same version.

**Solutions:**
1. Check commit messages follow conventional format:
   ```
   feat: add new feature    ✓
   fix: bug fix             ✓
   added new feature        ✗
   ```

2. Verify commit type is configured:
   ```yaml
   commit_types:
     feat:
       bump: minor
   ```

3. Check you have commits since the last tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```

### GitLab Release Creation Fails

**Problem:** Release creation fails with 401 or 403 error.

**Solutions:**
1. Check token has correct scopes: `api` and `write_repository`
2. Verify token is not expired
3. Check `CI_PROJECT_URL` is set correctly:
   ```bash
   echo $CI_PROJECT_URL
   ```

### Prerelease Counter Not Incrementing

**Problem:** Prerelease stays at `.1` instead of incrementing.

**Solutions:**
1. Check existing tags match expected pattern:
   ```bash
   git tag -l "1.0.0-dev.*"
   ```

2. Verify branch config is correct:
   ```yaml
   branches:
     - name: dev
       type: prerelease
       prerelease: dev  # Must match tag pattern
   ```

### CHANGELOG Not Updated

**Problem:** CHANGELOG.md is not being updated.

**Solutions:**
1. CHANGELOG is only updated on release branches (not prerelease)
2. Check file permissions
3. Verify the file exists or will be created:
   ```yaml
   changelog:
     file: CHANGELOG.md
   ```

### Docker Permission Issues

**Problem:** Permission denied when running in Docker.

**Solution:** Mount with correct permissions:
```bash
docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  --user $(id -u):$(id -g) \
  ghcr.io/Edgelabsolutions/releasify:latest
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `PLATFORM` | No | Platform override: `github`, `gitlab`, or `auto` |
| `GITHUB_TOKEN` | For GitHub | GitHub API token (auto-set in Actions) |
| `GITLAB_TOKEN` | For GitLab | GitLab API token |
| `GITHUB_REPOSITORY` | Auto in Actions | Repository in `owner/repo` format |
| `CI_PROJECT_URL` | Auto in GitLab CI | GitLab project URL |
| `CONFIG_FILE` | No | Custom config path |
| `DRY_RUN` | No | Set "true" for dry run |
| `OUTPUT_FILE` | No | Version output file |
| `SLACK_TOKEN` | No | Slack bot token |
| `SLACK_CHANNEL` | No | Slack channel |

---

## Getting Help

- Check the [README](../README.md) for quick start
- Review [examples](#examples) above
- Open an issue on GitHub for bugs or questions
