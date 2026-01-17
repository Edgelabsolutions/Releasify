"""
Git command wrapper for release workflow operations.

This module:
- Wraps git CLI calls for tags, branches, and commits
- Provides CI-aware branch detection helpers
- Supports push configuration for authenticated CI releases
"""

import os
import logging
import subprocess
import re
from typing import List, Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)


class GitHelper:
    """Helper class for git operations."""

    def __init__(self, repo_path: str = '.'):
        """
        Initialize git helper.

        Args:
            repo_path: Path to git repository (default: current directory)
        """
        self.repo_path = repo_path

    def _run_git(self, *args, capture_output=True, check=True) -> subprocess.CompletedProcess:
        """
        Run a git command.

        Args:
            *args: Git command arguments
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit

        Returns:
            CompletedProcess instance
        """
        cmd = ['git', '-C', self.repo_path] + list(args)
        return subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=check
        )

    def get_current_branch(self) -> str:
        """
        Get the name of the current branch.

        In CI/CD environments (GitLab CI or GitHub Actions), uses environment variables
        to detect the branch name since the repository may be in detached HEAD state.

        For merge/pull request pipelines, returns the TARGET branch (where code will be merged to)
        since that determines the type of release (stable vs prerelease).
        """
        # Check GitHub Actions environment first
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            return self._get_github_branch()

        # Try GitLab CI environment variables
        # In merge requests, use the TARGET branch (where we're merging TO)
        # This ensures we create the right version type (stable for main, prerelease for dev)
        branch = os.environ.get('CI_MERGE_REQUEST_TARGET_BRANCH_NAME')
        if branch:
            return branch

        # For regular pipelines, use CI_COMMIT_BRANCH
        branch = os.environ.get('CI_COMMIT_BRANCH')
        if branch:
            return branch

        # Fallback to git command for local development
        result = self._run_git('rev-parse', '--abbrev-ref', 'HEAD')
        branch = result.stdout.strip()

        # If still HEAD (detached state), try CI_COMMIT_REF_NAME as last resort
        if branch == 'HEAD':
            branch = os.environ.get('CI_COMMIT_REF_NAME', 'HEAD')

        return branch

    def _get_github_branch(self) -> str:
        """
        Get branch name in GitHub Actions environment.

        Returns:
            Branch name
        """
        event_name = os.environ.get('GITHUB_EVENT_NAME', '')

        # For pull requests, use base branch (where code merges TO)
        if event_name == 'pull_request':
            branch = os.environ.get('GITHUB_BASE_REF')
            if branch:
                return branch

        # For push events and others, use GITHUB_REF_NAME
        branch = os.environ.get('GITHUB_REF_NAME')
        if branch:
            return branch

        # Fallback: parse from GITHUB_REF (refs/heads/main)
        ref = os.environ.get('GITHUB_REF', '')
        if ref.startswith('refs/heads/'):
            return ref.replace('refs/heads/', '')
        if ref.startswith('refs/tags/'):
            return ref.replace('refs/tags/', '')

        return ref or 'HEAD'

    def get_latest_tag(self, pattern: Optional[str] = None) -> Optional[str]:
        """
        Get the most recent tag by version sorting.

        Args:
            pattern: Optional glob pattern to filter tags

        Returns:
            Tag name or None if no tags exist
        """
        try:
            # Fetch all tags from remote (CI often does shallow clone without tags)
            try:
                self._run_git('fetch', '--tags', check=False)
            except (subprocess.CalledProcessError, OSError):
                # Continue even if fetch fails (might be offline or no remote)
                pass

            # Use git tag with version sorting to get the highest version tag
            cmd_args = ['tag', '-l', '--sort=-version:refname']
            if pattern:
                cmd_args.append(pattern)

            result = self._run_git(*cmd_args)
            tags = [t for t in result.stdout.strip().split('\n') if t]

            # Return the first tag (highest version)
            if tags:
                return tags[0]
            return None
        except subprocess.CalledProcessError:
            return None

    def get_tags_matching(self, pattern: str) -> List[str]:
        """
        Get all tags matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., 'v1.2.3-*')

        Returns:
            List of matching tag names
        """
        try:
            result = self._run_git('tag', '-l', pattern)
            tags = result.stdout.strip().split('\n')
            return [t for t in tags if t]  # Filter empty strings
        except subprocess.CalledProcessError:
            return []

    def get_commits_since_tag(self, tag: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get commits since a specific tag.

        Args:
            tag: Tag name (if None, gets all commits)

        Returns:
            List of (sha, message) tuples
        """
        if tag:
            rev_range = f'{tag}..HEAD'
        else:
            rev_range = 'HEAD'

        try:
            # Format: <sha>|||<subject>\n<body>\n---END---
            result = self._run_git(
                'log',
                rev_range,
                '--format=%H|||%s%n%b---END---',
                '--no-merges'
            )

            commits = []
            raw_commits = result.stdout.split('---END---\n')

            for raw in raw_commits:
                raw = raw.strip()
                if not raw:
                    continue

                parts = raw.split('|||', 1)
                if len(parts) == 2:
                    sha = parts[0].strip()
                    message = parts[1].strip()
                    commits.append((sha, message))

            return commits

        except subprocess.CalledProcessError:
            return []

    def create_tag(self, tag: str, message: str, sha: str = 'HEAD') -> bool:
        """
        Create an annotated git tag.

        Args:
            tag: Tag name
            message: Tag annotation message
            sha: Commit SHA (default: HEAD)

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_git('tag', '-a', tag, '-m', message, sha)
            logger.info(f"Created git tag: {tag}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating tag {tag}: {e}")
            return False

    def configure_push_url(self, token: str = None, platform: str = None) -> bool:
        """
        Configure git remote URL with authentication token for pushing.

        Supports both GitLab and GitHub authentication formats.

        Args:
            token: API token (auto-detected from environment if not provided)
            platform: Platform name ('gitlab' or 'github', auto-detected if not provided)

        Returns:
            True if successful, False otherwise
        """
        from src.config import Config
        from src.platform import detect_platform, Platform

        # Auto-detect platform if not provided
        if platform is None:
            detected = detect_platform()
            platform = detected.value

        # Get appropriate token based on platform
        if not token:
            if platform == 'github':
                token = Config.get_github_token()
            else:
                token = Config.get_gitlab_token()

        if not token:
            logger.warning(f"No token available for {platform} authentication")
            return False

        try:
            # Get current remote URL
            result = self._run_git('remote', 'get-url', 'origin')
            current_url = result.stdout.strip()

            # If it's already using token auth, skip
            if '@' in current_url and token[:8] in current_url:
                return True

            if platform == 'github':
                return self._configure_github_push_url(token, current_url)
            else:
                return self._configure_gitlab_push_url(token, current_url)

        except subprocess.CalledProcessError as e:
            logger.error(f"Error configuring git remote: {e}")
            return False

    def _configure_gitlab_push_url(self, token: str, current_url: str) -> bool:
        """Configure push URL for GitLab."""
        ci_server_url = os.environ.get('CI_SERVER_URL', 'https://gitlab.com')
        project_path = os.environ.get('CI_PROJECT_PATH')

        if not project_path:
            # Try to extract from current URL
            match = re.search(r'([^/:]+/[^/:]+?)(?:\.git)?$', current_url)
            if match:
                project_path = match.group(1)
            else:
                logger.warning("Could not determine project path from remote URL")
                return False

        # Construct authenticated URL for GitLab
        auth_url = f"{ci_server_url.replace('://', f'://gitlab-ci-token:{token}@')}/{project_path}.git"

        # Set the push URL (keeps fetch URL unchanged)
        self._run_git('remote', 'set-url', '--push', 'origin', auth_url)
        logger.debug("Configured GitLab push URL with authentication")
        return True

    def _configure_github_push_url(self, token: str, current_url: str) -> bool:
        """Configure push URL for GitHub."""
        server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
        repo = os.environ.get('GITHUB_REPOSITORY')

        if not repo:
            # Try to extract from current URL
            if 'github.com' in current_url:
                if current_url.startswith('git@github.com:'):
                    repo = current_url.replace('git@github.com:', '').rstrip('.git')
                else:
                    match = re.search(r'github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$', current_url)
                    if match:
                        repo = match.group(1)

        if not repo:
            logger.warning("Could not determine repository from remote URL")
            return False

        # Construct authenticated URL for GitHub
        # GitHub accepts x-access-token as username with the token as password
        auth_url = f"{server_url.replace('://', f'://x-access-token:{token}@')}/{repo}.git"

        # Set the push URL (keeps fetch URL unchanged)
        self._run_git('remote', 'set-url', '--push', 'origin', auth_url)
        logger.debug("Configured GitHub push URL with authentication")
        return True

    def push_tag(self, tag: str) -> bool:
        """
        Push a tag to remote.

        Args:
            tag: Tag name

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_git('push', 'origin', tag)
            logger.info(f"Pushed tag to remote: {tag}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error pushing tag {tag}: {e}")
            return False

    def push_branch(self, branch: str = None) -> bool:
        """
        Push current branch or specified branch to remote.

        Args:
            branch: Branch name (if None, uses current branch)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not branch:
                # Get the actual branch name instead of using HEAD
                branch = self.get_current_branch()

            # Push using HEAD:branch format to handle detached HEAD state
            self._run_git('push', 'origin', f'HEAD:{branch}')
            logger.info(f"Pushed branch to remote: {branch}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error pushing branch {branch}: {e}")
            return False

    def commit_files(self, files: List[str], message: str) -> bool:
        """
        Stage and commit files.

        Args:
            files: List of file paths to commit
            message: Commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_git('add', *files)
            self._run_git('commit', '-m', message)
            logger.info(f"Committed {len(files)} file(s): {message}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error committing files: {e}")
            return False

    def has_changes(self, file_path: str) -> bool:
        """
        Check if a file has uncommitted changes.

        Args:
            file_path: Path to file

        Returns:
            True if file has changes, False otherwise
        """
        try:
            result = self._run_git('diff', '--quiet', file_path, check=False)
            return result.returncode != 0
        except subprocess.CalledProcessError:
            return False

    def get_commit_count(self) -> int:
        """Get total number of commits in the repository."""
        try:
            result = self._run_git('rev-list', '--count', 'HEAD')
            return int(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0

    def get_short_sha(self, sha: str = 'HEAD', length: int = 7) -> str:
        """
        Get short version of a commit SHA.

        Args:
            sha: Commit SHA (default: HEAD)
            length: Length of short SHA

        Returns:
            Short SHA string
        """
        try:
            result = self._run_git('rev-parse', '--short=' + str(length), sha)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return sha[:length]
