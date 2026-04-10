"""
Utility functions for Boost libraries scraper
"""

import time
import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Any
from urllib.parse import urlparse
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def rate_limit(delay: float):
    """
    Decorator for rate limiting function calls.

    Args:
        delay: Minimum seconds between calls
    """
    def decorator(func: Callable) -> Callable:
        last_called = [0.0]

        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator


def retry(max_attempts: int = 3, backoff: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Initial backoff time in seconds
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"Max retries ({max_attempts}) exceeded for {func.__name__}: {e}")
                        raise
                    wait_time = backoff * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator


def version_to_filename(version: str, extension: str = "json") -> str:
    """
    Convert version string to safe filename.

    Args:
        version: Version string (e.g., "1.36.0")
        extension: File extension (default: "json")

    Returns:
        Safe filename string (e.g., "1_36_0.json")
    """
    return version.replace(".", "_") + f".{extension}"


def version_to_url(version: str, base_url_pattern: str = None) -> str:
    """
    Convert version string to Boost libraries URL.

    Args:
        version: Version string (e.g., "1.36.0")
        base_url_pattern: Base URL pattern (defaults to config value)

    Returns:
        URL string (e.g., "https://www.boost.org/libraries/1.36.0/list/")
    """
    if base_url_pattern is None:
        from config import BASE_URL_PATTERN
        base_url_pattern = BASE_URL_PATTERN
    return base_url_pattern.format(version=version)


def parse_version_range(start: str, end: str) -> list:
    """
    Parse version range and generate list of versions.

    Note: This generates a simple sequential list. For actual Boost releases,
    you may want to provide a specific list of versions since releases
    don't follow a strict sequential pattern.

    Args:
        start: Start version (e.g., "1.36.0")
        end: End version (e.g., "1.90.0")

    Returns:
        List of version strings
    """
    def version_to_tuple(v: str) -> tuple:
        parts = v.split(".")
        # Ensure we have at least 3 parts (major.minor.patch)
        while len(parts) < 3:
            parts.append("0")
        return tuple(int(p) for p in parts[:3])

    def tuple_to_version(t: tuple) -> str:
        return ".".join(str(p) for p in t)

    start_tuple = version_to_tuple(start)
    end_tuple = version_to_tuple(end)

    versions = []
    current = list(start_tuple)

    # Generate versions from start to end
    while tuple(current) <= end_tuple:
        versions.append(tuple_to_version(tuple(current)))

        # Increment version (patch -> minor -> major)
        current[2] += 1  # Increment patch
        if current[2] > 3:  # Arbitrary limit
            current[2] = 0
            current[1] += 1  # Increment minor
            if current[1] > 99:
                current[1] = 0
                current[0] += 1  # Increment major

    return versions


def ensure_directories():
    """Ensure all necessary directories exist."""
    from config import OUTPUT_DIR, LOG_FILE, RAW_HTML_DIR

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(RAW_HTML_DIR).mkdir(parents=True, exist_ok=True)
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


def save_progress(progress_file: str, data: dict):
    """
    Save progress to JSON file.

    Args:
        progress_file: Path to progress file
        data: Progress data dictionary
    """
    Path(progress_file).parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_progress(progress_file: str) -> dict:
    """
    Load progress from JSON file.

    Args:
        progress_file: Path to progress file

    Returns:
        Progress data dictionary
    """
    # if Path(progress_file).exists():
    #     with open(progress_file, 'r', encoding='utf-8') as f:
    #         return json.load(f)
    return {
        "scraped_versions": [],
        "failed_versions": [],
        "last_updated": None
    }


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)

