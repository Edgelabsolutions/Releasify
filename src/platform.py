"""
Platform abstraction for multi-platform release support.

This module provides platform detection and URL generation for both
GitLab and GitHub platforms.
"""

import os
import subprocess
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Supported release platforms."""

    GITLAB = "gitlab"
    GITHUB = "github"


def detect_platform(explicit: Optional[str] = None) -> Platform:
    """
    Detect the current platform from environment or configuration.

    Detection priority:
    1. Explicit parameter (from CLI --platform or config file)
    2. CI environment variables (GITHUB_ACTIONS, GITLAB_CI)
    3. Git remote URL parsing
    4. Default to GitLab (backward compatibility)

    Args:
        explicit: Explicit platform name ("github", "gitlab", or "auto")

    Returns:
        Platform enum value
    """
    # 1. Explicit configuration
    if explicit and explicit.lower() != "auto":
        if explicit.lower() == "github":
            return Platform.GITHUB
        elif explicit.lower() == "gitlab":
            return Platform.GITLAB

    # 2. CI environment detection
    if os.environ.get("GITHUB_ACTIONS") == "true":
        logger.debug("Detected GitHub Actions environment")
        return Platform.GITHUB

    if os.environ.get("GITLAB_CI") == "true":
        logger.debug("Detected GitLab CI environment")
        return Platform.GITLAB

    # 3. Git remote URL parsing
    remote_url = _get_git_remote_url()
    if remote_url:
        if "github.com" in remote_url:
            logger.debug(f"Detected GitHub from remote URL: {remote_url}")
            return Platform.GITHUB
        if "gitlab" in remote_url.lower():
            logger.debug(f"Detected GitLab from remote URL: {remote_url}")
            return Platform.GITLAB

    # 4. Default to GitLab for backward compatibility
    logger.debug("Defaulting to GitLab platform")
    return Platform.GITLAB


def _get_git_remote_url() -> Optional[str]:
    """Get the origin remote URL from git."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"Could not get git remote URL: {e}")
    return None


def get_project_url(platform: Platform) -> Optional[str]:
    """
    Get the project URL for the current platform.

    Args:
        platform: The target platform

    Returns:
        Project URL or None if not available
    """
    if platform == Platform.GITHUB:
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        repo = os.environ.get("GITHUB_REPOSITORY")
        if repo:
            return f"{server}/{repo}"

        # Try to parse from git remote
        remote_url = _get_git_remote_url()
        if remote_url:
            return _parse_github_url(remote_url)

    elif platform == Platform.GITLAB:
        project_url = os.environ.get("CI_PROJECT_URL")
        if project_url:
            return project_url

        # Try to parse from git remote
        remote_url = _get_git_remote_url()
        if remote_url:
            return _parse_gitlab_url(remote_url)

    return None


def _parse_github_url(remote_url: str) -> Optional[str]:
    """Parse GitHub project URL from git remote."""
    # Handle SSH format: git@github.com:owner/repo.git
    if remote_url.startswith("git@github.com:"):
        path = remote_url.replace("git@github.com:", "").rstrip(".git")
        return f"https://github.com/{path}"

    # Handle HTTPS format: https://github.com/owner/repo.git
    if "github.com" in remote_url:
        url = remote_url.rstrip(".git")
        if not url.startswith("https://"):
            url = "https://" + url.split("://", 1)[-1]
        return url

    return None


def _parse_gitlab_url(remote_url: str) -> Optional[str]:
    """Parse GitLab project URL from git remote."""
    # Handle SSH format: git@gitlab.com:group/project.git
    if remote_url.startswith("git@"):
        # Extract host and path
        parts = remote_url.replace("git@", "").split(":", 1)
        if len(parts) == 2:
            host, path = parts
            path = path.rstrip(".git")
            return f"https://{host}/{path}"

    # Handle HTTPS format
    if "gitlab" in remote_url.lower():
        url = remote_url.rstrip(".git")
        if not url.startswith("https://"):
            url = "https://" + url.split("://", 1)[-1]
        return url

    return None


def get_compare_url(
    platform: Platform, project_url: str, from_tag: str, to_tag: str
) -> str:
    """
    Generate a comparison URL between two tags.

    Args:
        platform: Target platform
        project_url: Base project URL
        from_tag: Starting tag/version
        to_tag: Ending tag/version

    Returns:
        Comparison URL
    """
    if platform == Platform.GITHUB:
        # GitHub: https://github.com/owner/repo/compare/v1.0.0...v1.1.0
        return f"{project_url}/compare/{from_tag}...{to_tag}"
    else:
        # GitLab: https://gitlab.com/group/project/-/compare/v1.0.0...v1.1.0
        return f"{project_url}/-/compare/{from_tag}...{to_tag}"


def get_commit_url(platform: Platform, project_url: str, sha: str) -> str:
    """
    Generate a commit URL.

    Args:
        platform: Target platform
        project_url: Base project URL
        sha: Commit SHA

    Returns:
        Commit URL
    """
    if platform == Platform.GITHUB:
        # GitHub: https://github.com/owner/repo/commit/abc123
        return f"{project_url}/commit/{sha}"
    else:
        # GitLab: https://gitlab.com/group/project/-/commit/abc123
        return f"{project_url}/-/commit/{sha}"


def get_tag_url(platform: Platform, project_url: str, tag: str) -> str:
    """
    Generate a tag URL.

    Args:
        platform: Target platform
        project_url: Base project URL
        tag: Tag name

    Returns:
        Tag URL
    """
    if platform == Platform.GITHUB:
        # GitHub: https://github.com/owner/repo/releases/tag/v1.0.0
        return f"{project_url}/releases/tag/{tag}"
    else:
        # GitLab: https://gitlab.com/group/project/-/tags/v1.0.0
        return f"{project_url}/-/tags/{tag}"


def get_release_url(platform: Platform, project_url: str, tag: str) -> str:
    """
    Generate a release URL.

    Args:
        platform: Target platform
        project_url: Base project URL
        tag: Tag/release name

    Returns:
        Release URL
    """
    if platform == Platform.GITHUB:
        # GitHub: https://github.com/owner/repo/releases/tag/v1.0.0
        return f"{project_url}/releases/tag/{tag}"
    else:
        # GitLab: https://gitlab.com/group/project/-/releases/v1.0.0
        return f"{project_url}/-/releases/{tag}"


def get_pipeline_url(platform: Platform) -> Optional[str]:
    """
    Get the current CI pipeline/workflow URL.

    Args:
        platform: Target platform

    Returns:
        Pipeline URL or None
    """
    if platform == Platform.GITHUB:
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        repo = os.environ.get("GITHUB_REPOSITORY")
        run_id = os.environ.get("GITHUB_RUN_ID")
        if repo and run_id:
            return f"{server}/{repo}/actions/runs/{run_id}"
    else:
        return os.environ.get("CI_PIPELINE_URL")

    return None
