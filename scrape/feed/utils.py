"""
Utility functions for feed scraper.
"""

import time
import re
import logging
from typing import Callable, Any
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def rate_limit(delay: float):
    """Decorator for rate limiting function calls."""

    def decorator(func: Callable) -> Callable:
        last_called = [0.0]

        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result

        return wrapper

    return decorator


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    Turn a string (e.g. feed title or URL) into a safe filename.
    """
    if not name or not name.strip():
        return "feed"
    s = name.strip()
    s = re.sub(r"[^\w\-_.\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = s[:max_length].strip("_")
    return s or "feed"


def url_to_filename(url: str) -> str:
    """
    Derive a safe filename from a feed URL (e.g. for hashing or domain).
    If extension is empty, returns only the base name (no dot).
    """
    parsed = urlparse(url)
    netloc = parsed.netloc or "unknown"
    base = f"{netloc}_{parsed.path[:11].strip("/")}"
    base = re.sub(r"[^\w\-.]", "_", base)
    return base


def serialize_date(obj: Any) -> str | None:
    """
    Convert feedparser time tuple or struct_time to ISO 8601 string.
    """
    if obj is None:
        return None
    try:
        from time import struct_time

        if isinstance(obj, struct_time):
            from time import mktime
            from datetime import datetime

            ts = mktime(obj)
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    if hasattr(obj, "isoformat"):
        return getattr(obj, "isoformat")()
    return str(obj) if obj else None
