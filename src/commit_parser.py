"""
Parse conventional commits and map them to version bumps.

This module:
- Parses conventional commit headers and bodies
- Detects breaking changes via headers or footers
- Maps commit types to bump levels using configuration
"""

import re
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class BumpType(Enum):
    """Version bump types."""
    MAJOR = 'major'
    MINOR = 'minor'
    PATCH = 'patch'
    NONE = 'none'


@dataclass
class ParsedCommit:
    """Represents a parsed conventional commit."""
    sha: str
    type: str
    scope: Optional[str]
    subject: str
    body: str
    breaking: bool
    bump: BumpType

    @property
    def formatted_type(self) -> str:
        """Get formatted commit type for display."""
        if self.breaking:
            return 'BREAKING CHANGE'
        return self.type


class ConventionalCommitParser:
    """Parser for conventional commits."""

    # Regex for conventional commit format: type(scope): subject
    COMMIT_PATTERN = re.compile(
        r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?\s*:\s*(?P<subject>.+)$',
        re.MULTILINE
    )

    # Breaking change indicators
    BREAKING_PATTERNS = [
        re.compile(r'BREAKING[- ]CHANGE:\s*(.+)', re.MULTILINE | re.IGNORECASE),
        re.compile(r'^(\w+)(?:\([^)]+\))?!:\s*(.+)$', re.MULTILINE),  # feat!: breaking change
    ]

    def __init__(self, config):
        """
        Initialize the parser with configuration.

        Args:
            config: Config instance with commit type rules
        """
        self.config = config

    def parse(self, commit_message: str, commit_sha: str = '') -> Optional[ParsedCommit]:
        """
        Parse a commit message.

        Args:
            commit_message: Full commit message
            commit_sha: Git commit SHA

        Returns:
            ParsedCommit if valid conventional commit, None otherwise
        """
        lines = commit_message.strip().split('\n')
        if not lines:
            return None

        # Parse header (first line)
        header = lines[0].strip()
        match = self.COMMIT_PATTERN.match(header)

        if not match:
            return None

        commit_type = match.group('type').lower()
        scope = match.group('scope')
        subject = match.group('subject').strip()

        # Get body (remaining lines)
        body = '\n'.join(lines[1:]).strip()

        # Check for breaking changes
        breaking = self._is_breaking(header, body)

        # Determine bump type
        bump = self._determine_bump(commit_type, breaking)

        return ParsedCommit(
            sha=commit_sha,
            type=commit_type,
            scope=scope,
            subject=subject,
            body=body,
            breaking=breaking,
            bump=bump
        )

    def _is_breaking(self, header: str, body: str) -> bool:
        """Check if commit contains breaking changes."""
        # Check for exclamation mark in header (feat!: ...)
        if '!' in header.split(':')[0]:
            return True

        # Check body for BREAKING CHANGE indicators
        for pattern in self.BREAKING_PATTERNS:
            if pattern.search(body):
                return True

        return False

    def _determine_bump(self, commit_type: str, breaking: bool) -> BumpType:
        """
        Determine version bump type based on commit type and breaking flag.

        Args:
            commit_type: Type of commit (feat, fix, etc.)
            breaking: Whether this is a breaking change

        Returns:
            BumpType enum value
        """
        if breaking:
            return BumpType.MAJOR

        # Get commit type configuration
        type_config = self.config.get_commit_type(commit_type)

        if not type_config:
            return BumpType.NONE

        bump_map = {
            'major': BumpType.MAJOR,
            'minor': BumpType.MINOR,
            'patch': BumpType.PATCH,
        }

        return bump_map.get(type_config.bump, BumpType.NONE)

    def parse_commits(self, commits: List[tuple]) -> List[ParsedCommit]:
        """
        Parse multiple commits.

        Args:
            commits: List of (sha, message) tuples

        Returns:
            List of ParsedCommit objects
        """
        parsed = []
        for sha, message in commits:
            commit = self.parse(message, sha)
            if commit:
                parsed.append(commit)

        return parsed

    def get_max_bump(self, commits: List[ParsedCommit]) -> BumpType:
        """
        Get the maximum version bump from a list of commits.

        Args:
            commits: List of ParsedCommit objects

        Returns:
            Maximum BumpType
        """
        bump_priority = {
            BumpType.MAJOR: 3,
            BumpType.MINOR: 2,
            BumpType.PATCH: 1,
            BumpType.NONE: 0,
        }

        max_bump = BumpType.NONE
        max_priority = 0

        for commit in commits:
            priority = bump_priority.get(commit.bump, 0)
            if priority > max_priority:
                max_priority = priority
                max_bump = commit.bump

        return max_bump
