# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities.

2. **Email** the maintainers directly at: [security contact to be added]

3. **Include** the following information:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours.
- **Assessment**: We will assess the vulnerability and determine its severity.
- **Fix Timeline**: Critical vulnerabilities will be addressed as quickly as possible.
- **Disclosure**: We will coordinate with you on public disclosure timing.

## Security Best Practices

When using Releasify, follow these security practices:

### Token Security

- **Never commit tokens** to your repository
- Use **CI/CD secrets** for storing `GITLAB_TOKEN` or `GITHUB_TOKEN`
- Use **minimal permissions** - tokens only need `api` and `write_repository` scope

### Docker Image Security

- Use **specific version tags** instead of `latest` in production
- **Verify image digests** for critical deployments
- Keep images **up to date** for security patches

### CI/CD Security

```yaml
# GitHub Actions - Good: Use secrets
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

# GitLab CI - Good: Use CI variables
variables:
  GITLAB_TOKEN: $GITLAB_TOKEN

# Bad: Hardcoded tokens (never do this!)
env:
  GITHUB_TOKEN: "ghp_xxxxxxxxxxxx"
```

### Dependency Security

We regularly scan dependencies for vulnerabilities using `pip-audit`. You can run this locally:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

## Automated Security

### Dependency Scanning

- **Dependabot** monitors for vulnerable dependencies
- **pip-audit** runs in CI on every push
- Weekly scheduled security scans

### Container Security

- Base image: `python:3.14-alpine` (minimal attack surface)
- No unnecessary packages installed
- Non-root user recommended in production

## Known Security Considerations

### Git Operations

The tool executes git commands. Ensure:
- Repository is from a trusted source
- Commit messages don't contain malicious content
- Tags are verified before release

### API Tokens

The tool requires API tokens with write access:

**GitHub tokens** (`GITHUB_TOKEN`) can:
- Create tags and releases
- Push commits (CHANGELOG.md updates)
- Required permission: `contents: write`

**GitLab tokens** (`GITLAB_TOKEN`) can:
- Create tags and releases
- Push commits (CHANGELOG.md updates)
- Required scopes: `api`, `write_repository`

Best practices: limit token scope to what's needed and rotate tokens regularly.

## Changelog

Security-related changes are documented in [CHANGELOG.md](CHANGELOG.md).
