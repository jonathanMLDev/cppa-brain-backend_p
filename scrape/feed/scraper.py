"""
Feed scraper: fetch RSS/Atom feeds via feedparser and save as JSON.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from config import (
    OUTPUT_DIR,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    FEED_URLS,
    CONVERT_HTML_TO_MARKDOWN,
)
from utils import (
    rate_limit,
    sanitize_filename,
    url_to_filename,
    serialize_date,
)

logger = logging.getLogger(__name__)


def html_to_markdown(html: str) -> str:
    """
    Convert HTML content to Markdown format.

    Args:
        html: HTML content as string

    Returns:
        Markdown content as string
    """
    if not html or not isinstance(html, str):
        return html

    # Pre-process HTML to remove unwanted tags before conversion
    soup = BeautifulSoup(html, "lxml")

    # Remove script and style tags
    for elem in soup.find_all(["script", "style"]):
        elem.decompose()

    # Use markdownify to convert HTML to Markdown
    markdown = md(
        str(soup),
        heading_style="ATX",  # Use # for headings
        bullets="-",  # Use - for bullets
        convert=[
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "a",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
            "table",
            "tr",
            "td",
            "th",
            "code",
            "pre",
            "blockquote",
            "div",
            "span",
            "section",
            "img",
            "br",
        ],
    )

    # Clean up excessive whitespace
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"[ \t]+", " ", markdown)

    return markdown.strip()


def _filter_entry_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter entry to only include specified fields:
    title, link, author, published_parsed, id, summary, content/value
    """
    filtered = {}

    # Extract basic fields (only include if they exist)
    if "title" in entry:
        filtered["title"] = entry["title"]
    if "link" in entry:
        filtered["link"] = entry["link"]
    if "author" in entry:
        filtered["author"] = entry["author"]
    if "published_parsed" in entry:
        filtered["published_parsed"] = entry["published_parsed"]
    if "id" in entry:
        filtered["id"] = entry["id"]
    if "summary" in entry:
        filtered["summary"] = entry["summary"]

    # Extract content/value from content array
    # After HTML-to-Markdown conversion, content is still an array with value fields
    if "content" in entry:
        if isinstance(entry["content"], list) and len(entry["content"]) > 0:
            # Get the value from the first content item (usually the main content)
            first_content = entry["content"][0]
            if isinstance(first_content, dict) and "value" in first_content:
                content_value = first_content["value"]
                if content_value:  # Only add if not empty
                    filtered["content"] = content_value
            elif isinstance(first_content, str) and first_content:
                filtered["content"] = first_content
        elif isinstance(entry["content"], str) and entry["content"]:
            # Sometimes content is a direct string
            filtered["content"] = entry["content"]

    return filtered


