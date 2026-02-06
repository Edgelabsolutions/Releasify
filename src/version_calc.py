"""
Semantic version calculation and prerelease management.

This module provides:
- Version class: Parses and formats semantic versions (major.minor.patch-prerelease+build)
- VersionCalculator: Calculates next version based on conditional commits
- Two prerelease modes: counter (1.2.3-dev.1, dev.2) and bump (1.1.0-dev, 1.2.0-dev)

Key Algorithm:
- Stable branches: Increment version based on commit types (major/minor/patch)
- Prerelease counter mode: Use latest stable as base, increment counter
- Prerelease bump mode: Each tag bumps from previous prerelease tag's base version
"""

import re
import logging
import subprocess
from typing import Optional, List
from dataclasses import dataclass
from src.commit_parser import BumpType, ParsedCommit

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class Version:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __str__(self) -> str:
        """Format as semantic version string."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """
        Parse a semantic version string.

        Args:
            version_str: Version string (e.g., "1.2.3", "1.2.3-alpha.1", "1.2.3-dev.4+build.123")

        Returns:
            Version object

        Raises:
            ValueError: If version string is invalid
        """
        # Remove 'v' prefix if present
        version_str = version_str.lstrip("v")

        # Pattern: major.minor.patch[-prerelease][+build]
        pattern = r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<prerelease>[0-9A-Za-z\-.]+))?(?:\+(?P<build>[0-9A-Za-z\-.]+))?$"
        match = re.match(pattern, version_str)

        if not match:
            raise ValueError(f"Invalid semantic version: {version_str}")

        try:
            return cls(
                major=int(match.group("major")),
                minor=int(match.group("minor")),
                patch=int(match.group("patch")),
                prerelease=match.group("prerelease"),
                build=match.group("build"),
            )
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid version format: {version_str}") from e

    def bump(self, bump_type: BumpType) -> "Version":
        """
        Create a new version with the specified bump.

        Args:
            bump_type: Type of version bump

        Returns:
            New Version object
        """
        if bump_type == BumpType.MAJOR:
            return Version(self.major + 1, 0, 0)
        elif bump_type == BumpType.MINOR:
            return Version(self.major, self.minor + 1, 0)
        elif bump_type == BumpType.PATCH:
            return Version(self.major, self.minor, self.patch + 1)
        else:
            return Version(self.major, self.minor, self.patch)

    def with_prerelease(
        self, prerelease: str, counter: Optional[int] = None
    ) -> "Version":
        """
        Create a new version with prerelease identifier.

        Args:
            prerelease: Prerelease identifier (e.g., 'dev', 'alpha', 'beta')
            counter: Prerelease counter. If None, no counter suffix (bump mode).

        Returns:
            New Version object with prerelease
        """
        if counter is not None:
            prerelease_str = f"{prerelease}.{counter}"
        else:
            prerelease_str = prerelease
        return Version(self.major, self.minor, self.patch, prerelease=prerelease_str)

    def base(self) -> "Version":
        """Return a copy without prerelease or build metadata."""
        return Version(self.major, self.minor, self.patch)

    def get_prerelease_identifier(self) -> Optional[str]:
        """
        Extract the prerelease identifier without counter.

        Examples:
            '1.2.3-dev.1' -> 'dev'
            '1.2.3-dev'   -> 'dev'
            '1.2.3'       -> None
        """
        if not self.prerelease:
            return None
        parts = self.prerelease.split(".")
        if parts[-1].isdigit() and len(parts) >= 2:
            return ".".join(parts[:-1])
        return self.prerelease

    def version_tuple(self) -> tuple:
        """Return (major, minor, patch) for comparison."""
        return (self.major, self.minor, self.patch)


class VersionCalculator:
    """Calculate next semantic version based on commits."""

    def __init__(self, config, git_helper):
        """
        Initialize version calculator.

        Args:
            config: Config instance
            git_helper: GitHelper instance
        """
        self.config = config
        self.git = git_helper

    def calculate_next_version(
        self,
        commits: List[ParsedCommit],
        current_version: Optional[Version],
        branch_name: str,
        max_bump: BumpType,
    ) -> Optional[Version]:
        """
        Calculate the next version based on commits and branch configuration.

        For prerelease branches:
        - Uses latest stable version from main as base
        - Calculates next base version
        - Checks for existing prereleases (X.Y.Z-beta.1, X.Y.Z-beta.2)
        - Increments prerelease counter or starts at .1

        Args:
            commits: List of parsed commits
            current_version: Current version (None if first release)
            branch_name: Current branch name
            max_bump: Maximum bump type from commits

        Returns:
            Next version or None if no release needed
        """
        # Get branch configuration
        branch_config = self.config.get_branch_config(branch_name)

        if not branch_config:
            logger.warning(f"No configuration for branch '{branch_name}'")
            return None

        # If no bump needed, return None
        if max_bump == BumpType.NONE:
            logger.info("No version bump needed (no relevant commits)")
            return None

        # Different logic for prerelease vs stable branches
        if branch_config.prerelease:
            return self._calculate_prerelease_version(commits, max_bump, branch_config)
        else:
            # For stable branches, check if prerelease tags exist (merge from bump-mode branch)
            prerelease_version = self._get_version_from_prerelease_tags()
            if prerelease_version:
                return prerelease_version

            # Standard stable calculation
            if current_version is None:
                base_version = Version(0, 0, 0)
            else:
                base_version = Version(
                    current_version.major, current_version.minor, current_version.patch
                )

            return base_version.bump(max_bump)

    def _calculate_prerelease_version(
        self, commits: List[ParsedCommit], max_bump: BumpType, branch_config
    ) -> Version:
        """
        Calculate prerelease version based on mode.

        Args:
            commits: List of parsed commits
            max_bump: Maximum bump type from commits
            branch_config: Branch configuration with prerelease settings

        Returns:
            Next prerelease version
        """
        prerelease_id = branch_config.prerelease
        mode = getattr(branch_config, "prerelease_mode", "counter")

        if mode == "bump":
            return self._calculate_bump_mode_version(max_bump, prerelease_id)
        else:
            return self._calculate_counter_mode_version(max_bump, prerelease_id)

    def _calculate_counter_mode_version(
        self, max_bump: BumpType, prerelease_id: str
    ) -> Version:
        """
        Calculate prerelease version using counter mode (X.Y.Z-id.N).

        Includes regression prevention: base version never goes below
        the highest existing prerelease tag's base.
        """
        stable_version = self._get_latest_stable_version()
        if stable_version is None:
            stable_version = Version(0, 0, 0)

        next_base_version = stable_version.bump(max_bump)

        # Prevent regression: ensure base is not lower than existing prerelease tags
        latest_prerelease = self._get_latest_prerelease_version(prerelease_id)
        if latest_prerelease:
            existing_base = latest_prerelease.base()
            if existing_base.version_tuple() > next_base_version.version_tuple():
                next_base_version = existing_base

        counter = self._get_prerelease_counter(next_base_version, prerelease_id, "")
        return next_base_version.with_prerelease(prerelease_id, counter)

    def _calculate_bump_mode_version(
        self, max_bump: BumpType, prerelease_id: str
    ) -> Version:
        """
        Calculate prerelease version using bump mode (X.Y.Z-id, no counter).

        Each tag bumps from the previous prerelease tag's base version.
        Example: 1.0.0 → feat → 1.1.0-dev → feat → 1.2.0-dev → fix → 1.2.1-dev
        """
        latest_prerelease = self._get_latest_prerelease_version(prerelease_id)

        if latest_prerelease is not None:
            base_version = latest_prerelease.base()
            next_version = base_version.bump(max_bump)
        else:
            stable_version = self._get_latest_stable_version()
            if stable_version is None:
                stable_version = Version(0, 0, 0)
            next_version = stable_version.bump(max_bump)

        return next_version.with_prerelease(prerelease_id)

    def _get_latest_stable_version(self) -> Optional[Version]:
        """
        Get the latest stable version (without prerelease identifier).

        Returns:
            Latest stable Version or None if no stable version exists
        """
        # Fetch tags to ensure we have the latest
        try:
            self.git._run_git("fetch", "--tags", check=False)
        except (subprocess.CalledProcessError, OSError):
            # Silently ignore fetch failures (might be offline or no remote)
            pass

        # Get all tags
        all_tags = self.git.get_tags_matching("*")

        stable_versions = []
        for tag in all_tags:
            try:
                version = Version.parse(tag)
                # Only include versions without prerelease
                if version.prerelease is None:
                    stable_versions.append(version)
            except ValueError:
                continue

        if not stable_versions:
            return None

        # Sort and return the highest stable version
        stable_versions.sort(key=lambda v: (v.major, v.minor, v.patch), reverse=True)
        return stable_versions[0]

    def _get_prerelease_counter(
        self, base_version: Version, prerelease_id: str, branch_name: str
    ) -> int:
        """
        Get the next prerelease counter for a version.

        Args:
            base_version: Base version (without prerelease)
            prerelease_id: Prerelease identifier (e.g., 'dev', 'alpha')
            branch_name: Current branch name

        Returns:
            Next prerelease counter (starting from 1)
        """
        # Get all tags that match the base version with this prerelease id
        pattern = f"{base_version}-{prerelease_id}.*"
        matching_tags = self.git.get_tags_matching(pattern)

        if not matching_tags:
            return 1

        # Extract counters from matching tags
        counters = []
        for tag in matching_tags:
            # Parse: 1.2.3-dev.4 -> 4
            try:
                version = Version.parse(tag)
                if version.prerelease:
                    parts = version.prerelease.split(".")
                    if len(parts) >= 2 and parts[0] == prerelease_id:
                        counters.append(int(parts[1]))
            except (ValueError, IndexError):
                continue

        # Return next counter
        if counters:
            return max(counters) + 1
        return 1

    def _get_latest_prerelease_version(self, prerelease_id: str) -> Optional[Version]:
        """
        Get the latest prerelease version matching the given identifier.

        Args:
            prerelease_id: Prerelease identifier (e.g., 'dev', 'alpha')

        Returns:
            Latest prerelease Version or None if none exist
        """
        all_tags = self.git.get_tags_matching("*")

        prerelease_versions = []
        for tag in all_tags:
            try:
                version = Version.parse(tag)
                if version.get_prerelease_identifier() == prerelease_id:
                    prerelease_versions.append(version)
            except ValueError:
                continue

        if not prerelease_versions:
            return None

        # Sort by version components, then by counter
        def sort_key(v):
            counter = 0
            if v.prerelease:
                parts = v.prerelease.split(".")
                if parts[-1].isdigit():
                    counter = int(parts[-1])
            return (v.major, v.minor, v.patch, counter)

        prerelease_versions.sort(key=sort_key, reverse=True)
        return prerelease_versions[0]

    def _get_version_from_prerelease_tags(self) -> Optional[Version]:
        """
        Check for prerelease tags between last stable and HEAD.

        Used by stable branches to adopt the version from a merged
        bump-mode prerelease branch (e.g., 1.2.1-dev → 1.2.1).

        Returns:
            Stripped prerelease version or None if not applicable
        """
        stable_version = self._get_latest_stable_version()
        all_tags = self.git.get_tags_matching("*")

        # Find prerelease tags higher than current stable
        prerelease_versions = []
        for tag in all_tags:
            try:
                version = Version.parse(tag)
                if version.prerelease is None:
                    continue
                # Only consider prerelease tags with base higher than stable
                if (
                    stable_version
                    and version.base().version_tuple() <= stable_version.version_tuple()
                ):
                    continue
                prerelease_versions.append(version)
            except ValueError:
                continue

        if not prerelease_versions:
            return None

        # Find the highest prerelease base version
        prerelease_versions.sort(key=lambda v: v.base().version_tuple(), reverse=True)
        highest = prerelease_versions[0].base()

        logger.info(
            f"Found prerelease tag {prerelease_versions[0]}, "
            f"using base version {highest} for stable release"
        )
        return highest

    def get_current_version(self, stable_only: bool = False) -> Optional[Version]:
        """
        Get the current version from git tags.

        Args:
            stable_only: If True, only return stable versions (no prerelease)

        Returns:
            Current Version or None if no version exists
        """
        if stable_only:
            return self._get_latest_stable_version()

        latest_tag = self.git.get_latest_tag()

        if not latest_tag:
            return None

        try:
            return Version.parse(latest_tag)
        except ValueError as e:
            logger.warning(f"Could not parse latest tag '{latest_tag}': {e}")
            return None

    def format_tag(self, version: Version) -> str:
        """
        Format version as git tag using configured tag format.

        Args:
            version: Version to format

        Returns:
            Formatted tag string
        """
        tag_format = self.config.tag_format
        return tag_format.replace("${version}", str(version))
