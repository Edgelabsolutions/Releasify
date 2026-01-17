#!/usr/bin/env python3
"""
Releasify - Semantic versioning and release automation for GitLab and GitHub.

Author: Oleh Hordon
Company: Edge Solutions Lab
License: MIT
Repository: https://github.com/Edgelabsolutions/releasify

This script wires together configuration, parsing, version calculation,
changelog updates, git operations, and platform API calls. It exposes three
CLI actions:
- generate-version: calculate the next version without creating a release
- release: perform the full release workflow
- validate: validate commit messages against conventional rules

Supports both GitLab and GitHub platforms with automatic detection.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.commit_parser import ConventionalCommitParser
from src.version_calc import VersionCalculator, Version
from src.git_helper import GitHelper
from src.changelog import ChangelogGenerator
from src.gitlab_api import GitLabAPI, GitLabAPIError
from src.github_api import GitHubAPI, GitHubAPIError
from src.platform import Platform, detect_platform, get_project_url
from src.commit_validator import validate_commit_message
from src.slack_notifier import SlackNotifier, SlackConfig


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"


class ReleaseOrchestrator:
    """Main release orchestrator for GitLab and GitHub."""

    def __init__(
        self, config_path: str = None, dry_run: bool = False, platform: str = None
    ):
        """
        Initialize release orchestrator.

        Args:
            config_path: Path to config file (optional)
            dry_run: If True, don't create tags or releases
            platform: Platform to use ('gitlab', 'github', or 'auto')
        """
        self.dry_run = dry_run
        self.config = Config(config_path)
        self.git = GitHelper()
        self.parser = ConventionalCommitParser(self.config)
        self.version_calc = VersionCalculator(self.config, self.git)

        # Detect platform (CLI arg > config file > auto-detect)
        platform_setting = platform or self.config.platform
        self.platform = detect_platform(platform_setting)
        print(f"Platform: {Colors.CYAN}{self.platform.value}{Colors.RESET}")

        # Initialize changelog with platform awareness
        self.changelog = ChangelogGenerator(self.config, self.platform)

        # Initialize platform API client (only if not dry run)
        self.release_api = None
        if not dry_run:
            self._init_release_api()

        # Slack notifier (configured from config.yaml and environment variables)
        slack_cfg = self.config.slack_config
        self.slack = SlackNotifier(
            SlackConfig(
                enabled=slack_cfg.get("enabled", False),
                token=slack_cfg.get("token"),
                channel=slack_cfg.get("channel"),
            ),
            platform=self.platform,
        )
        self.notify_success = slack_cfg.get("notify_success", True)
        self.notify_failure = slack_cfg.get("notify_failure", True)

    def _init_release_api(self):
        """Initialize the appropriate release API client based on platform."""
        logger = logging.getLogger(__name__)

        if self.platform == Platform.GITHUB:
            try:
                self.release_api = GitHubAPI()
                logger.info("GitHub API initialized")
            except GitHubAPIError as e:
                logger.warning(f"GitHub API initialization failed: {e}")
                logger.warning("GitHub releases will not be created")
        else:
            try:
                self.release_api = GitLabAPI()
                logger.info("GitLab API initialized")
            except (ValueError, GitLabAPIError) as e:
                logger.warning(f"GitLab API initialization failed: {e}")
                logger.warning("GitLab releases will not be created")

    def generate_version(self) -> dict:
        """
        Generate next version without creating release.

        Returns:
            Dictionary with version information
        """
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(
            f"{Colors.CYAN}Analyzing commits for version calculation...{Colors.RESET}"
        )
        print(f"{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

        # Get current branch
        branch = self.git.get_current_branch()
        print(f"Current branch: {Colors.GREEN}{branch}{Colors.RESET}")

        # Get branch configuration
        branch_config = self.config.get_branch_config(branch)
        if not branch_config:
            print(
                f"{Colors.RED}❌ No configuration found for branch '{branch}'{Colors.RESET}"
            )
            return {"error": f"No configuration for branch {branch}"}

        print(f"Branch type: {Colors.GREEN}{branch_config.type}{Colors.RESET}")
        if branch_config.prerelease:
            print(
                f"Prerelease identifier: {Colors.YELLOW}{branch_config.prerelease}{Colors.RESET}"
            )

        # Get current version (stable only for release branches)
        is_stable_branch = branch_config.prerelease is None
        current_version = self.version_calc.get_current_version(
            stable_only=is_stable_branch
        )
        if current_version:
            print(f"Current version: {Colors.GREEN}{current_version}{Colors.RESET}")
        else:
            print(f"Current version: {Colors.YELLOW}None (first release){Colors.RESET}")

        # Get commits since last tag (use latest stable tag for stable branches)
        if is_stable_branch and current_version:
            latest_tag = self.version_calc.format_tag(current_version)
        elif is_stable_branch:
            latest_tag = None  # No stable releases yet, get all commits
        else:
            latest_tag = self.git.get_latest_tag()
        commits_data = self.git.get_commits_since_tag(latest_tag)

        print(
            f"Commits since last release: {Colors.CYAN}{len(commits_data)}{Colors.RESET}"
        )

        if not commits_data:
            print(f"\n{Colors.YELLOW}⚠️  No new commits found{Colors.RESET}")
            return {
                "next_version": str(current_version) if current_version else "0.0.0",
                "last_version": str(current_version) if current_version else "0.0.0",
                "no_release": True,
            }

        # Parse commits
        parsed_commits = self.parser.parse_commits(commits_data)
        print(
            f"Conventional commits found: {Colors.CYAN}{len(parsed_commits)}{Colors.RESET}\n"
        )

        # Display commit summary
        if parsed_commits:
            self._display_commit_summary(parsed_commits)

        # Determine version bump
        max_bump = self.parser.get_max_bump(parsed_commits)
        print(
            f"\nVersion bump required: {Colors.MAGENTA}{max_bump.value}{Colors.RESET}"
        )

        # Calculate next version
        next_version = self.version_calc.calculate_next_version(
            parsed_commits, current_version, branch, max_bump
        )

        if not next_version:
            return {
                "next_version": str(current_version) if current_version else "0.0.0",
                "last_version": str(current_version) if current_version else "0.0.0",
                "no_release": True,
            }

        print(f"Next version: {Colors.GREEN}{next_version}{Colors.RESET}\n")

        # Print summary box
        self._print_version_summary(current_version, next_version, branch, max_bump)

        return {
            "next_version": str(next_version),
            "last_version": str(current_version) if current_version else "0.0.0",
            "branch": branch,
            "commits": len(parsed_commits),
        }

    def create_release(self) -> dict:
        """
        Create a full release (tag, changelog, platform release).

        Returns:
            Dictionary with release information
        """
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}Creating release...{Colors.RESET}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

        # First, generate version info
        version_info = self.generate_version()

        # Get platform-aware project URL
        project_url = get_project_url(self.platform)

        if "error" in version_info:
            # Send Slack failure notification
            if self.notify_failure:
                branch = self.git.get_current_branch()
                self.slack.notify_failure(
                    error_message=version_info["error"],
                    branch=branch,
                    project_url=project_url,
                )
            return {"status": "failed", "error": version_info["error"]}

        if version_info.get("no_release"):
            print(f"\n{Colors.YELLOW}⚠️  No release needed{Colors.RESET}")
            return {"status": "skipped", "reason": "No commits requiring release"}

        next_version = Version.parse(version_info["next_version"])
        tag_name = self.version_calc.format_tag(next_version)

        # Get branch configuration
        branch = self.git.get_current_branch()
        branch_config = self.config.get_branch_config(branch)
        is_stable_branch = branch_config and branch_config.prerelease is None

        # Get commits for changelog (use stable tags only for stable branches)
        if is_stable_branch:
            stable_version = self.version_calc.get_current_version(stable_only=True)
            if stable_version:
                latest_tag = self.version_calc.format_tag(stable_version)
            else:
                latest_tag = None  # No stable releases yet, get all commits
        else:
            latest_tag = self.git.get_latest_tag()

        commits_data = self.git.get_commits_since_tag(latest_tag)
        parsed_commits = self.parser.parse_commits(commits_data)

        # Update CHANGELOG.md (only for stable releases)
        changelog_updated = False
        if is_stable_branch:
            print(f"{Colors.CYAN}📝 Updating CHANGELOG.md...{Colors.RESET}")
            if self.changelog.update(next_version, parsed_commits):
                print(f"{Colors.GREEN}✅ CHANGELOG.md updated{Colors.RESET}")
                changelog_updated = True
            else:
                print(f"{Colors.RED}Failed to update CHANGELOG.md{Colors.RESET}")
                # Send Slack failure notification
                if self.notify_failure:
                    self.slack.notify_failure(
                        error_message="Failed to update CHANGELOG.md",
                        branch=branch,
                        attempted_version=str(next_version),
                        project_url=project_url,
                    )
                return {"status": "failed", "error": "Changelog update failed"}
        else:
            print(
                f"{Colors.YELLOW}⏭️  Skipping CHANGELOG.md update (prerelease){Colors.RESET}"
            )

        if self.dry_run:
            print(
                f"\n{Colors.YELLOW}🔍 DRY RUN - No tags or releases will be created{Colors.RESET}"
            )
            self._print_release_summary(next_version, tag_name, "dry-run")
            return {"status": "dry-run", "version": str(next_version), "tag": tag_name}

        # Configure git authentication for pushing
        print(f"{Colors.CYAN}🔐 Configuring git authentication...{Colors.RESET}")
        if self.git.configure_push_url():
            print(f"{Colors.GREEN}✅ Git authentication configured{Colors.RESET}")
        else:
            print(
                f"{Colors.YELLOW}⚠️  Could not configure git authentication{Colors.RESET}"
            )

        # Commit CHANGELOG.md (only if it was updated for stable releases)
        if changelog_updated:
            print(f"{Colors.CYAN}📦 Committing CHANGELOG.md...{Colors.RESET}")
            commit_msg = f"chore(release): {next_version}"
            if self.git.commit_files([self.config.changelog_file], commit_msg):
                print(f"{Colors.GREEN}✅ CHANGELOG.md committed{Colors.RESET}")

                # Push CHANGELOG.md commit to branch
                print(
                    f"{Colors.CYAN}📤 Pushing CHANGELOG.md to remote branch...{Colors.RESET}"
                )
                if self.git.push_branch():
                    print(
                        f"{Colors.GREEN}✅ CHANGELOG.md pushed to remote{Colors.RESET}"
                    )
                else:
                    print(
                        f"{Colors.YELLOW}⚠️  Could not push CHANGELOG.md (committed locally){Colors.RESET}"
                    )
            else:
                print(f"{Colors.YELLOW}⚠️  Could not commit CHANGELOG.md{Colors.RESET}")

        # Create git tag
        print(f"{Colors.CYAN}🏷️  Creating git tag: {tag_name}...{Colors.RESET}")
        tag_message = f"Release {next_version}"
        if self.git.create_tag(tag_name, tag_message):
            print(f"{Colors.GREEN}✅ Git tag created{Colors.RESET}")
        else:
            print(f"{Colors.RED}Failed to create git tag{Colors.RESET}")
            # Send Slack failure notification
            if self.notify_failure:
                self.slack.notify_failure(
                    error_message="Failed to create git tag",
                    branch=branch,
                    attempted_version=str(next_version),
                    project_url=project_url,
                )
            return {"status": "failed", "error": "Tag creation failed"}

        # Push tag to remote
        print(f"{Colors.CYAN}📤 Pushing git tag to remote...{Colors.RESET}")
        if self.git.push_tag(tag_name):
            print(f"{Colors.GREEN}✅ Git tag pushed to remote{Colors.RESET}")
        else:
            print(
                f"{Colors.YELLOW}⚠️  Failed to push tag (tag created locally){Colors.RESET}"
            )

        # Create platform release (GitLab or GitHub)
        if self.release_api:
            platform_name = self.platform.value.capitalize()
            print(f"{Colors.CYAN}Creating {platform_name} release...{Colors.RESET}")

            # For stable releases, use changelog entry; for prereleases, generate simple description
            if is_stable_branch:
                release_description = self.changelog.get_entry_for_version(next_version)
            else:
                # Generate simple description for prerelease
                release_description = f"Prerelease {next_version}\n\nThis is a prerelease version for testing."

            current_branch = self.git.get_current_branch()
            is_prerelease = not is_stable_branch

            try:
                if self.platform == Platform.GITHUB:
                    success = self.release_api.create_release(
                        next_version,
                        tag_name,
                        release_description,
                        ref=current_branch,
                        prerelease=is_prerelease,
                    )
                else:
                    success = self.release_api.create_release(
                        next_version, tag_name, release_description, ref=current_branch
                    )

                if success:
                    print(
                        f"{Colors.GREEN}{platform_name} release created{Colors.RESET}"
                    )
            except (GitLabAPIError, GitHubAPIError) as e:
                logger = logging.getLogger(__name__)
                logger.error(f"{platform_name} release creation failed: {e}")
                print(
                    f"{Colors.YELLOW}{platform_name} release creation failed (tag still created){Colors.RESET}"
                )

        # Print summary
        self._print_release_summary(next_version, tag_name, "success")

        # Send Slack success notification
        if self.notify_success:
            changelog_entry = None
            if is_stable_branch:
                changelog_entry = self.changelog.get_entry_for_version(next_version)

            self.slack.notify_success(
                version=str(next_version),
                tag=tag_name,
                branch=branch,
                project_url=project_url,
                changelog_entry=changelog_entry,
            )

        return {"status": "success", "version": str(next_version), "tag": tag_name}

    def _display_commit_summary(self, commits):
        """Display summary of parsed commits."""
        from collections import Counter

        type_counts = Counter(c.formatted_type for c in commits)

        print(f"{Colors.CYAN}Commit breakdown:{Colors.RESET}")
        for commit_type, count in type_counts.most_common():
            print(f"  {commit_type}: {count}")

    def _print_version_summary(self, current, next_ver, branch, bump):
        """Print formatted version summary box."""
        width = 60
        bar = "─" * width

        print(f"{Colors.GREEN}┌{bar}┐{Colors.RESET}")
        print(f"{Colors.GREEN}│{Colors.RESET} 🧮 Version Summary")
        print(f"{Colors.GREEN}├{bar}┤{Colors.RESET}")
        print(f" Current version    : {current or 'None'}")
        print(f" Next version       : {Colors.GREEN}{next_ver}{Colors.RESET}")
        print(f" Branch             : {branch}")
        print(f" Bump type          : {bump.value}")
        print(f"{Colors.GREEN}└{bar}┘{Colors.RESET}")

    def _print_release_summary(self, version, tag, status):
        """Print formatted release summary box."""
        width = 60
        bar = "─" * width

        print(f"\n{Colors.GREEN}┌{bar}┐{Colors.RESET}")
        print(f"{Colors.GREEN}│{Colors.RESET} 🏁 Release Summary")
        print(f"{Colors.GREEN}├{bar}┤{Colors.RESET}")
        print(f" Version            : {version}")
        print(f" Tag                : {tag}")
        print(f" Status             : {status}")
        print(f"{Colors.GREEN}└{bar}┘{Colors.RESET}\n")


def validate_message(
    config_path: str = None, message: str = None, message_file: str = None
):
    """
    Validate a commit message.

    Args:
        config_path: Path to config file
        message: Commit message text
        message_file: Path to file containing commit message
    """
    # Load config
    config = Config(config_path)

    # Get message
    if message_file:
        with open(message_file, "r") as f:
            message = f.read()
    elif not message:
        print(
            f"{Colors.RED}❌ No message provided. Use --message or --message-file{Colors.RESET}"
        )
        sys.exit(1)

    # Validate
    is_valid, formatted = validate_commit_message(message, config)

    # Print results
    print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.CYAN}📝 Commit Message Validation{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")

    print(f"{Colors.YELLOW}Message:{Colors.RESET}")
    print(message)
    print()

    print(formatted)
    print()

    # Exit with appropriate code (formatted already contains success/failure message)
    sys.exit(0 if is_valid else 1)


def main():
    """Main entry point."""
    # Configure logging before any other operations
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),  # Console output
        ],
    )

    # Optionally add file handler if LOG_FILE environment variable is set
    if log_file := os.getenv("LOG_FILE"):
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)

    parser = argparse.ArgumentParser(
        description="Release automation for GitLab and GitHub projects"
    )

    parser.add_argument(
        "action",
        choices=["generate-version", "release", "validate"],
        help="Action to perform: generate-version (calculate only), release (create full release), or validate (check commit message)",
    )

    parser.add_argument(
        "--config",
        help="Path to configuration file (default: config.yaml in repo root)",
        default=None,
    )

    parser.add_argument(
        "--platform",
        choices=["auto", "gitlab", "github"],
        help="Platform to use (default: auto-detect)",
        default=None,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without creating tags or releases",
    )

    parser.add_argument(
        "--output", help="Output file for version info (dotenv format)", default=None
    )

    parser.add_argument(
        "--message",
        help="Commit message to validate (for validate action)",
        default=None,
    )

    parser.add_argument(
        "--message-file",
        help="File containing commit message to validate (for validate action)",
        default=None,
    )

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = ReleaseOrchestrator(
        config_path=args.config,
        dry_run=args.dry_run or (args.action == "generate-version"),
        platform=args.platform,
    )

    # Execute action
    if args.action == "validate":
        # Validate action doesn't need orchestrator
        validate_message(args.config, args.message, args.message_file)
        return  # validate_message exits
    elif args.action == "generate-version":
        result = orchestrator.generate_version()
    else:
        result = orchestrator.create_release()

    # Write output file if requested
    if args.output:
        with open(args.output, "w") as f:
            # For generate-version action
            if "next_version" in result:
                f.write(f"NEXT_RELEASE_VERSION={result['next_version']}\n")
                f.write(f"LAST_RELEASE_VERSION={result['last_version']}\n")
            # For release action
            elif "version" in result:
                f.write(f"RELEASE_VERSION={result['version']}\n")
                f.write(f"RELEASE_TAG={result.get('tag', result['version'])}\n")
                f.write(f"RELEASE_STATUS={result.get('status', 'unknown')}\n")

        print(f"\n{Colors.GREEN}✅ Version info written to {args.output}{Colors.RESET}")

    # Exit with appropriate code
    if result.get("status") == "failed":
        sys.exit(1)
    elif result.get("error"):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
