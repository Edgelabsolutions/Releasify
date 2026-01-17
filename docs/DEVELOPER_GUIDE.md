# Developer Guide

This guide explains the internal architecture of Releasify for developers who want to understand, modify, or extend the codebase.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Module Reference](#module-reference)
- [Data Flow](#data-flow)
- [Key Algorithms](#key-algorithms)
- [Extending the Code](#extending-the-code)
- [Testing](#testing)

---

## Architecture Overview

Releasify follows a modular architecture where each module has a single responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                        release.py                                │
│                   (CLI & Orchestration)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   config.py   │    │ git_helper.py │    │  platform.py  │
│ Configuration │    │ Git Operations│    │ Platform URLs │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼           ┌────────┴────────┐
┌───────────────┐    ┌───────────────┐    ▼                 ▼
│commit_parser.py│   │ changelog.py  │  ┌──────────┐  ┌──────────┐
│ Parse Commits │    │ Generate Logs │  │gitlab_api│  │github_api│
└───────────────┘    └───────────────┘  └──────────┘  └──────────┘
        │
        ▼
┌───────────────┐
│version_calc.py│
│Calc Versions  │
└───────────────┘
```

### Design Principles

1. **Single Responsibility**: Each module handles one specific task
2. **Dependency Injection**: Configuration and dependencies are passed, not hardcoded
3. **No External Dependencies**: Uses only stdlib + requests + PyYAML + slack-sdk
4. **CI Agnostic**: Works locally and in any CI environment
5. **Transparent Logic**: No magic - all algorithms are readable Python

---

## Module Reference

### `release.py` - Main Orchestrator

**Location:** `/release.py` (530 lines)

**Purpose:** CLI entry point and release workflow orchestration.

**Key Classes:**

```python
class Colors:
    """ANSI color codes for terminal output."""
    RED = "\033[31m"
    GREEN = "\033[32m"
    # ...

class ReleaseOrchestrator:
    """Coordinates the entire release workflow."""

    def __init__(self, config_path: str = None, dry_run: bool = False):
        """Initialize with optional config and dry-run mode."""

    def generate_version(self) -> dict:
        """Calculate next version without creating release."""

    def create_release(self) -> dict:
        """Execute full release workflow."""
```

**Key Functions:**

```python
def validate_message(message: str, config_path: str = None) -> bool:
    """Validate a commit message against conventional commit rules."""

def main():
    """CLI entry point with argparse."""
```

**CLI Arguments:**
- `generate-version`: Calculate next version
- `release`: Create full release
- `validate`: Validate commit message

---

### `src/config.py` - Configuration Management

**Location:** `/src/config.py` (223 lines)

**Purpose:** Load, merge, and provide access to configuration.

**Key Classes:**

```python
@dataclass
class BranchConfig:
    """Configuration for a single branch."""
    name: str           # Branch name or pattern
    type: str           # 'release' or 'prerelease'
    prerelease: str     # Prerelease identifier (e.g., 'dev', 'alpha')

@dataclass
class CommitTypeConfig:
    """Configuration for a commit type."""
    bump: str           # 'major', 'minor', 'patch'
    aliases: list       # Alternative names (e.g., ['bugfix', 'hotfix'])
    keywords: list      # Keywords that trigger this type

class Config:
    """Main configuration class."""

    DEFAULT_CONFIG = {
        'branches': [...],
        'commit_types': {...},
        'tag_format': '${version}',
        # ...
    }

    def __init__(self, config_path: str = None):
        """Load config from file, merge with defaults."""

    def get_branch_config(self, branch_name: str) -> BranchConfig:
        """Get config for branch, supports glob patterns."""

    def get_commit_type(self, type_name: str) -> CommitTypeConfig:
        """Get commit type config, resolving aliases."""
```

**Configuration Resolution Order:**
1. Environment variables (highest priority)
2. Custom config file (`--config`)
3. Auto-discovered `config.yaml`
4. Default configuration (lowest priority)

**Pattern Matching:**
```python
# Uses fnmatch for glob pattern matching
import fnmatch

def get_branch_config(self, branch_name: str) -> BranchConfig:
    for branch in self.branches:
        if fnmatch.fnmatch(branch_name, branch['name']):
            return BranchConfig(**branch)
    return None
```

---

### `src/commit_parser.py` - Commit Parsing

**Location:** `/src/commit_parser.py` (198 lines)

**Purpose:** Parse conventional commits and determine version bumps.

**Key Classes:**

```python
class BumpType(Enum):
    """Version bump types in priority order."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    NONE = "none"

@dataclass
class ParsedCommit:
    """Represents a parsed conventional commit."""
    sha: str            # Commit SHA
    type: str           # Commit type (feat, fix, etc.)
    scope: str          # Optional scope
    subject: str        # Commit subject
    body: str           # Commit body
    is_breaking: bool   # Breaking change flag
    bump: BumpType      # Calculated bump type

class ConventionalCommitParser:
    """Parses conventional commit messages."""

    # Regex pattern for conventional commits
    PATTERN = r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<subject>.+)$'

    def parse(self, message: str, sha: str = "") -> ParsedCommit:
        """Parse a single commit message."""

    def parse_commits(self, commits: list) -> list[ParsedCommit]:
        """Parse multiple commits from (sha, message) tuples."""

    def get_max_bump(self, commits: list[ParsedCommit]) -> BumpType:
        """Get highest priority bump from list of commits."""
```

**Breaking Change Detection:**
```python
def _is_breaking(self, match, body: str) -> bool:
    # Method 1: Exclamation mark in header
    if match.group('breaking'):
        return True

    # Method 2: BREAKING CHANGE in body
    if 'BREAKING CHANGE' in body or 'BREAKING-CHANGE' in body:
        return True

    return False
```

---

### `src/version_calc.py` - Version Calculation

**Location:** `/src/version_calc.py` (340 lines)

**Purpose:** Calculate semantic versions with prerelease support.

**Key Classes:**

```python
@dataclass
class Version:
    """Semantic version representation."""
    major: int
    minor: int
    patch: int
    prerelease: str = None    # e.g., "dev.1", "alpha.2"
    build: str = None         # Build metadata (rarely used)

    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """Parse version string like '1.2.3-dev.1'."""

    def bump(self, bump_type: BumpType) -> 'Version':
        """Return new version with bump applied."""

    def with_prerelease(self, identifier: str, counter: int) -> 'Version':
        """Return new version with prerelease."""

    def __str__(self) -> str:
        """Format as string: 1.2.3 or 1.2.3-dev.1"""

class VersionCalculator:
    """Calculates next version based on commits and branch config."""

    def calculate_next_version(
        self,
        current_version: Version,
        commits: list[ParsedCommit],
        branch_config: BranchConfig
    ) -> Version:
        """Calculate the next version."""
```

**Prerelease Algorithm:**
```python
def _calculate_prerelease_version(self, base_version, branch_config):
    """
    Algorithm:
    1. Get the latest stable version (no prerelease)
    2. Calculate what the next stable would be
    3. Find existing prerelease tags matching pattern
    4. Increment the counter

    Example:
    - Latest stable: 1.2.3
    - Commits contain: feat (minor bump)
    - Next stable would be: 1.3.0
    - Existing tags: 1.3.0-dev.1, 1.3.0-dev.2
    - Result: 1.3.0-dev.3
    """
    pass
```

---

### `src/git_helper.py` - Git Operations

**Location:** `/src/git_helper.py` (351 lines)

**Purpose:** Wrapper for git CLI operations.

**Key Class:**

```python
class GitHelper:
    """Wraps git CLI operations."""

    def __init__(self, repo_path: str = "."):
        """Initialize with repository path."""

    def get_current_branch(self) -> str:
        """Get current branch name (handles CI environments)."""

    def get_latest_tag(self) -> str:
        """Get most recent tag by version sorting."""

    def get_tags_matching(self, pattern: str) -> list[str]:
        """Get tags matching glob pattern."""

    def get_commits_since_tag(self, tag: str) -> list[tuple]:
        """Get (sha, message) tuples since tag."""

    def create_tag(self, tag: str, message: str) -> bool:
        """Create annotated git tag."""

    def push_tag(self, tag: str, remote: str = "origin") -> bool:
        """Push tag to remote."""

    def commit_files(self, files: list, message: str) -> bool:
        """Stage and commit files."""
```

**CI Environment Detection:**
```python
def get_current_branch(self) -> str:
    # GitHub Actions
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        # Pull request: use base branch (merge target)
        if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
            return os.environ.get('GITHUB_BASE_REF')
        # Push: use ref name
        return os.environ.get('GITHUB_REF_NAME')

    # GitLab CI - MR pipeline uses target branch
    if os.environ.get('CI_MERGE_REQUEST_TARGET_BRANCH_NAME'):
        return os.environ['CI_MERGE_REQUEST_TARGET_BRANCH_NAME']

    # GitLab CI - regular pipeline
    if os.environ.get('CI_COMMIT_BRANCH'):
        return os.environ['CI_COMMIT_BRANCH']

    # Local git
    return self._run_git('rev-parse', '--abbrev-ref', 'HEAD')
```

---

### `src/changelog.py` - Changelog Generation

**Location:** `/src/changelog.py` (301 lines)

**Purpose:** Generate and update CHANGELOG.md files.

**Key Class:**

```python
class ChangelogGenerator:
    """Generates and updates CHANGELOG.md."""

    # Commit type to section header mapping
    TYPE_LABELS = {
        'feat': '### Features',
        'fix': '### Bug Fixes',
        'perf': '### Performance',
        'revert': '### Reverts',
        'breaking': '### BREAKING CHANGES',
    }

    def __init__(self, config: Config, project_url: str = None):
        """Initialize with config and project URL for links."""

    def update(self, version: str, commits: list, prev_version: str = None) -> str:
        """Update changelog file and return the new entry."""

    def _group_commits(self, commits: list) -> dict:
        """Group commits by type."""

    def _generate_entry(self, version: str, groups: dict, prev_version: str) -> str:
        """Generate markdown entry for a version."""

    def _generate_compare_url(self, from_ver: str, to_ver: str) -> str:
        """Generate GitLab compare URL."""
```

**Generated Format (GitLab):**
```markdown
## [1.2.0](https://gitlab.com/org/repo/-/compare/1.1.0...1.2.0) (2024-01-15)

### Features

* **api:** add user authentication endpoint ([abc1234](https://gitlab.com/org/repo/-/commit/abc1234))

### Bug Fixes

* **auth:** fix token expiration handling ([ghi9012](https://gitlab.com/org/repo/-/commit/ghi9012))
```

**Generated Format (GitHub):**
```markdown
## [1.2.0](https://github.com/org/repo/compare/1.1.0...1.2.0) (2024-01-15)

### Features

* **api:** add user authentication endpoint ([abc1234](https://github.com/org/repo/commit/abc1234))

### Bug Fixes

* **auth:** fix token expiration handling ([ghi9012](https://github.com/org/repo/commit/ghi9012))
```

---

### `src/gitlab_api.py` - GitLab API Client

**Location:** `/src/gitlab_api.py` (332 lines)

**Purpose:** REST API client for GitLab releases.

**Key Classes:**

```python
class GitLabAPIError(Exception):
    """GitLab API error with status code."""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message)

class GitLabAPI:
    """GitLab REST API client."""

    def __init__(self, token: str = None, project_url: str = None):
        """
        Initialize client.

        Args:
            token: GitLab API token (or from GITLAB_TOKEN env)
            project_url: Project URL (or from CI_PROJECT_URL env)
        """

    def create_release(self, tag: str, name: str, description: str) -> dict:
        """Create a new GitLab release."""

    def update_release(self, tag: str, **kwargs) -> dict:
        """Update an existing release."""

    def get_release(self, tag: str) -> dict:
        """Get release by tag name."""

    def release_exists(self, tag: str) -> bool:
        """Check if release exists."""
```

**API Endpoints Used:**
```python
# Create release
POST /api/v4/projects/{id}/releases

# Get release
GET /api/v4/projects/{id}/releases/{tag}

# Update release
PUT /api/v4/projects/{id}/releases/{tag}
```

**Project ID Resolution:**
```python
def _get_project_id(self) -> str:
    # From environment
    if os.environ.get('CI_PROJECT_ID'):
        return os.environ['CI_PROJECT_ID']

    # Parse from URL: https://gitlab.com/group/project
    # Returns URL-encoded path: group%2Fproject
    return urllib.parse.quote(project_path, safe='')
```

---

### `src/github_api.py` - GitHub API Client

**Location:** `/src/github_api.py`

**Purpose:** REST API client for GitHub releases.

**Key Classes:**

```python
class GitHubAPIError(Exception):
    """GitHub API error with status code."""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message)

class GitHubAPI:
    """GitHub REST API client."""

    def __init__(self, token: str = None, repo: str = None):
        """
        Initialize client.

        Args:
            token: GitHub API token (or from GITHUB_TOKEN env)
            repo: Repository in owner/repo format (or from GITHUB_REPOSITORY env)
        """

    def create_release(self, version, tag_name, description, ref=None, prerelease=False) -> bool:
        """Create a new GitHub release."""

    def update_release(self, tag_name, description=None, name=None) -> bool:
        """Update an existing release."""

    def get_release(self, tag_name) -> dict:
        """Get release by tag name."""

    def release_exists(self, tag_name) -> bool:
        """Check if release exists."""
```

**API Endpoints Used:**
```python
# Create release
POST /repos/{owner}/{repo}/releases

# Get release by tag
GET /repos/{owner}/{repo}/releases/tags/{tag}

# Update release
PATCH /repos/{owner}/{repo}/releases/{release_id}
```

---

### `src/platform.py` - Platform Detection

**Location:** `/src/platform.py`

**Purpose:** Detect CI platform and generate platform-specific URLs.

**Key Classes and Functions:**

```python
class Platform(Enum):
    """Supported platforms."""
    GITLAB = "gitlab"
    GITHUB = "github"

def detect_platform(explicit: str = None) -> Platform:
    """
    Detect which platform we're running on.

    Priority:
    1. Explicit parameter
    2. GITHUB_ACTIONS environment variable
    3. GITLAB_CI environment variable
    4. Git remote URL parsing
    5. Default to GitLab
    """

def get_project_url(platform: Platform) -> str:
    """Get project URL from environment."""

def get_compare_url(platform: Platform, project_url: str, from_tag: str, to_tag: str) -> str:
    """Generate compare URL (different format per platform)."""

def get_commit_url(platform: Platform, project_url: str, sha: str) -> str:
    """Generate commit URL."""

def get_tag_url(platform: Platform, project_url: str, tag: str) -> str:
    """Generate tag URL."""

def get_release_url(platform: Platform, project_url: str, tag: str) -> str:
    """Generate release URL."""
```

**URL Format Differences:**
```python
# GitLab uses /-/ prefix
GitLab: https://gitlab.com/org/repo/-/compare/v1.0.0...v1.1.0
GitLab: https://gitlab.com/org/repo/-/commit/abc123

# GitHub doesn't use /-/
GitHub: https://github.com/org/repo/compare/v1.0.0...v1.1.0
GitHub: https://github.com/org/repo/commit/abc123
```

---

### `src/commit_validator.py` - Commit Validation

**Location:** `/src/commit_validator.py` (351 lines)

**Purpose:** Validate commit messages against rules.

**Key Classes:**

```python
class ValidationLevel(Enum):
    """Validation result severity."""
    ERROR = "error"      # Blocks commit
    WARNING = "warning"  # Allowed but flagged
    INFO = "info"        # Informational

@dataclass
class ValidationResult:
    """Single validation result."""
    level: ValidationLevel
    message: str
    line: int = None

class CommitMessageValidator:
    """Validates conventional commit messages."""

    def validate(self, message: str) -> list[ValidationResult]:
        """Validate message and return all results."""

    def _validate_header(self, header: str) -> list[ValidationResult]:
        """Validate the first line."""

    def _validate_body(self, body: str) -> list[ValidationResult]:
        """Validate the commit body."""
```

**Validation Rules:**
1. Header matches conventional commit format
2. Type is in configured types
3. Scope matches allowed scopes (if configured)
4. Subject length within limits
5. Header length within limits
6. Body line length within limits

---

### `src/slack_notifier.py` - Slack Notifications

**Location:** `/src/slack_notifier.py` (283 lines)

**Purpose:** Send release notifications to Slack.

**Key Classes:**

```python
@dataclass
class SlackConfig:
    """Slack configuration."""
    enabled: bool
    token: str
    channel: str
    notify_success: bool = True
    notify_failure: bool = True

class SlackNotifier:
    """Sends notifications to Slack."""

    def __init__(self, config: SlackConfig):
        """Initialize with Slack config."""

    def notify_success(self, version: str, changelog: str, **kwargs) -> bool:
        """Send success notification."""

    def notify_failure(self, error: str, **kwargs) -> bool:
        """Send failure notification."""
```

---

## Data Flow

### Version Generation Flow

```
1. CLI invokes generate_version()
         │
         ▼
2. Config.load() - Load configuration
         │
         ▼
3. GitHelper.get_current_branch() - Detect branch
         │
         ▼
4. Config.get_branch_config() - Get branch rules
         │
         ▼
5. GitHelper.get_latest_tag() - Find last version
         │
         ▼
6. GitHelper.get_commits_since_tag() - Get commits
         │
         ▼
7. CommitParser.parse_commits() - Parse all commits
         │
         ▼
8. CommitParser.get_max_bump() - Determine bump type
         │
         ▼
9. VersionCalculator.calculate_next_version()
         │
         ▼
10. Output version.env file
```

### Release Creation Flow

```
1. CLI invokes create_release()
         │
         ▼
2. [Version Generation Flow] - Get next version
         │
         ▼
3. ChangelogGenerator.update() - Update CHANGELOG.md
         │
         ▼
4. GitHelper.commit_files() - Commit changelog
         │
         ▼
5. GitHelper.create_tag() - Create version tag
         │
         ▼
6. GitHelper.push_tag() - Push to remote
         │
         ▼
7. GitLabAPI.create_release() - Create GitLab release
         │
         ▼
8. SlackNotifier.notify_success() - Send notification
```

---

## Key Algorithms

### Prerelease Counter Algorithm

```python
def _get_prerelease_counter(self, base_version: Version, identifier: str) -> int:
    """
    Find the next prerelease counter.

    Example:
        base_version: 1.3.0
        identifier: dev
        existing tags: 1.3.0-dev.1, 1.3.0-dev.2, 1.3.0-dev.5
        result: 6
    """
    # Build pattern: 1.3.0-dev.*
    pattern = f"{base_version}-{identifier}.*"

    # Get matching tags
    tags = self.git_helper.get_tags_matching(pattern)

    if not tags:
        return 1

    # Extract counters and find max
    counters = []
    for tag in tags:
        # Parse: 1.3.0-dev.5 -> 5
        match = re.search(rf'{identifier}\.(\d+)$', tag)
        if match:
            counters.append(int(match.group(1)))

    return max(counters) + 1 if counters else 1
```

### Branch Pattern Matching

```python
def get_branch_config(self, branch_name: str) -> BranchConfig:
    """
    Match branch against patterns in order.
    First match wins (like firewall rules).

    Config:
        branches:
          - name: main          # Exact match
          - name: dev           # Exact match
          - name: feature/*     # Glob pattern
          - name: release/*     # Glob pattern

    Examples:
        'main' -> matches 'main'
        'feature/auth' -> matches 'feature/*'
        'feature/auth/oauth' -> matches 'feature/*'
        'unknown' -> no match, returns None
    """
    for branch in self.branches:
        if fnmatch.fnmatch(branch_name, branch['name']):
            return BranchConfig(**branch)
    return None
```

---

## Extending the Code

### Adding a New Commit Type

1. Update `config.yaml`:
```yaml
commit_types:
  docs:
    bump: patch
    aliases: [documentation]
```

2. Optionally update `changelog.py` for custom section header:
```python
TYPE_LABELS = {
    # ...
    'docs': '### Documentation',
}
```

### Adding a New Platform

To add support for another platform (e.g., Bitbucket):

1. Create `src/bitbucket_api.py` following the `gitlab_api.py` or `github_api.py` pattern
2. Add platform enum value in `src/platform.py`
3. Add URL generators in `src/platform.py` for the new platform
4. Update `detect_platform()` to check for Bitbucket CI environment
5. Update `release.py` to initialize the correct API client

### Adding a New Notification Channel

1. Create `src/teams_notifier.py` following `slack_notifier.py` pattern
2. Add configuration in `config.py`
3. Integrate in `release.py` orchestrator

### Custom Validation Rules

Add to `CommitMessageValidator._validate_header()`:
```python
def _validate_header(self, header: str) -> list[ValidationResult]:
    results = []

    # Existing validation...

    # Custom: require ticket number
    if not re.search(r'[A-Z]+-\d+', header):
        results.append(ValidationResult(
            level=ValidationLevel.WARNING,
            message="Consider adding ticket number (e.g., PROJ-123)"
        ))

    return results
```

---

## Testing

### Manual Testing

```bash
# Create test repository
mkdir /tmp/test-repo && cd /tmp/test-repo
git init
git config user.name "Test"
git config user.email "test@test.com"

# Create commits
echo "initial" > README.md
git add README.md
git commit -m "feat: initial commit"

git tag 1.0.0

echo "feature" >> README.md
git add README.md
git commit -m "feat(api): add new endpoint"

# Test from releasify directory
cd /path/to/releasify
python3 release.py generate-version
# Expected: 1.1.0
```

### Unit Testing Components

```python
# Test commit parser
from src.config import Config
from src.commit_parser import ConventionalCommitParser, BumpType

config = Config()
parser = ConventionalCommitParser(config)

# Test parsing
commit = parser.parse("feat(api): add endpoint", "abc123")
assert commit.type == "feat"
assert commit.scope == "api"
assert commit.bump == BumpType.MINOR

# Test breaking change
commit = parser.parse("feat!: breaking change", "def456")
assert commit.is_breaking == True
assert commit.bump == BumpType.MAJOR
```

```python
# Test version calculation
from src.version_calc import Version, VersionCalculator

v = Version.parse("1.2.3")
assert v.major == 1
assert v.minor == 2
assert v.patch == 3

v2 = v.bump(BumpType.MINOR)
assert str(v2) == "1.3.0"

v3 = v2.with_prerelease("dev", 1)
assert str(v3) == "1.3.0-dev.1"
```

### Integration Testing

```bash
# Test full workflow in dry-run
python3 release.py release --dry-run

# Test validation
python3 release.py validate --message "feat: valid message"
echo $?  # Should be 0

python3 release.py validate --message "invalid"
echo $?  # Should be 1
```

---

## Code Style

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use dataclasses for data structures
- Prefer composition over inheritance
- Keep functions small and focused

---

## Questions?

Open an issue on GitHub or check existing documentation.
