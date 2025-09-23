"""Utilities for working with stable identifier strings."""
from __future__ import annotations

import re
from typing import Any

__all__ = ["ProjectIdNormalizationError", "normalize_project_id"]


class ProjectIdNormalizationError(ValueError):
    """Raised when a project identifier fails validation."""


_VALID_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def normalize_project_id(raw: Any, *, max_length: int = 128) -> str:
    """Return a normalized project id or raise if the value is invalid.

    Normalization enforces a lowercase, trimmed identifier that fits a constrained
    character set. The goal is to avoid accidental high-cardinality keys caused by
    differing whitespace, casing, or unusual characters.
    """

    if not isinstance(raw, str):
        raise ProjectIdNormalizationError("projectId must be a string")

    candidate = raw.strip()
    if not candidate:
        raise ProjectIdNormalizationError("projectId (string) is required")

    candidate = candidate.lower()
    if max_length <= 0:
        raise ProjectIdNormalizationError("projectId max_length must be positive")
    if len(candidate) > max_length:
        raise ProjectIdNormalizationError(
            f"projectId exceeds max length ({max_length})"
        )

    if not _VALID_PROJECT_ID.fullmatch(candidate):
        raise ProjectIdNormalizationError(
            "projectId may only contain lowercase letters, numbers, '.', '_' or '-'"
        )

    return candidate
