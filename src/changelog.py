"""
Generate and update CHANGELOG.md entries for releases.

This module:
- Groups commits by configured type buckets
- Renders markdown entries with platform-aware links (GitLab/GitHub)
- Inserts new entries at the top of the changelog file
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from src.commit_parser import ParsedCommit
from src.version_calc import Version
from src.platform import (
    Platform,
    detect_platform,
    get_project_url,
    get_compare_url,
    get_commit_url,
)

# Configure module logger
logger = logging.getLogger(__name__)


class ChangelogGenerator:
    """Generate and update CHANGELOG.md."""

    def __init__(self, config, platform: Platform = None):
        """
        Initialize changelog generator.

        Args:
            config: Config instance
            platform: Platform enum (auto-detected if not provided)
        """
        self.config = config
        self.file_path = config.changelog_file
        self.platform = platform or detect_platform(config.platform)

    def update(
        self, version: Version, commits: List[ParsedCommit], date: datetime = None
    ) -> bool:
        """
        Update CHANGELOG.md with new version information.

        Args:
            version: New version
            commits: List of commits to include
            date: Release date (default: now)

        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = datetime.now()

        # Group commits by type
        grouped = self._group_commits(commits)

        # Generate new entry
        new_entry = self._generate_entry(version, grouped, date)

        # Update or create changelog file
        try:
            if os.path.exists(self.file_path):
                self._insert_entry(new_entry)
            else:
                self._create_changelog(new_entry)
            return True
        except Exception as e:
            logger.error(f"Error updating changelog: {e}")
            return False

    def _group_commits(
        self, commits: List[ParsedCommit]
    ) -> Dict[str, List[ParsedCommit]]:
        """
        Group commits by type.

        Args:
            commits: List of commits

        Returns:
            Dictionary mapping commit type to list of commits
        """
        grouped = {}
        include_types = set(self.config.changelog_types)

        for commit in commits:
            # Special handling for breaking changes
            if commit.breaking:
                commit_type = "breaking"
            else:
                commit_type = commit.type
                type_config = self.config.get_commit_type(commit_type)
                if type_config and type_config.name != commit_type:
                    commit_type = type_config.name

            # Only include configured types
            if commit_type not in include_types:
                continue

            if commit_type not in grouped:
                grouped[commit_type] = []

            grouped[commit_type].append(commit)

        return grouped

    def _generate_entry(
        self,
        version: Version,
        grouped_commits: Dict[str, List[ParsedCommit]],
        date: datetime,
    ) -> str:
        """
        Generate changelog entry for a version.

        Args:
            version: Version object
            grouped_commits: Commits grouped by type
            date: Release date

        Returns:
            Formatted changelog entry
        """
        lines = []

        # Get project URL (platform-aware)
        project_url = get_project_url(self.platform)

        # Build compare link for version header
        date_str = date.strftime("%Y-%m-%d")
        if project_url:
            # Get previous version for compare link
            prev_version = self._get_previous_version(version)
            if prev_version:
                compare_link = get_compare_url(
                    self.platform, project_url, prev_version, str(version)
                )
                lines.append(f"# [{version}]({compare_link}) ({date_str})")
            else:
                lines.append(f"# [{version}] ({date_str})")
        else:
            lines.append(f"# [{version}] ({date_str})")

        lines.append("")

        # Type headers (in priority order)
        type_order = ["breaking", "feat", "fix", "perf", "revert"]
        type_labels = {
            "breaking": "BREAKING CHANGES",
            "feat": "Features",
            "fix": "Bug Fixes",
            "perf": "Performance Improvements",
            "revert": "Reverts",
        }

        for commit_type in type_order:
            if commit_type not in grouped_commits:
                continue

            commits = grouped_commits[commit_type]
            label = type_labels.get(commit_type, commit_type.capitalize())

            lines.append(f"### {label}")
            lines.append("")

            for commit in commits:
                # Format: * message ([sha](link))
                short_sha = commit.sha[:7] if len(commit.sha) >= 7 else commit.sha

                if project_url:
                    commit_link = get_commit_url(self.platform, project_url, commit.sha)
                    sha_link = f"([{short_sha}]({commit_link}))"
                else:
                    sha_link = f"({short_sha})"

                # Include scope in message if present
                if commit.scope:
                    message = f"**{commit.scope}:** {commit.subject}"
                else:
                    message = commit.subject

                lines.append(f"* {message} {sha_link}")

            lines.append("")

        return "\n".join(lines)

    def _get_previous_version(self, current_version: Version) -> Optional[str]:
        """
        Get the previous version from CHANGELOG for compare links.

        Args:
            current_version: Current version being released

        Returns:
            Previous version string or None
        """
        if not os.path.exists(self.file_path):
            return None

        try:
            with open(self.file_path, "r") as f:
                content = f.read()

            # Find all version headers
            versions = re.findall(r"^#+ \[([^\]]+)\]", content, re.MULTILINE)

            if len(versions) >= 1:
                # Return the first version found (most recent before this one)
                return versions[0]

            return None
        except (FileNotFoundError, IOError, OSError):
            return None

    def _insert_entry(self, new_entry: str):
        """
        Insert new entry at the top of existing changelog.

        Args:
            new_entry: Formatted changelog entry
        """
        with open(self.file_path, "r") as f:
            content = f.read()

        # Find where to insert (after title and before first version)
        lines = content.split("\n")
        insert_pos = 0

        # Skip title and initial content
        for i, line in enumerate(lines):
            if line.startswith("# [") or line.startswith(
                "## ["
            ):  # First version header
                insert_pos = i
                break
        else:
            # No existing versions, append at end
            insert_pos = len(lines)

        # Insert new entry
        new_lines = lines[:insert_pos] + [new_entry] + lines[insert_pos:]

        with open(self.file_path, "w") as f:
            f.write("\n".join(new_lines))

    def _create_changelog(self, first_entry: str):
        """
        Create new CHANGELOG.md file.

        Args:
            first_entry: First changelog entry
        """
        content = [
            "# Changelog",
            "",
            "All notable changes to this project will be documented in this file.",
            "",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
            "",
            first_entry,
        ]

        with open(self.file_path, "w") as f:
            f.write("\n".join(content))

    def get_entry_for_version(self, version: Version) -> str:
        """
        Get the changelog entry for a specific version.

        Args:
            version: Version to get entry for

        Returns:
            Changelog entry text or empty string if not found
        """
        if not os.path.exists(self.file_path):
            return ""

        try:
            with open(self.file_path, "r") as f:
                content = f.read()

            # Find entry for this version
            version_str = str(version)
            # Match both old (##) and new (#) formats
            pattern = re.compile(f"^#+ \\[{re.escape(version_str)}\\]")

            lines = content.split("\n")
            entry_lines = []
            capturing = False

            for line in lines:
                if pattern.match(line):
                    capturing = True
                    entry_lines.append(line)
                elif capturing:
                    # Stop at next version header
                    if line.startswith("# [") or line.startswith("## ["):
                        break
                    entry_lines.append(line)

            return "\n".join(entry_lines).strip()

        except Exception as e:
            logger.error(f"Error reading changelog: {e}")
            return ""
