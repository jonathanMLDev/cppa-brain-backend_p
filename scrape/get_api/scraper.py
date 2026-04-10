"""
Fetch JSON from REST APIs (e.g. WordPress wp/v2/posts) and save with
essential meta keys aligned to feed format: title, link, author,
published_parsed, id, summary, content.
"""

import json
import logging
import re
import unicodedata
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from config import (
    OUTPUT_DIR,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    DEFAULT_PER_PAGE,
    DEFAULT_MAX_PAGES,
    API_URLS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Invisible / problematic Unicode to strip (avoids "invisible unicode" editor warnings)
_INVISIBLE_UNICODE_RE = re.compile(
    "[\u200b-\u200d\u2060\u00ad\ufeff\u2028\u2029]"
    "|[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]"  # C0/C1 controls
)


def _strip_invisible_unicode(s: str) -> str:
    """Remove invisible and control Unicode characters from a string."""
    if not s or not isinstance(s, str):
        return s
    s = _INVISIBLE_UNICODE_RE.sub("", s)
    # Optionally normalize other format characters (Cf category)
    s = "".join(c for c in s if unicodedata.category(c) != "Cf")
    return s


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to Markdown (same as feed scraper).
    """
    if not html or not isinstance(html, str):
        return html
    soup = BeautifulSoup(html, "lxml")
    for elem in soup.find_all(["script", "style"]):
        elem.decompose()
    markdown = md(
        str(soup),
        heading_style="ATX",
        bullets="-",
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
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"[ \t]+", " ", markdown)
    return markdown.strip()


def _date_from_link(link: str) -> str:
    """
    Extract date from post link (e.g. .../2022/06/25/slug/ -> 2022_06_25).
    """
    if not link:
        return "unknown"
    # Match /YYYY/MM/DD/ or /YYYY/MM/DD in path
    match = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})", link)
    if match:
        y, m, d = match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)
        return f"{y}_{m}_{d}"
    return "unknown"


def _sanitize_filename(name: str, max_length: int = 80) -> str:
    """Turn a string into a safe filename."""
    if not name or not name.strip():
        return "api"
    s = re.sub(r"[^\w\-_.\s]", "", name.strip())
    s = re.sub(r"\s+", "_", s)
    return s[:max_length].strip("_") or "api"


def _url_to_basename(url: str) -> str:
    """Derive a safe filename base from API URL (host + path)."""
    parsed = urlparse(url)
    netloc = (parsed.netloc or "unknown").replace(":", "_")
    path = (parsed.path or "").strip("/").replace("/", "_")
    base = f"{netloc}_{path}" if path else netloc
    base = re.sub(r"[^\w\-.]", "_", base)
    return base[:80].strip("_") or "api"


def _wp_post_to_entry(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a WordPress REST API post object to feed-like entry with essential keys:
    title, link, author, published_parsed, id, summary, content
    """
    title_obj = post.get("title") or {}
    content_obj = post.get("content") or {}
    excerpt_obj = post.get("excerpt") or {}
    # Author: WP returns author ID; use yoast_head_json.author if present for name
    author = OUTPUT_DIR.split("/")[-1]

    def _clean(s: str) -> str:
        return _strip_invisible_unicode(s) if isinstance(s, str) else str(s or "")

    return {
        "id": post.get("id"),
        "title": _clean(
            title_obj.get("rendered", "")
            if isinstance(title_obj, dict)
            else str(title_obj)
        ),
        "link": _clean(post.get("link", "")),
        "author": _clean(author),
        "published_parsed": _clean(post.get("date_gmt") or post.get("date", "")),
        "summary": _clean(
            excerpt_obj.get("rendered", "")
            if isinstance(excerpt_obj, dict)
            else str(excerpt_obj or "")
        ),
        "content": _clean(
            content_obj.get("rendered", "")
            if isinstance(content_obj, dict)
            else str(content_obj or "")
        ),
    }


def _generic_item_to_entry(
    item: Dict[str, Any],
    id_key: str = "id",
    link_key: str = "link",
    title_key: str = "title",
) -> Dict[str, Any]:
    """
    Map a generic API item to feed-like entry when not WordPress.
    Expects item to have or nest: id, link/url, title, date, author, summary/excerpt, content.
    """

    def _get(obj: Any, *keys: str, default: str = "") -> str:
        for k in keys:
            if isinstance(obj, dict) and k in obj:
                v = obj[k]
                if isinstance(v, dict) and "rendered" in v:
                    return str(v.get("rendered", default))
                return str(v) if v is not None else default
        return default

    def _clean(s: str) -> str:
        return _strip_invisible_unicode(s) if isinstance(s, str) else str(s or "")

    return {
        "id": item.get(id_key),
        "title": _clean(_get(item, "title", default="")),
        "link": _clean(_get(item, "link", "url", "permalink", default="")),
        "author": _clean(str(item.get("author", item.get("author_name", "")) or "")),
        "published_parsed": _clean(
            str(item.get("date_gmt") or item.get("date") or item.get("published") or "")
        ),
        "summary": _clean(_get(item, "excerpt", "summary", "description", default="")),
        "content": _clean(_get(item, "content", "body", default="")),
    }


def _is_wp_posts_url(url: str) -> bool:
    """Heuristic: is this URL a WordPress wp/v2/posts endpoint."""
    return "/wp/v2/posts" in url or "/wp-json/wp/v2/posts" in url


def _fetch_page(url: str, per_page: int = 100, page: int = 1) -> Optional[List[Dict]]:
    """Fetch one page of JSON from URL. Returns list of items or None."""
    try:
        header = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        r = requests.get(
            url, params={"per_page": per_page, "page": page}, headers=header
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 406:
            logger.warning(
                "406 Not Acceptable for %s (server may reject per_page or require Accept: application/json)",
                url,
            )
        logger.exception("Request failed %s: %s", url, e)
        return None
    except Exception as e:
        logger.exception("Request failed %s: %s", url, e)
        return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"] if isinstance(data["data"], list) else None
    return None


def _paginate_wp_posts(
    base_url: str,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> List[Dict[str, Any]]:
    """Fetch all pages from a WordPress posts API URL."""
    all_posts = []
    page = 1
    # Some WordPress hosts return 406 for large per_page; retry with smaller
    effective_per_page = per_page
    while True:
        items = _fetch_page(base_url, per_page=effective_per_page, page=page)
        if not items and page == 1 and effective_per_page > 10:
            effective_per_page = 10
            logger.info(
                "Retrying with per_page=%d (server may have rejected %d)",
                effective_per_page,
                per_page,
            )
            continue
        if not items:
            break
        all_posts.extend(items)
        if len(items) < effective_per_page:
            break
        page += 1
        if max_pages is not None and page > max_pages:
            break
        if REQUEST_DELAY > 0:
            time.sleep(REQUEST_DELAY)
    return all_posts


def _entry_html_to_markdown(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert summary and content from HTML to Markdown (like feed scraper)."""
    out = dict(entry)
    if entry.get("summary"):
        out["summary"] = html_to_markdown(entry["summary"])
    if entry.get("content"):
        out["content"] = html_to_markdown(entry["content"])
    return out


def fetch_and_save(
    api_url: str,
    output_dir: Optional[Path] = None,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
    to_entry_fn=None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch from api_url, map to feed-like entries, convert HTML to Markdown,
    and save one JSON file per entry with date-based filename (e.g. 2022_06_25.json).
    """
    output_dir = Path(output_dir or OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if _is_wp_posts_url(api_url):
        raw_items = _paginate_wp_posts(api_url, per_page=per_page, max_pages=max_pages)
        to_entry = to_entry_fn or _wp_post_to_entry
    else:
        raw_items = _fetch_page(api_url)
        raw_items = raw_items or []
        to_entry = to_entry_fn or (lambda x: _generic_item_to_entry(x))

    entries = [to_entry(item) for item in raw_items]
    # Convert HTML to Markdown (like feed scraper)
    entries = [_entry_html_to_markdown(e) for e in entries]

    # One JSON per entry; filename from link date (e.g. 2022_06_25.json)
    date_count: Dict[str, int] = {}
    saved = 0
    for entry in entries:
        date_key = entry.get("published_parsed", "")[:10].replace("-", "_")
        date_count[date_key] = date_count.get(date_key, 0) + 1
        n = date_count[date_key]
        base = f"{date_key}.json" if n == 1 else f"{date_key}_{n}.json"
        out_file = output_dir / base
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
            saved += 1
            logger.debug("Saved %s", out_file)
        except OSError as e:
            logger.exception("Failed to write %s: %s", out_file, e)
    logger.info(
        "Saved %d entries to %s (one JSON per entry, date-based filenames)",
        saved,
        output_dir,
    )
    return {"api_url": api_url, "entries": entries}


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch API JSON and save with essential meta keys (feed-like)"
    )
    parser.add_argument("url", nargs="?", help="API URL (e.g. WordPress wp/v2/posts)")
    parser.add_argument(
        "-o", "--output-dir", default=OUTPUT_DIR, help="Output directory for JSON"
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help="Posts per page (WordPress)",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None, help="Max pages to fetch (default: all)"
    )
    args = parser.parse_args()

    url = args.url
    if not url:
        url = API_URLS[0] if API_URLS else None
    if not url:
        logger.error("Provide URL as argument or set config.API_URLS")
        return

    fetch_and_save(
        url,
        output_dir=Path(args.output_dir),
        per_page=args.per_page,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    main()
