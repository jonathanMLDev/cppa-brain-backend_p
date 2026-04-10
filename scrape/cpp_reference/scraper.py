"""
Main scraper implementation for cppreference.com
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import json
from pathlib import Path
from urllib.parse import urljoin, quote
from typing import List, Optional, Set
from xml.etree import ElementTree as ET

from config import (
    BASE_URL,
    CHECKPOINT_INTERVAL,
    INDEX_PAGES,
    LOG_FILE,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_DELAY_SECONDS,
    MAX_RETRIES,
    MEDIAWIKI_API_URL,
    MIN_CONTENT_LENGTH,
    PROGRESS_FILE,
    RAW_DIR,
    RAW_HTML_DIR,
    RAW_MD_DIR,
    RECOMMENDED_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_FACTOR,
    SELECTORS,
    USER_AGENT,
)
from html2md import convert_html_to_md
from utils import (
    rate_limit,
    retry,
    normalize_url,
    url_to_filename,
    save_progress,
    load_progress,
    ensure_directories,
    format_duration,
    estimate_time_remaining,
)

# Ensure directories exist before setting up logging
ensure_directories()

# Set up logging
log_file_path = Path(LOG_FILE)
log_file_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CppReferenceScraper:
    """
    Scraper for cppreference.com live site.
    """

    def __init__(self, delay: float = RECOMMENDED_DELAY_SECONDS):
        """
        Initialize scraper.

        Args:
            delay: Delay between requests in seconds
        """
        self.base_url = BASE_URL
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.visited: Set[str] = set()
        self.failed: Set[str] = set()
        self.progress = load_progress(PROGRESS_FILE)

        # Ensure directories exist
        ensure_directories()

        logger.info(f"Scraper initialized with delay={delay}s, User-Agent={USER_AGENT}")

    @retry(
        max_attempts=MAX_RETRIES,
        backoff=RETRY_BACKOFF_FACTOR,
        exceptions=(requests.RequestException,),
    )
    @rate_limit(RECOMMENDED_DELAY_SECONDS)
    def get_page(self, url: str) -> Optional[requests.Response]:
        """
        Fetch a page with rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if failed
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            # Ensure UTF-8 encoding for proper handling of Chinese and other Unicode characters
            response.encoding = "utf-8"
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Page not found (404): {url}")
            elif e.response.status_code == 429:
                logger.warning(f"Rate limited (429): {url}. Increasing delay...")
                self.delay = min(self.delay * 1.5, MAX_DELAY_SECONDS)
                raise  # Retry with backoff
            elif e.response.status_code == 503:
                logger.warning(
                    f"Service unavailable (503): {url}. May be in maintenance mode."
                )
                raise  # Retry with backoff
            else:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
                self.failed.add(url)
            return None
        except requests.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            self.failed.add(url)
            raise  # Retry with backoff

    def discover_urls_from_api(self) -> List[str]:
        """
        Discover all URLs using MediaWiki API.
        This is the recommended method since sitemap.xml doesn't exist.

        Returns:
            List of URLs to scrape
        """
        logger.info(f"Discovering URLs using MediaWiki API: {MEDIAWIKI_API_URL}")

        urls = []
        continue_token = None
        page_count = 0

        try:
            while True:
                params = {
                    "action": "query",
                    "list": "allpages",
                    "aplimit": 500,  # Max per request (MediaWiki limit)
                    "apnamespace": 0,  # Main namespace
                    "apfilterredir": "nonredirects",  # Skip redirects
                    "format": "json",
                }

                if continue_token:
                    params["apcontinue"] = continue_token

                logger.debug(
                    f"API request: page_count={page_count}, continue_token={'...' if continue_token else None}"
                )

                response = self.session.get(
                    MEDIAWIKI_API_URL, params=params, timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()

                data = response.json()

                # Check for errors
                if "error" in data:
                    logger.error(f"API error: {data['error']}")
                    break

                # Extract page titles
                pages = data.get("query", {}).get("allpages", [])

                for page in pages:
                    title = page["title"]
                    # Convert MediaWiki title to URL
                    # Replace spaces with underscores and URL encode
                    url_path = title.replace(" ", "_")
                    url = f"{BASE_URL}{quote(url_path, safe='/')}"

                    # Filter for C++ related pages
                    if "/w/cpp/" in url or url.startswith(f"{BASE_URL}cpp"):
                        urls.append(url)

                page_count += len(pages)
                logger.info(
                    f"Processed {page_count} pages, found {len(urls)} C++ URLs so far..."
                )

                # Check for continuation
                if "continue" in data and "apcontinue" in data["continue"]:
                    continue_token = data["continue"]["apcontinue"]
                    # Rate limit between API requests
                    time.sleep(RECOMMENDED_DELAY_SECONDS)
                else:
                    break

            logger.info(
                f"Discovered {len(urls)} C++ URLs from MediaWiki API (from {page_count} total pages)"
            )
            return urls

        except requests.RequestException as e:
            logger.error(f"Error fetching from MediaWiki API: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing API response: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in API discovery: {e}")
            return []

    def discover_urls_from_sitemap(self) -> List[str]:
        """
        Discover all URLs from sitemap.
        NOTE: This method will fail since sitemap.xml doesn't exist on cppreference.com.
        Kept for compatibility but will always return empty list.

        Returns:
            List of URLs to scrape (always empty)
        """
        logger.warning(
            "Sitemap method called, but sitemap.xml doesn't exist on cppreference.com"
        )
        return []

    def discover_urls_from_index(self, max_depth: int = 2) -> List[str]:
        """
        Discover URLs by following links from index pages.

        Args:
            max_depth: Maximum depth to follow links

        Returns:
            List of URLs to scrape
        """
        logger.info("Discovering URLs from index pages")

        all_urls: Set[str] = set()

        for index_url in INDEX_PAGES:
            logger.info(f"Processing index: {index_url}")
            urls = self._extract_links_from_page(index_url, max_depth)
            all_urls.update(urls)

        logger.info(f"Discovered {len(all_urls)} unique URLs from index pages")
        url_pattern = "https://www.fluentcpp.com/20"
        all_urls = [url for url in all_urls if url_pattern in url]
        return all_urls

    def _extract_links_from_page(
        self, url: str, max_depth: int, current_depth: int = 0
    ) -> Set[str]:
        """
        Recursively extract links from a page.

        Args:
            url: URL to extract links from
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth

        Returns:
            Set of discovered URLs
        """
        if current_depth >= max_depth:
            return set()

        urls = set()
        response = self.get_page(url)

        if not response:
            return urls
        base_url = "/".join(url.split("/")[:-1]) + "/"

        try:
            soup = BeautifulSoup(response.content, "html.parser")

            # Find all links to cppreference pages
            for link in soup.find_all("a", href=True):
                href = link["href"]

                # Root-relative URL - might be valid
                full_url = urljoin(base_url, href)
                if "#" in full_url:
                    continue
                if not (full_url.endswith(".html") or full_url.endswith("/")):
                    continue

                # Filter for C++ related pages (consistent with API method)
                if not full_url.startswith(base_url):
                    continue
                if full_url in self.visited:
                    continue

                self.visited.add(full_url)
                urls.add(full_url)

                # Recursively follow links if depth allows
                sub_urls = self._extract_links_from_page(
                    full_url, max_depth, current_depth + 1
                )
                urls.update(sub_urls)

        except Exception as e:
            logger.error(f"Error extracting links from {url}: {e}")

        return urls

    def get_html_path(self, file_name: str) -> Path:
        """Return path for raw HTML file under raw_dir/html."""
        return Path(RAW_HTML_DIR) / f"{file_name}.html"

    def get_md_path(self, file_name: str) -> Path:
        """Return path for Markdown file under raw_dir/md."""
        return Path(RAW_MD_DIR) / f"{file_name}.md"

    def save_raw_html(self, url: str, html: str):
        """
        Save raw HTML to raw_dir/html and convert to Markdown in raw_dir/md.

        Args:
            url: Source URL
            html: HTML content
        """
        filename = url_to_filename(url)
        html_path = self.get_html_path(filename)
        md_path = self.get_md_path(filename)

        # Ensure directories exist
        html_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        # Save HTML
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.debug(f"Saved raw HTML: {html_path}")

        # Convert to Markdown using html2md and save to raw_dir/md
        try:
            result = convert_html_to_md(
                str(html_path),
                url,
                markdown_format="gfm",
                md_path=md_path,
            )
            if result:
                logger.debug(f"Saved Markdown: {md_path}")
            else:
                logger.warning(f"HTML-to-MD conversion failed for {url}")
        except Exception as e:
            logger.warning(f"HTML-to-MD conversion failed for {url}: {e}")

    def update_progress(self):
        """Update and save progress."""
        self.progress["total_pages"] = len(self.visited) + len(self.failed)
        self.progress["scraped_pages"] = len(self.visited)
        self.progress["failed_pages"] = len(self.failed)
        self.progress["visited_urls"] = list(self.visited)
        self.progress["failed_urls"] = list(self.failed)

        save_progress(self.progress, PROGRESS_FILE)

    def check_process(self, re_scrape: bool = True):
        """
        Check if HTML files exist for all URLs in progress.json and re-scrape missing ones.

        Args:
            re_scrape: If True, attempt to re-scrape missing URLs. If False, only report missing files.

        Returns:
            Dictionary with statistics about the check process
        """
        logger.info("Starting process check...")

        # Load progress from file (in case it was updated externally)
        self.progress = load_progress(PROGRESS_FILE)

        # Get all URLs from progress
        visited_urls = self.progress.get("visited_urls", [])
        failed_urls = self.progress.get("failed_urls", [])
        all_urls = visited_urls + failed_urls

        logger.info(f"Checking {len(all_urls)} URLs from progress.json")
        logger.info(f"  - Visited URLs: {len(visited_urls)}")
        logger.info(f"  - Failed URLs: {len(failed_urls)}")

        missing_urls = []
        existing_urls = []

        # Check each URL
        for url in all_urls:
            filename = url_to_filename(url)
            filepath = self.get_html_path(filename)

            if not filepath.exists():
                missing_urls.append(url)
                logger.debug(f"Missing file for URL: {url} (expected: {filepath})")
            else:
                existing_urls.append(url)

        logger.info(f"File check complete:")
        logger.info(f"  - Existing files: {len(existing_urls)}")
        logger.info(f"  - Missing files: {len(missing_urls)}")

        self.progress["visited_urls"] = existing_urls
        self.progress["failed_urls"] = missing_urls
        self.progress["scraped_pages"] = len(existing_urls)
        self.progress["failed_pages"] = len(missing_urls)
        save_progress(self.progress, PROGRESS_FILE)
        if missing_urls:
            logger.warning(
                f"Found {len(missing_urls)} URLs without corresponding HTML files"
            )

            if re_scrape:
                logger.info(
                    f"Attempting to re-scrape {len(missing_urls)} missing URLs..."
                )

                # Remove from visited/failed sets to allow re-scraping
                for url in missing_urls:
                    self.visited.discard(url)
                    self.failed.discard(url)

                # Re-scrape missing URLs
                self.scrape_urls(missing_urls, save_raw=True)

                logger.info("Re-scraping complete")
            else:
                logger.info("Re-scraping disabled. Missing URLs logged above.")
        else:
            logger.info("All URLs have corresponding HTML files!")

        return {
            "total_urls": len(all_urls),
            "existing_files": len(existing_urls),
            "missing_files": len(missing_urls),
            "missing_urls": missing_urls,
        }

    def scrape_urls(self, urls: List[str], save_raw: bool = True):
        """
        Scrape a list of URLs.

        Args:
            urls: List of URLs to scrape
            save_raw: Whether to save raw HTML files
        """
        total = len(urls)
        start_time = time.time()

        logger.info(f"Starting to scrape {total} URLs...")

        for i, url in enumerate(urls, 1):
            try:
                response = self.get_page(url)
                if response:
                    if save_raw:
                        self.save_raw_html(url, response.text)

                    # Log progress
                    if i % 10 == 0 or i == total:
                        elapsed = time.time() - start_time
                        remaining = estimate_time_remaining(total, i, elapsed)
                        logger.info(
                            f"Progress: {i}/{total} ({i/total*100:.1f}%) | "
                            f"Elapsed: {format_duration(elapsed)} | "
                            f"Remaining: {format_duration(remaining)}"
                        )

                    # Save progress periodically
                    if i % CHECKPOINT_INTERVAL == 0:
                        self.update_progress()

            except Exception as e:
                logger.error(f"Unexpected error scraping {url}: {e}")
                self.failed.add(url)

        # Final progress update
        self.update_progress()

        elapsed = time.time() - start_time
        logger.info(
            f"Scraping completed: {len(self.visited)} successful, "
            f"{len(self.failed)} failed in {format_duration(elapsed)}"
        )


def main(check_mode: bool = False):
    """Main entry point."""
    scraper = CppReferenceScraper()

    if check_mode:
        scraper.check_process()
        return

    # Discover URLs using multiple methods (in order of preference)
    logger.info("Discovering URLs...")
    urls = []

    # Method 1: MediaWiki API (recommended - most complete)
    logger.info("Trying MediaWiki API method...")
    urls = scraper.discover_urls_from_api()

    # Method 2: Index-based discovery (fallback if API fails)
    if not urls:
        logger.warning("API method failed, trying index-based discovery...")
        urls = scraper.discover_urls_from_index()

    # Method 3: Sitemap (will always fail, but kept for compatibility)
    if not urls:
        logger.warning("Index method failed, trying sitemap (will likely fail)...")
        urls = scraper.discover_urls_from_sitemap()

    if not urls:
        logger.error("Failed to discover any URLs using all methods. Exiting.")
        return

    logger.info(f"Successfully discovered {len(urls)} URLs to scrape")

    # Filter out already visited URLs
    if scraper.progress.get("visited_urls"):
        visited = set(scraper.progress["visited_urls"])
        urls = [url for url in urls if url not in visited]
        logger.info(
            f"Filtered to {len(urls)} new URLs (skipping {len(visited)} already visited)"
        )

    # Begin scraping
    scraper.scrape_urls(urls, save_raw=True)

    logger.info("Scraping complete!")


if __name__ == "__main__":
    main(check_mode=False)
