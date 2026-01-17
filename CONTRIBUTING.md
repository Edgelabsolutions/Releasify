# Contributing to Releasify

Thank you for your interest in contributing to Releasify! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

When creating a bug report, include:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Your environment (OS, Python version, Docker version if applicable)
- Relevant logs or error messages

### Suggesting Features

Feature requests are welcome. Please provide:
- A clear description of the feature
- The problem it solves or use case
- Any alternative solutions you've considered

### Pull Requests

1. **Fork the repository** and create your branch from `dev`:
   ```bash
   git checkout -b feature/my-feature dev
   ```

2. **Make your changes** following the coding standards below.

3. **Test your changes** locally:
   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Run linting
   pip install ruff
   ruff check src/ release.py
   ruff format --check src/ release.py

   # Test version generation
   python3 release.py generate-version --dry-run

   # Test release (dry run)
   python3 release.py release --dry-run
   ```

4. **Commit your changes** using conventional commits:
   ```bash
   git commit -m "feat(parser): add support for custom commit types"
   ```

5. **Push to your fork** and create a pull request to `dev` branch.

## Coding Standards

### Python Style

- Follow PEP 8 guidelines
- Use type hints where practical
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(changelog): add support for custom section headers

fix(version): handle edge case with prerelease counters

docs: update README with Docker examples
```

### File Organization

```
releasify/
├── src/                    # Core modules
│   ├── config.py           # Configuration
│   ├── commit_parser.py    # Commit parsing
│   ├── version_calc.py     # Version calculation
│   ├── changelog.py        # Changelog generation
│   ├── gitlab_api.py       # GitLab API client
│   ├── git_helper.py       # Git operations
│   └── ...
├── release.py              # Main entry point
├── config.yaml             # Default configuration
└── tests/                  # Tests (if added)
```

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- Docker (optional, for container testing)

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/releasify.git
cd releasify

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install ruff
```

### Docker Development

```bash
# Build image locally
docker build -t releasify:dev .

# Test locally
docker run --rm -v $(pwd):/workspace -w /workspace \
  -e RELEASE_ACTION=generate-version \
  releasify:dev
```

## Testing

### Manual Testing

```bash
# Create a test git repository
mkdir /tmp/test-release && cd /tmp/test-release
git init
git config user.name "Test"
git config user.email "test@example.com"

# Create test commits
echo "# Test" > README.md
git add README.md
git commit -m "feat: initial commit"

# Test version generation
cd /path/to/releasify
python3 release.py generate-version
```

### Validation Testing

```bash
# Test commit validation
python3 release.py validate --message "feat(api): add new endpoint"
python3 release.py validate --message "invalid message"
```

## Release Process

Releases are automated via GitHub Actions when tags are pushed:

1. Merge changes to `main` branch
2. Create and push a tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions will:
   - Create a GitHub release
   - Build and push Docker images

## Questions?

If you have questions, feel free to:
- Open an issue for discussion
- Check existing documentation

Thank you for contributing!
