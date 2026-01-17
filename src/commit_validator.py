"""
Validate conventional commit messages with severity results.

This module:
- Enforces conventional commit format
- Applies configurable type, scope, and length rules
- Produces structured validation results with severity levels
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    """Validation severity levels."""
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class ValidationResult:
    """Result of a validation check."""
    level: ValidationLevel
    message: str
    line: Optional[int] = None

    @property
    def is_error(self) -> bool:
        return self.level == ValidationLevel.ERROR

    @property
    def is_warning(self) -> bool:
        return self.level == ValidationLevel.WARNING


class CommitMessageValidator:
    """Validator for conventional commit messages."""

    # Conventional commit pattern
    COMMIT_PATTERN = re.compile(
        r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?\s*:\s*(?P<subject>.+)$'
    )

    # Valid scope pattern (alphanumeric, dash, underscore)
    SCOPE_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def __init__(self, config):
        """
        Initialize validator with configuration.

        Args:
            config: Config instance
        """
        self.config = config
        self.validation_config = config.config.get('validation', {})

    def validate(self, commit_message: str) -> List[ValidationResult]:
        """
        Validate a commit message.

        Args:
            commit_message: Full commit message to validate

        Returns:
            List of ValidationResult objects
        """
        results = []
        lines = commit_message.strip().split('\n')

        if not lines:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                "Commit message is empty"
            ))
            return results

        # Validate header (first line)
        header = lines[0].strip()
        results.extend(self._validate_header(header))

        # Validate body if present
        if len(lines) > 1:
            body = '\n'.join(lines[1:]).strip()
            if body:
                results.extend(self._validate_body(body, len(lines)))

        return results

    def _validate_header(self, header: str) -> List[ValidationResult]:
        """Validate commit message header."""
        results = []

        # Check if header matches conventional commit format
        match = self.COMMIT_PATTERN.match(header)

        if not match:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Header does not match conventional commit format: '{header}'",
                line=1
            ))
            results.append(ValidationResult(
                ValidationLevel.INFO,
                "Expected format: type(scope): subject or type: subject",
                line=1
            ))
            return results

        commit_type = match.group('type').lower()
        scope = match.group('scope')
        subject = match.group('subject').strip()
        breaking = match.group('breaking')

        # Validate type
        results.extend(self._validate_type(commit_type))

        # Validate scope if present
        if scope:
            results.extend(self._validate_scope(scope))

        # Validate subject
        results.extend(self._validate_subject(subject))

        # Validate breaking change indicator
        if breaking:
            results.extend(self._validate_breaking_indicator())

        # Validate header length
        results.extend(self._validate_header_length(header))

        return results

    def _validate_type(self, commit_type: str) -> List[ValidationResult]:
        """Validate commit type."""
        results = []

        # Get allowed types from config
        allowed_types = set(self.config.commit_types.keys())

        # Add aliases
        for type_config in self.config.commit_types.values():
            if type_config.aliases:
                allowed_types.update(type_config.aliases)

        if commit_type not in allowed_types:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid commit type '{commit_type}'. Allowed types: {', '.join(sorted(allowed_types))}",
                line=1
            ))

        return results

    def _validate_scope(self, scope: str) -> List[ValidationResult]:
        """Validate commit scope."""
        results = []

        # Check scope pattern
        if not self.SCOPE_PATTERN.match(scope):
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid scope format '{scope}'. Use only alphanumeric, dash, or underscore",
                line=1
            ))

        # Check allowed scopes if configured
        allowed_scopes = self.validation_config.get('allowed_scopes', [])
        if allowed_scopes and scope not in allowed_scopes:
            results.append(ValidationResult(
                ValidationLevel.WARNING,
                f"Scope '{scope}' is not in allowed list: {', '.join(allowed_scopes)}",
                line=1
            ))

        return results

    def _validate_subject(self, subject: str) -> List[ValidationResult]:
        """Validate commit subject."""
        results = []

        min_length = self.validation_config.get('subject_min_length', 3)
        max_length = self.validation_config.get('subject_max_length', 100)

        # Check minimum length
        if len(subject) < min_length:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Subject too short ({len(subject)} chars). Minimum: {min_length} chars",
                line=1
            ))

        # Check maximum length
        if len(subject) > max_length:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Subject too long ({len(subject)} chars). Maximum: {max_length} chars",
                line=1
            ))

        # Check if starts with lowercase (optional)
        if self.validation_config.get('subject_lowercase', True):
            if subject and subject[0].isupper():
                results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    "Subject should start with lowercase letter",
                    line=1
                ))

        # Check if ends with period
        if subject.endswith('.'):
            results.append(ValidationResult(
                ValidationLevel.WARNING,
                "Subject should not end with a period",
                line=1
            ))

        return results

    def _validate_breaking_indicator(self) -> List[ValidationResult]:
        """Validate breaking change indicator (!)."""
        results = []

        # This is valid, but we can add info
        results.append(ValidationResult(
            ValidationLevel.INFO,
            "Breaking change indicator (!) detected. Ensure BREAKING CHANGE in body or footer",
            line=1
        ))

        return results

    def _validate_header_length(self, header: str) -> List[ValidationResult]:
        """Validate total header length."""
        results = []

        max_header_length = self.validation_config.get('header_max_length', 100)

        if len(header) > max_header_length:
            results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Header too long ({len(header)} chars). Maximum: {max_header_length} chars",
                line=1
            ))

        return results

    def _validate_body(self, body: str, total_lines: int) -> List[ValidationResult]:
        """Validate commit body."""
        results = []

        # Check for blank line after header
        if total_lines > 1:
            # Body should be separated by blank line (index 1 in split result)
            # This is a common convention
            pass  # We'd need original format to check this properly

        # Check body line length
        max_line_length = self.validation_config.get('body_max_line_length', 100)
        for i, line in enumerate(body.split('\n'), start=3):  # Start at line 3 (header, blank, body)
            if len(line) > max_line_length:
                results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Body line {i-2} too long ({len(line)} chars). Maximum: {max_line_length} chars",
                    line=i
                ))

        # Check for BREAKING CHANGE in body
        if 'BREAKING CHANGE:' in body or 'BREAKING-CHANGE:' in body:
            results.append(ValidationResult(
                ValidationLevel.INFO,
                "BREAKING CHANGE detected in body",
                line=None
            ))

        return results

    def is_valid(self, commit_message: str) -> bool:
        """
        Check if commit message is valid (no errors).

        Args:
            commit_message: Commit message to validate

        Returns:
            True if valid (no errors), False otherwise
        """
        results = self.validate(commit_message)
        return not any(r.is_error for r in results)

    def format_results(self, results: List[ValidationResult]) -> str:
        """
        Format validation results for display.

        Args:
            results: List of validation results

        Returns:
            Formatted string
        """
        if not results:
            return "✅ Commit message is valid"

        lines = []
        errors = [r for r in results if r.is_error]
        warnings = [r for r in results if r.is_warning]
        infos = [r for r in results if not r.is_error and not r.is_warning]

        if errors:
            lines.append("❌ Errors:")
            for result in errors:
                line_info = f" (line {result.line})" if result.line else ""
                lines.append(f"  • {result.message}{line_info}")
            lines.append("")

        if warnings:
            lines.append("⚠️  Warnings:")
            for result in warnings:
                line_info = f" (line {result.line})" if result.line else ""
                lines.append(f"  • {result.message}{line_info}")
            lines.append("")

        if infos:
            lines.append("ℹ️  Info:")
            for result in infos:
                line_info = f" (line {result.line})" if result.line else ""
                lines.append(f"  • {result.message}{line_info}")

        return '\n'.join(lines)


def validate_commit_message(message: str, config) -> Tuple[bool, str]:
    """
    Convenience function to validate a commit message.

    Args:
        message: Commit message to validate
        config: Config instance

    Returns:
        Tuple of (is_valid, formatted_results)
    """
    validator = CommitMessageValidator(config)
    results = validator.validate(message)
    formatted = validator.format_results(results)
    is_valid = not any(r.is_error for r in results)

    return is_valid, formatted
