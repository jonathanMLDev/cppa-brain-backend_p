"""
Utility functions for cppreference.com scraper
"""

import time
import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Any
from urllib.parse import urlparse, urljoin
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


def retry(
    max_attempts: int = 3, backoff: float = 1.0, exceptions: tuple = (Exception,)
):
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
                        logger.error(
                            f"Max retries ({max_attempts}) exceeded for {func.__name__}: {e}"
                        )
                        raise
                    wait_time = backoff * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
            return None

        return wrapper

    return decorator


def normalize_url(url: str, base_url: str = "https://en.cppreference.com") -> str:
    """
    Normalize URL to absolute form.

    Args:
        url: URL to normalize (can be relative or absolute)
        base_url: Base URL for relative URLs

    Returns:
        Normalized absolute URL
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url
    elif url.startswith("/"):
        return urljoin(base_url, url)
    else:
        return urljoin(base_url + "/", url)


def url_to_filename(url: str) -> str:
    """
    Convert URL to safe filename.

    Args:
        url: URL to convert

    Returns:
        Safe filename string
    """
    # Remove protocol and domain
    parsed = urlparse(url)
    path = parsed.path

    # Remove leading slash
    if path.startswith("/"):
        path = path[1:]

    # Replace slashes and special chars
    filename = path.replace("/", "~").replace(":", "~")

    # Remove query parameters and fragments
    if "?" in filename:
        filename = filename.split("?")[0]
    if "#" in filename:
        filename = filename.split("#")[0]

    # Ensure it's not empty
    if not filename:
        filename = "index"

    # Limit length
    if len(filename) > 200:
        filename = filename[:200]

    return filename


def save_progress(progress_data: dict, filepath: str = "data/progress.json"):
    """
    Save progress to JSON file.

    Args:
        progress_data: Dictionary containing progress information
        filepath: Path to save progress file
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    progress_data["last_updated"] = datetime.now().isoformat()

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Progress saved to {filepath}")


def load_progress(filepath: str = "data/progress.json") -> dict:
    """
    Load progress from JSON file.

    Args:
        filepath: Path to progress file

    Returns:
        Dictionary containing progress information, or empty dict if file doesn't exist
    """
    if not Path(filepath).exists():
        return {
            "total_pages": 0,
            "scraped_pages": 0,
            "failed_pages": 0,
            "visited_urls": [],
            "failed_urls": [],
            "start_time": datetime.now().isoformat(),
        }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading progress: {e}")
        return {
            "total_pages": 0,
            "scraped_pages": 0,
            "failed_pages": 0,
            "visited_urls": [],
            "failed_urls": [],
            "start_time": datetime.now().isoformat(),
        }


def ensure_directories():
    """Create necessary directories if they don't exist."""
    dirs = ["data", "data/raw", "data/parsed", "data/logs"]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    logger.info("Directories ensured")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2h 30m 15s")
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


def estimate_time_remaining(total: int, completed: int, elapsed_time: float) -> float:
    """
    Estimate time remaining based on current progress.

    Args:
        total: Total number of items
        completed: Number of completed items
        elapsed_time: Time elapsed in seconds

    Returns:
        Estimated time remaining in seconds
    """
    if completed == 0:
        return 0.0

    avg_time_per_item = elapsed_time / completed
    remaining_items = total - completed
    return avg_time_per_item * remaining_items
