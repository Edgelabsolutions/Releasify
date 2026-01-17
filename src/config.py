"""
Configuration loader and accessors for release automation.

This module:
- Loads config.yaml with defaults
- Applies environment variable overrides
- Exposes structured accessors for branch and commit type settings
"""

import os
import logging
import yaml
from dataclasses import dataclass
from typing import List, Dict, Optional

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class BranchConfig:
    """Configuration for a branch pattern."""

    name: str
    type: str  # 'release' or 'prerelease'
    prerelease: Optional[str] = (
        None  # Prerelease identifier (e.g., 'dev', 'alpha', 'beta')
    )


@dataclass
class CommitTypeConfig:
    """Configuration for a commit type."""

    name: str
    bump: str  # 'major', 'minor', or 'patch'
    aliases: List[str] = None


class Config:
    """Main configuration class."""

    DEFAULT_CONFIG = {
        "platform": "auto",  # 'auto', 'gitlab', or 'github'
        "branches": [
            {"name": "main", "type": "release", "prerelease": None},
            {"name": "master", "type": "release", "prerelease": None},
            {"name": "dev", "type": "prerelease", "prerelease": "dev"},
            {"name": "develop", "type": "prerelease", "prerelease": "dev"},
        ],
        "commit_types": {
            "breaking": {
                "bump": "major",
                "keywords": ["BREAKING CHANGE", "BREAKING-CHANGE"],
            },
            "feat": {"bump": "minor", "aliases": ["feature"]},
            "fix": {"bump": "patch", "aliases": ["bugfix", "hotfix"]},
            "perf": {"bump": "patch", "aliases": []},
            "revert": {"bump": "patch", "aliases": []},
        },
        "tag_format": "${version}",
        "changelog": {
            "file": "CHANGELOG.md",
            "include_types": ["feat", "fix", "perf", "revert", "breaking"],
        },
        "slack": {
            "enabled": False,
            "token": None,
            "channel": None,
            "notify_success": True,
            "notify_failure": True,
        },
    }

    def __init__(self, config_path: Optional[str] = None, env_overrides: bool = True):
        """
        Initialize configuration.

        Args:
            config_path: Path to YAML config file (optional)
            env_overrides: Whether to allow environment variable overrides
        """
        # Start with defaults
        self.config = self.DEFAULT_CONFIG.copy()

        # Auto-discover config file if not provided
        if config_path is None:
            # Try standard locations
            candidate_paths = [
                "/app/config.yaml",  # Docker container location
                "config.yaml",  # Current directory
                "./config.yaml",  # Explicit current directory
            ]
            for path in candidate_paths:
                if os.path.exists(path):
                    config_path = path
                    break

        # Load from file if found
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        self._merge_config(user_config)
            except FileNotFoundError:
                raise ValueError(f"Configuration file not found: {config_path}")
            except yaml.YAMLError as e:
                raise ValueError(
                    f"Invalid YAML in configuration file {config_path}: {e}"
                )
            except (IOError, OSError) as e:
                raise ValueError(f"Error reading configuration file {config_path}: {e}")

        # Apply environment variable overrides
        if env_overrides:
            self._apply_env_overrides()

        # Parse into structured objects
        self.branches = [BranchConfig(**branch) for branch in self.config["branches"]]
        self.commit_types = {
            name: CommitTypeConfig(
                name=name, bump=cfg["bump"], aliases=cfg.get("aliases", [])
            )
            for name, cfg in self.config["commit_types"].items()
        }

    def _merge_config(self, user_config: dict):
        """Merge user configuration with defaults."""
        for key, value in user_config.items():
            if (
                key in self.config
                and isinstance(self.config[key], dict)
                and isinstance(value, dict)
            ):
                self.config[key].update(value)
            else:
                self.config[key] = value

    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        # Platform override
        if platform := os.getenv("RELEASE_PLATFORM"):
            self.config["platform"] = platform.lower()

        # Tag format override
        if tag_format := os.getenv("TAG_FORMAT"):
            self.config["tag_format"] = tag_format

        # Branches override (JSON string)
        if branches_json := os.getenv("RELEASE_BRANCHES"):
            import json

            try:
                self.config["branches"] = json.loads(branches_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in RELEASE_BRANCHES: {branches_json}")

        # Slack configuration overrides
        if slack_enabled := os.getenv("SLACK_ENABLED"):
            self.config["slack"]["enabled"] = slack_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

        if slack_token := os.getenv("SLACK_TOKEN"):
            self.config["slack"]["token"] = slack_token
            # Auto-enable if token is provided
            if not self.config["slack"]["enabled"]:
                self.config["slack"]["enabled"] = True

        if slack_channel := os.getenv("SLACK_CHANNEL"):
            self.config["slack"]["channel"] = slack_channel

    def get_branch_config(self, branch_name: str) -> Optional[BranchConfig]:
        """
        Get configuration for a specific branch.

        Supports glob patterns (e.g., 'alpha/*', 'feature/*').
        """
        import fnmatch

        for branch_cfg in self.branches:
            if fnmatch.fnmatch(branch_name, branch_cfg.name):
                return branch_cfg

        return None

    def get_commit_type(self, commit_type: str) -> Optional[CommitTypeConfig]:
        """Get commit type configuration, including aliases."""
        # Direct match
        if commit_type in self.commit_types:
            return self.commit_types[commit_type]

        # Check aliases
        for name, cfg in self.commit_types.items():
            if commit_type in cfg.aliases:
                return cfg

        return None

    @property
    def tag_format(self) -> str:
        """Get the tag format string."""
        return self.config["tag_format"]

    @property
    def changelog_file(self) -> str:
        """Get the changelog file path."""
        return self.config["changelog"]["file"]

    @property
    def changelog_types(self) -> List[str]:
        """Get commit types to include in changelog."""
        return self.config["changelog"]["include_types"]

    @property
    def slack_config(self) -> Dict:
        """Get Slack notification configuration."""
        return self.config.get(
            "slack",
            {
                "enabled": False,
                "token": None,
                "channel": None,
                "notify_success": True,
                "notify_failure": True,
            },
        )

    @property
    def platform(self) -> str:
        """
        Get the configured platform.

        Returns:
            Platform string: 'auto', 'gitlab', or 'github'
        """
        return self.config.get("platform", "auto")

    @staticmethod
    def get_gitlab_token(explicit_token: Optional[str] = None) -> Optional[str]:
        """
        Get GitLab token from environment variables with fallback chain.

        Priority:
        1. Explicitly provided token parameter
        2. GITLAB_TOKEN environment variable
        3. GL_TOKEN environment variable (legacy)

        Args:
            explicit_token: Optional token provided directly

        Returns:
            Token string or None if not found
        """
        return explicit_token or os.getenv("GITLAB_TOKEN") or os.getenv("GL_TOKEN")

    @staticmethod
    def get_github_token(explicit_token: Optional[str] = None) -> Optional[str]:
        """
        Get GitHub token from environment variables with fallback chain.

        Priority:
        1. Explicitly provided token parameter
        2. GITHUB_TOKEN environment variable
        3. GH_TOKEN environment variable (GitHub CLI convention)

        Args:
            explicit_token: Optional token provided directly

        Returns:
            Token string or None if not found
        """
        return explicit_token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
