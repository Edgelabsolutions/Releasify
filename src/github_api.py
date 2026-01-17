"""
GitHub API integration for releases.

This module provides a client for GitHub REST API to:
- Create and update GitHub releases
- Fetch release metadata
- Check release existence

Mirrors the GitLabAPI interface for consistent usage.
"""

import os
import logging
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class GitHubAPI:
    """GitHub API client for release management."""

    # API configuration
    API_VERSION = "2022-11-28"
    DEFAULT_TIMEOUT = (10, 30)  # 10s connect, 30s read

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 0.3
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: Optional[tuple] = None
    ):
        """
        Initialize GitHub API client.

        Args:
            token: GitHub token (defaults to GITHUB_TOKEN or GH_TOKEN env var)
            repo: Repository in 'owner/repo' format (defaults to GITHUB_REPOSITORY env var)
            api_url: API base URL (defaults to https://api.github.com)
            timeout: Tuple of (connect_timeout, read_timeout) in seconds

        Raises:
            GitHubAPIError: If token is missing or repository cannot be determined
        """
        self.token = token or self._get_token()
        self.repo = repo or self._get_repo()
        self.api_url = api_url or os.environ.get(
            "GITHUB_API_URL", "https://api.github.com"
        )
        self.timeout = timeout or self.DEFAULT_TIMEOUT

        if not self.token:
            raise GitHubAPIError(
                "GitHub token not found. Set GITHUB_TOKEN or GH_TOKEN environment variable."
            )

        if not self.repo:
            raise GitHubAPIError(
                "Repository not found. Set GITHUB_REPOSITORY environment variable "
                "or provide repo parameter in 'owner/repo' format."
            )

        # Create session with connection pooling and retry logic
        self.session = self._create_session()

        logger.info(f"GitHub API initialized for repository {self.repo}")

    @staticmethod
    def _get_token() -> Optional[str]:
        """Get GitHub token from environment variables."""
        return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    @staticmethod
    def _get_repo() -> Optional[str]:
        """Get repository from environment or git remote."""
        repo = os.environ.get("GITHUB_REPOSITORY")
        if repo:
            return repo

        # Try to parse from git remote
        try:
            import subprocess
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # Parse owner/repo from URL
                if "github.com" in remote_url:
                    # Handle SSH: git@github.com:owner/repo.git
                    if remote_url.startswith("git@github.com:"):
                        return remote_url.replace("git@github.com:", "").rstrip(".git")
                    # Handle HTTPS: https://github.com/owner/repo.git
                    if "github.com/" in remote_url:
                        path = remote_url.split("github.com/", 1)[1]
                        return path.rstrip(".git")
        except Exception:
            pass

        return None

    def _create_session(self) -> requests.Session:
        """
        Create requests Session with connection pooling and retry logic.

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF_FACTOR,
            status_forcelist=self.RETRY_STATUS_CODES,
            allowed_methods=["GET", "POST", "PATCH", "DELETE"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers per GitHub API requirements
        session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": "releasify/1.0"
        })

        return session

    def create_release(
        self,
        version,
        tag_name: str,
        description: str,
        ref: Optional[str] = None,
        prerelease: bool = False,
        draft: bool = False
    ) -> bool:
        """
        Create a GitHub release.

        Args:
            version: Version object or string
            tag_name: Git tag name
            description: Release description (changelog/body)
            ref: Target commitish (branch/commit) for the tag
            prerelease: Mark as prerelease
            draft: Create as draft release

        Returns:
            True if successful

        Raises:
            GitHubAPIError: If release creation fails
        """
        url = f"{self.api_url}/repos/{self.repo}/releases"

        data = {
            "tag_name": tag_name,
            "name": f"Release {version}",
            "body": description or f"Release {version}",
            "draft": draft,
            "prerelease": prerelease
        }

        if ref:
            data["target_commitish"] = ref

        try:
            logger.info(f"Creating GitHub release for {version}")
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            logger.info(f"Created GitHub release: {version}")
            return True

        except requests.exceptions.HTTPError as e:
            # Handle duplicate release (422 with "already_exists")
            if e.response.status_code == 422:
                try:
                    error_data = e.response.json()
                    errors = error_data.get("errors", [])
                    if any(err.get("code") == "already_exists" for err in errors):
                        logger.warning(f"Release {version} already exists")
                        return True
                except Exception:
                    pass

            error_detail = e.response.text if e.response else str(e)
            logger.error(
                f"HTTP error creating release: {e.response.status_code} - {error_detail}"
            )
            raise GitHubAPIError(
                f"Failed to create release: {e}",
                status_code=e.response.status_code,
                response_data=e.response.json() if e.response else None
            )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout creating release after {self.timeout}s: {e}")
            raise GitHubAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error creating release: {e}")
            raise GitHubAPIError(f"Network error: {e}")

    def update_release(
        self,
        tag_name: str,
        description: Optional[str] = None,
        name: Optional[str] = None
    ) -> bool:
        """
        Update an existing GitHub release.

        Args:
            tag_name: Git tag name
            description: New release body
            name: New release name

        Returns:
            True if successful

        Raises:
            GitHubAPIError: If update fails
        """
        # First get the release to find its ID
        release = self.get_release(tag_name)
        if not release:
            raise GitHubAPIError(f"Release not found: {tag_name}")

        release_id = release.get("id")
        url = f"{self.api_url}/repos/{self.repo}/releases/{release_id}"

        data = {}
        if description is not None:
            data["body"] = description
        if name is not None:
            data["name"] = name

        if not data:
            return True  # Nothing to update

        try:
            logger.info(f"Updating GitHub release: {tag_name}")
            response = self.session.patch(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            logger.info(f"Updated GitHub release: {tag_name}")
            return True

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                f"HTTP error updating release: {e.response.status_code} - {error_detail}"
            )
            raise GitHubAPIError(
                f"Failed to update release: {e}",
                status_code=e.response.status_code,
                response_data=e.response.json() if e.response else None
            )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout updating release: {e}")
            raise GitHubAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error updating release: {e}")
            raise GitHubAPIError(f"Network error: {e}")

    def get_release(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get release information by tag name.

        Args:
            tag_name: Git tag name

        Returns:
            Release data dictionary or None if not found

        Raises:
            GitHubAPIError: If request fails (except 404)
        """
        url = f"{self.api_url}/repos/{self.repo}/releases/tags/{tag_name}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.debug(f"Release not found: {tag_name}")
                return None
            logger.error(f"HTTP error getting release: {e}")
            raise GitHubAPIError(
                f"Failed to get release: {e}",
                status_code=e.response.status_code
            )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout getting release: {e}")
            raise GitHubAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting release: {e}")
            raise GitHubAPIError(f"Network error: {e}")

    def release_exists(self, tag_name: str) -> bool:
        """
        Check if a release exists for the given tag.

        Args:
            tag_name: Git tag name

        Returns:
            True if release exists, False otherwise
        """
        try:
            return self.get_release(tag_name) is not None
        except GitHubAPIError:
            return False

    def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest release.

        Returns:
            Latest release data or None
        """
        url = f"{self.api_url}/repos/{self.repo}/releases/latest"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.debug("No releases found")
                return None
            raise GitHubAPIError(
                f"Failed to get latest release: {e}",
                status_code=e.response.status_code
            )

        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Network error: {e}")

    def close(self) -> None:
        """Close the session and release resources."""
        if self.session:
            self.session.close()
            logger.debug("GitHub API session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
