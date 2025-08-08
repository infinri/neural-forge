from datetime import datetime, timezone


def utc_now_iso_z() -> str:
    """Return an ISO-8601 UTC timestamp ending with 'Z'."""
    # datetime.now(timezone.utc).isoformat() yields e.g. '2025-08-07T23:20:00.123456+00:00'
    # Replace the offset with 'Z' for consistency with existing API responses.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
