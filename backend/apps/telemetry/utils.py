"""Shared utilities for telemetry app."""

from django.core.exceptions import ValidationError


def extract_validation_errors(error: ValidationError) -> dict:
    """Extract error details from ValidationError in consistent format."""
    return (
        error.message_dict if hasattr(error, "message_dict") else {"error": str(error)}
    )
