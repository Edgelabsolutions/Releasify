"""
GitLab API integration for releases.

This module provides a thin client for:
- Resolving project identifiers from CI variables or project URL
- Creating and updating GitLab releases
- Fetching release metadata

IMPROVEMENTS:
- Added timeout to all HTTP requests (security)
- Using requests.Session for connection pooling (performance)
- Added logging instead of print() (production-ready)
- Improved error handling with detailed exceptions
- Added retry logic for transient failures
- Type hints on all public methods
"""

import os
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, quote

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from src.version_calc import Version
from src.config import Config

# Configure module logger
logger = logging.getLogger(__name__)


class GitLabAPIError(Exception):
    """Custom exception for GitLab API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class GitLabAPI:
    """GitLab API client for release management."""

    # Timeout configuration (connect_timeout, read_timeout)
    DEFAULT_TIMEOUT = (10, 30)  # 10s connect, 30s read

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 0.3
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

    def __init__(
        self,
        project_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[tuple] = None,
    ):
        """
        Initialize GitLab API client.

        Args:
            project_url: GitLab project URL (e.g., https://gitlab.com/group/project)
            token: GitLab API token with api and write_repository scopes
            timeout: Tuple of (connect_timeout, read_timeout) in seconds

        Raises:
            GitLabAPIError: If token is missing or project info cannot be extracted
        """
        self.project_url = project_url or os.getenv("CI_PROJECT_URL")
        self.token = Config.get_gitlab_token(token)
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.server_url = os.getenv("CI_SERVER_URL", "https://gitlab.com")
        self.project_id = os.getenv("CI_PROJECT_ID")

        if not self.token:
            raise GitLabAPIError(
                "GitLab token not found. Set GL_TOKEN or GITLAB_TOKEN environment variable."
            )

        if not self.project_id:
            # Extract from URL if not in CI
            self._extract_project_info()

        self.api_url = f"{self.server_url}/api/v4"

        # Create session with connection pooling and retry logic
        self.session = self._create_session()

        logger.info(f"GitLab API initialized for project {self.project_id}")

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
            allowed_methods=["GET", "POST", "PUT"],  # Retry safe methods
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update(
            {
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json",
                "User-Agent": "releasify/1.0",
            }
        )

        return session

    def _extract_project_info(self) -> None:
        """
        Extract project ID from project URL.

        Raises:
            GitLabAPIError: If project URL is missing or invalid
        """
        if not self.project_url:
            raise GitLabAPIError(
                "Project URL not found. Set CI_PROJECT_URL or provide project_url."
            )

        # Parse URL: https://gitlab.com/group/subgroup/project
        try:
            parsed = urlparse(self.project_url)
            self.server_url = f"{parsed.scheme}://{parsed.netloc}"

            # Get project path
            path = parsed.path.strip("/")
            if path.endswith(".git"):
                path = path[:-4]

            # URL-encode the path to use as project ID
            self.project_id = quote(path, safe="")

            logger.debug(f"Extracted project ID: {self.project_id}")
        except Exception as e:
            raise GitLabAPIError(f"Failed to parse project URL: {e}")

    def create_release(
        self,
        version: Version,
        tag_name: str,
        description: str,
        ref: Optional[str] = None,
    ) -> bool:
        """
        Create a GitLab release.

        Args:
            version: Version object
            tag_name: Git tag name
            description: Release description (changelog entry)
            ref: Git ref (branch/commit) to create release from (default: tag)

        Returns:
            True if successful, False otherwise

        Raises:
            GitLabAPIError: If release creation fails (except for 409 conflict)
        """
        url = f"{self.api_url}/projects/{self.project_id}/releases"

        data = {
            "name": f"Release {version}",
            "tag_name": tag_name,
            "description": description or f"Release {version}",
        }

        if ref:
            data["ref"] = ref

        try:
            logger.info(f"Creating GitLab release for {version}")
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            logger.info(f"✅ Created GitLab release: {version}")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.warning(f"Release {version} already exists")
                return True  # Not an error
            else:
                error_detail = e.response.text if e.response else str(e)
                logger.error(
                    f"HTTP error creating release: {e.response.status_code} - {error_detail}"
                )
                raise GitLabAPIError(
                    f"Failed to create release: {e}",
                    status_code=e.response.status_code,
                    response_data=e.response.json() if e.response else None,
                )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout creating release after {self.timeout}s: {e}")
            raise GitLabAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error creating release: {e}")
            raise GitLabAPIError(f"Network error: {e}")

    def update_release(
        self,
        tag_name: str,
        description: Optional[str] = None,
        name: Optional[str] = None,
    ) -> bool:
        """
        Update an existing GitLab release.

        Args:
            tag_name: Git tag name
            description: New release description
            name: New release name

        Returns:
            True if successful

        Raises:
            GitLabAPIError: If update fails
        """
        url = f"{self.api_url}/projects/{self.project_id}/releases/{tag_name}"

        data = {}
        if description:
            data["description"] = description
        if name:
            data["name"] = name

        if not data:
            return True  # Nothing to update

        try:
            logger.info(f"Updating GitLab release: {tag_name}")
            response = self.session.put(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            logger.info(f"✅ Updated GitLab release: {tag_name}")
            return True

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                f"HTTP error updating release: {e.response.status_code} - {error_detail}"
            )
            raise GitLabAPIError(
                f"Failed to update release: {e}",
                status_code=e.response.status_code,
                response_data=e.response.json() if e.response else None,
            )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout updating release: {e}")
            raise GitLabAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error updating release: {e}")
            raise GitLabAPIError(f"Network error: {e}")

    def get_release(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get release information.

        Args:
            tag_name: Git tag name

        Returns:
            Release data dictionary or None if not found

        Raises:
            GitLabAPIError: If request fails (except 404)
        """
        url = f"{self.api_url}/projects/{self.project_id}/releases/{tag_name}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.debug(f"Release not found: {tag_name}")
                return None
            logger.error(f"HTTP error getting release: {e}")
            raise GitLabAPIError(
                f"Failed to get release: {e}", status_code=e.response.status_code
            )

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout getting release: {e}")
            raise GitLabAPIError(f"Request timeout: {e}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting release: {e}")
            raise GitLabAPIError(f"Network error: {e}")

    def release_exists(self, tag_name: str) -> bool:
        """
        Check if a release exists.

        Args:
            tag_name: Git tag name

        Returns:
            True if release exists, False otherwise
        """
        try:
            return self.get_release(tag_name) is not None
        except GitLabAPIError:
            return False

    def close(self) -> None:
        """Close the session and release resources."""
        if self.session:
            self.session.close()
            logger.debug("GitLab API session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