def _convert_html_fields_to_markdown(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively convert HTML fields (summary, content) to Markdown in feed data.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in ("summary", "description") and isinstance(value, str):
                # Convert summary/description HTML to Markdown
                result[key] = html_to_markdown(value)
            elif key == "summary_detail" and isinstance(value, dict):
                # Convert summary_detail.value HTML to Markdown
                result[key] = value.copy()
                if "value" in result[key] and isinstance(result[key]["value"], str):
                    result[key]["value"] = html_to_markdown(result[key]["value"])
                    result[key]["type"] = "text/markdown"  # Update type
            elif key == "content" and isinstance(value, list):
                # Convert content[].value HTML to Markdown
                result[key] = []
                for item in value:
                    if isinstance(item, dict) and "value" in item:
                        new_item = item.copy()
                        if isinstance(new_item["value"], str):
                            new_item["value"] = html_to_markdown(new_item["value"])
                            new_item["type"] = "text/markdown"  # Update type
                        result[key].append(new_item)
                    else:
                        result[key].append(item)
            else:
                # Recursively process nested structures
                result[key] = (
                    _convert_html_fields_to_markdown(value)
                    if isinstance(value, (dict, list))
                    else value
                )
        return result
    elif isinstance(data, list):
        return [_convert_html_fields_to_markdown(item) for item in data]
    else:
        return data


def _to_serializable(obj: Any) -> Any:
    """
    Recursively convert feedparser structures to JSON-serializable types.
    Converts time.struct_time to ISO 8601 strings.
    """
    if obj is None:
        return None
    try:
        from time import struct_time

        if isinstance(obj, struct_time):
            return serialize_date(obj)
    except Exception:
        pass
    if hasattr(obj, "isoformat"):
        return getattr(obj, "isoformat")()
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    # feedparser uses objects with .__dict__ or key access
    if hasattr(obj, "keys"):
        try:
            return {str(k): _to_serializable(obj[k]) for k in obj.keys()}
        except (KeyError, TypeError):
            pass
    return str(obj)


def _feed_to_dict(parsed: feedparser.FeedParserDict) -> Dict[str, Any]:
    """Convert parsed feed (feed.feed + feed.entries) to a plain dict."""
    feed_meta = getattr(parsed, "feed", {})
    entries = getattr(parsed, "entries", [])
    return {
        "feed_url": getattr(parsed, "href", None) or getattr(parsed, "url", None),
        "bozo": bool(getattr(parsed, "bozo", False)),
        "bozo_exception": (
            str(parsed.get("bozo_exception", ""))
            if parsed.get("bozo_exception")
            else None
        ),
        "feed": _to_serializable(dict(feed_meta)) if feed_meta else {},
        "entries": [_to_serializable(dict(e)) for e in entries],
    }


@rate_limit(REQUEST_DELAY)
def fetch_feed(
    url: str, timeout: int = REQUEST_TIMEOUT, user_agent: str = USER_AGENT
) -> feedparser.FeedParserDict:
    """Fetch and parse a feed URL. Rate-limited. Uses requests for timeout support."""
    headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def scrape_feed(
    url: str, output_dir: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single feed URL, convert to a plain dict, and save as JSON.
    Returns the converted dict or None on failure.
    """
    output_dir = output_dir or Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        parsed = fetch_feed(url)
    except Exception as e:
        logger.exception("Failed to fetch feed %s: %s", url, e)
        return None

    data = _feed_to_dict(parsed)
    data["feed_url"] = url

    # Convert HTML fields to Markdown if enabled
    if CONVERT_HTML_TO_MARKDOWN:
        data = _convert_html_fields_to_markdown(data)

    # Filter entries to only include specified fields
    if "entries" in data and isinstance(data["entries"], list):
        data["entries"] = [_filter_entry_fields(entry) for entry in data["entries"]]

    for i, entry in enumerate(data["entries"]):
        entry_date = _filter_entry_fields(entry)

        file_name = url_to_filename(entry["link"])
        entry_path = output_dir / f"{file_name}_{i+1:02d}.json"

        with open(entry_path, "w", encoding="utf-8") as f:
            json.dump(entry_date, f, indent=2, ensure_ascii=False)

        logger.info("Saved entry to %s", entry_path)

    return data


def scrape_feeds(
    urls: Optional[List[str]] = None, output_dir: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Scrape multiple feed URLs and save each as a JSON file.
    Uses FEED_URLS from config if urls is None.
    """
    urls = urls or FEED_URLS
    if not urls:
        logger.warning("No feed URLs configured; pass urls= or set config.FEED_URLS")
        return []

    results = []
    for url in urls:
        data = scrape_feed(url.strip(), output_dir=output_dir)
        if data is not None:
            results.append(data)
    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape RSS/Atom feeds to JSON")
    parser.add_argument(
        "urls", nargs="*", help="Feed URLs (default: use config FEED_URLS)"
    )
    parser.add_argument(
        "-o", "--output-dir", default=OUTPUT_DIR, help="Output directory for JSON files"
    )
    args = parser.parse_args()

    urls = args.urls if args.urls else None
    output_dir = Path(args.output_dir)
    scrape_feeds(urls=urls, output_dir=output_dir)


if __name__ == "__main__":
    main()
