"""
Slack notification integration for release events.

This module provides:
- Success and failure notifications for releases
- Optional integration (no-op if not configured)
- Formatted messages with release details
- Platform-aware URLs (GitLab/GitHub)
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

from src.platform import Platform, detect_platform, get_tag_url, get_release_url, get_pipeline_url

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class SlackConfig:
    """Slack notification configuration."""
    enabled: bool
    token: Optional[str] = None
    channel: Optional[str] = None


class SlackNotifier:
    """Send Slack notifications for release events."""

    def __init__(self, config: SlackConfig, platform: Platform = None):
        """
        Initialize Slack notifier.

        Args:
            config: Slack configuration
            platform: Platform enum (auto-detected if not provided)
        """
        self.config = config
        self.client = None
        self.platform = platform or detect_platform()

        # Only initialize Slack client if properly configured
        if self.config.enabled and self.config.token and self.config.channel:
            try:
                from slack_sdk import WebClient
                from slack_sdk.errors import SlackApiError

                self.client = WebClient(token=self.config.token)
                self.SlackApiError = SlackApiError
            except ImportError:
                logger.warning("slack_sdk not installed. Install with: pip install slack-sdk")
                self.config.enabled = False
            except Exception as e:
                logger.warning(f"Failed to initialize Slack client: {e}")
                self.config.enabled = False

    def notify_success(
        self,
        version: str,
        tag: str,
        branch: str,
        project_url: Optional[str] = None,
        changelog_entry: Optional[str] = None
    ) -> bool:
        """
        Send success notification for a release.

        Args:
            version: Released version (e.g., "1.2.3")
            tag: Git tag created
            branch: Branch the release was created from
            project_url: GitLab project URL (optional)
            changelog_entry: Changelog text for this version (optional)

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self._is_enabled():
            return False

        # Build message blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Release Successful",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Version:*\n`{version}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Status:*\n:white_check_mark: Published"
                    }
                ]
            }
        ]

        # Add project link if available (platform-aware URLs)
        if project_url:
            tag_link = get_tag_url(self.platform, project_url, tag)
            release_link = get_release_url(self.platform, project_url, tag)

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{tag_link}|View Tag> • <{release_link}|View Release>"
                }
            })

        # Add changelog if available
        if changelog_entry:
            # Truncate if too long (Slack has limits)
            changelog_text = changelog_entry[:2000]
            if len(changelog_entry) > 2000:
                changelog_text += "\n... (truncated)"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Changes:*\n```{changelog_text}```"
                }
            })

        return self._send_message(blocks=blocks)

    def notify_failure(
        self,
        error_message: str,
        branch: str,
        attempted_version: Optional[str] = None,
        project_url: Optional[str] = None
    ) -> bool:
        """
        Send failure notification for a release.

        Args:
            error_message: Error description
            branch: Branch where release was attempted
            attempted_version: Version that was being released (if known)
            project_url: GitLab project URL (optional)

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self._is_enabled():
            return False

        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "❌ Release Failed",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Status:*\n:x: Failed"
                    }
                ]
            }
        ]

        # Add version if known
        if attempted_version:
            blocks[1]["fields"].insert(0, {
                "type": "mrkdwn",
                "text": f"*Attempted Version:*\n`{attempted_version}`"
            })

        # Add error details
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error:*\n```{error_message}```"
            }
        })

        # Add pipeline link if available (platform-aware)
        if project_url:
            pipeline_link = get_pipeline_url(self.platform)
            if pipeline_link:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{pipeline_link}|View Pipeline>"
                    }
                })

        return self._send_message(blocks=blocks)

    def _is_enabled(self) -> bool:
        """Check if Slack notifications are enabled and configured."""
        return (
            self.config.enabled and
            self.client is not None and
            self.config.channel is not None
        )

    def _send_message(self, blocks: list) -> bool:
        """
        Send message to Slack channel.

        Args:
            blocks: Slack Block Kit formatted message blocks

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._is_enabled():
            return False

        try:
            response = self.client.chat_postMessage(
                channel=self.config.channel,
                blocks=blocks,
                text="Release notification"  # Fallback text for notifications
            )
            return response["ok"]
        except self.SlackApiError as e:
            logger.warning(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            logger.warning(f"Failed to send Slack notification: {e}")
            return False


def create_slack_notifier_from_env() -> SlackNotifier:
    """
    Create SlackNotifier from environment variables.

    Uses:
    - SLACK_TOKEN: Slack bot token (required if enabled)
    - SLACK_CHANNEL: Slack channel ID or name (required if enabled)
    - SLACK_ENABLED: Set to "true" to enable (default: auto-detect from token presence)

    Returns:
        SlackNotifier instance (may be disabled if not configured)
    """
    token = os.getenv('SLACK_TOKEN')
    channel = os.getenv('SLACK_CHANNEL')
    enabled_str = os.getenv('SLACK_ENABLED', '').lower()

    # Auto-enable if token and channel are present, or if explicitly enabled
    if enabled_str == 'true':
        enabled = True
    elif enabled_str == 'false':
        enabled = False
    else:
        # Auto-detect: enabled if both token and channel are set
        enabled = bool(token and channel)

    config = SlackConfig(
        enabled=enabled,
        token=token,
        channel=channel
    )

    return SlackNotifier(config)
