"""
Main scraper implementation for Boost release notes
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import json
from pathlib import Path
from typing import Optional, Set, List
from markdownify import markdownify as md

from config import *
from utils import (
    rate_limit, retry, version_to_filename, version_to_url,
    save_progress, load_progress, ensure_directories,
    format_duration, parse_version_range
)

# Ensure directories exist before setting up logging
ensure_directories()

# Set up logging
log_file_path = Path(LOG_FILE)
log_file_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BoostReleaseNoteScraper:
    """
    Scraper for Boost.org release notes.
    """

    def __init__(self, delay: float = RECOMMENDED_DELAY_SECONDS):
        """
        Initialize scraper.

        Args:
            delay: Delay between requests in seconds
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT
        })
        self.visited: Set[str] = set()
        self.failed: Set[str] = set()
        self.progress = load_progress(PROGRESS_FILE)

        # Ensure directories exist
        ensure_directories()

        logger.info(f"Scraper initialized with delay={delay}s, User-Agent={USER_AGENT}")

    @retry(max_attempts=MAX_RETRIES, backoff=RETRY_BACKOFF_FACTOR,
           exceptions=(requests.RequestException,))
    @rate_limit(RECOMMENDED_DELAY_SECONDS)
    def get_page(self, url: str) -> Optional[requests.Response]:
        """
        Fetch a page with rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if failed
        """
        if url in self.visited:
            logger.debug(f"Skipping already visited: {url}")
            return None

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            response.encoding = 'utf-8'
            self.visited.add(url)
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Page not found (404): {url}")
                self.visited.add(url)  # Mark as visited to avoid retrying
            elif e.response.status_code == 429:
                logger.warning(f"Rate limited (429): {url}. Increasing delay...")
                self.delay = min(self.delay * 1.5, MAX_DELAY_SECONDS)
                raise  # Retry with backoff
            elif e.response.status_code == 503:
                logger.warning(f"Service unavailable (503): {url}. May be in maintenance mode.")
                raise  # Retry with backoff
            else:
                logger.error(f"HTTP error {e.response.status_code}: {url}")
                self.failed.add(url)
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {e}")
            self.failed.add(url)
            return None

    def extract_main_content(self, html: str) -> Optional[str]:
        """
        Extract content from <main> tag or fallback selector.

        Args:
            html: HTML content as string

        Returns:
            Extracted HTML content or None if not found
        """
        soup = BeautifulSoup(html, 'lxml')

        # Remove version dropdown selector and related form elements
        # Remove select elements with version dropdown
        for select in soup.find_all('select', {'name': 'version'}):
            select.decompose()
        for select in soup.find_all('select', {'id': 'id_version'}):
            select.decompose()

        # Remove forms containing version selectors
        for form in soup.find_all('form'):
            if form.find('select', {'name': 'version'}) or form.find('select', {'id': 'id_version'}):
                form.decompose()

        # Remove divs containing version selector forms
        for div in soup.find_all('div', class_='flex-shrink'):
            if div.find('form') and div.find('select', {'name': 'version'}):
                div.decompose()

        # Try to find <main> tag first
        main_tag = soup.find('main')
        if main_tag:
            logger.debug("Found <main> tag")
            # Also clean the main tag content
            for select in main_tag.find_all('select', {'name': 'version'}):
                select.decompose()
            for form in main_tag.find_all('form'):
                if form.find('select', {'name': 'version'}):
                    form.decompose()
            for div in main_tag.find_all('div', class_='flex-shrink'):
                if div.find('form') and div.find('select', {'name': 'version'}):
                    div.decompose()
            return str(main_tag)

        # Fallback to section.content if main not found
        fallback_selector = SELECTORS["fallback_content"]
        if '.' in fallback_selector:
            tag_name, class_name = fallback_selector.split('.', 1)
            fallback = soup.find(tag_name, class_=class_name)
        else:
            fallback = soup.find(fallback_selector)

        if fallback:
            logger.debug("Using fallback content selector")
            # Clean the fallback content too
            for select in fallback.find_all('select', {'name': 'version'}):
                select.decompose()
            for form in fallback.find_all('form'):
                if form.find('select', {'name': 'version'}):
                    form.decompose()
            for div in fallback.find_all('div', class_='flex-shrink'):
                if div.find('form') and div.find('select', {'name': 'version'}):
                    div.decompose()
            return str(fallback)

        # Last resort: try to find any main content area
        body = soup.find('body')
        if body:
            logger.warning("No main tag found, using body content")
            # Remove common non-content elements
            for elem in body.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                elem.decompose()
            return str(body)

        logger.error("Could not find main content")
        return None

    def html_to_markdown(self, html: str) -> str:
        """
        Convert HTML content to Markdown.

        Args:
            html: HTML content as string

        Returns:
            Markdown content as string
        """
        # Pre-process HTML to remove unwanted tags before conversion
        soup = BeautifulSoup(html, 'lxml')

        # Remove script and style tags
        for elem in soup.find_all(['script', 'style']):
            elem.decompose()

        # Remove version dropdown selector (safety check in case it wasn't removed earlier)
        for select in soup.find_all('select', {'name': 'version'}):
            select.decompose()
        for select in soup.find_all('select', {'id': 'id_version'}):
            select.decompose()

        # Remove forms containing version selectors
        for form in soup.find_all('form'):
            if form.find('select', {'name': 'version'}) or form.find('select', {'id': 'id_version'}):
                form.decompose()

        # Remove divs containing version selector forms
        for div in soup.find_all('div', class_='flex-shrink'):
            if div.find('form') and div.find('select', {'name': 'version'}):
                div.decompose()

        # Use markdownify to convert HTML to Markdown
        # Note: markdownify doesn't allow both strip and convert parameters
        markdown = md(
            str(soup),
            heading_style="ATX",  # Use # for headings
            bullets="-",  # Use - for bullets
            convert=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'strong', 'em', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'code', 'pre', 'blockquote', 'div', 'span', 'section']
        )

        # Clean up excessive whitespace
        import re
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        markdown = re.sub(r'[ \t]+', ' ', markdown)

        return markdown.strip()

    def scrape_version(self, version: str) -> bool:
        """
        Scrape a single version's release notes.

        Args:
            version: Version string (e.g., "1.36.0")

        Returns:
            True if successful, False otherwise
        """
        url = version_to_url(version)
        logger.info(f"Scraping version {version}: {url}")

        response = self.get_page(url)
        if not response:
            logger.error(f"Failed to fetch {url}")
            return False

        # Extract main content
        main_html = self.extract_main_content(response.text)
        if not main_html:
            logger.error(f"Failed to extract main content from {url}")
            return False

        # Validate content length
        if len(main_html) < MIN_CONTENT_LENGTH:
            logger.warning(f"Content too short ({len(main_html)} chars) for {url}")
            return False

        # Convert to Markdown
        markdown_content = self.html_to_markdown(main_html)

        # Add header with version and URL
        header = f"# Boost {version} Release Notes\n\n"
        header += f"**Source:** {url}\n\n"
        header += f"**Scraped:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        header += "---\n\n"

        full_content = header + markdown_content

        # Save to file
        filename = version_to_filename(version)
        output_path = Path(OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        logger.info(f"Saved release notes for {version} to {output_path}")

        # Update progress
        if version not in self.progress["scraped_versions"]:
            self.progress["scraped_versions"].append(version)
        self.progress["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')

        return True

    def scrape_list(self, versions: List[str]) -> dict:
        """
        Scrape release notes for a specific list of versions.

        Args:
            versions: List of version strings (e.g., ["1.36.0", "1.37.0", "1.85.0"])

        Returns:
            Dictionary with scraping statistics
        """
        total = len(versions)
        logger.info(f"Starting to scrape {total} versions")

        successful = 0
        failed = 0
        skipped = 0

        start_time = time.time()

        for i, version in enumerate(versions, 1):
            # Check if already scraped
            if version in self.progress["scraped_versions"]:
                logger.info(f"[{i}/{total}] Skipping already scraped version: {version}")
                skipped += 1
                continue

            # Check if file already exists
            filename = version_to_filename(version)
            output_path = Path(OUTPUT_DIR) / filename
            if output_path.exists():
                logger.info(f"[{i}/{total}] File already exists for version: {version}")
                if version not in self.progress["scraped_versions"]:
                    self.progress["scraped_versions"].append(version)
                skipped += 1
                continue

            logger.info(f"[{i}/{total}] Scraping version: {version}")

            if self.scrape_version(version):
                successful += 1
            else:
                failed += 1
                if version not in self.progress["failed_versions"]:
                    self.progress["failed_versions"].append(version)

            # Save progress periodically
            if i % CHECKPOINT_INTERVAL == 0:
                save_progress(PROGRESS_FILE, self.progress)
                logger.info(f"Progress saved: {successful} successful, {failed} failed, {skipped} skipped")

        # Final progress save
        save_progress(PROGRESS_FILE, self.progress)

        elapsed = time.time() - start_time

        stats = {
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "elapsed_time": format_duration(elapsed)
        }

        logger.info(f"Scraping completed: {stats}")

        return stats

    def scrape_range(self, start_version: str = None, end_version: str = None) -> dict:
        """
        Scrape release notes for a range of versions.

        Args:
            start_version: Start version (defaults to START_VERSION from config)
            end_version: End version (defaults to END_VERSION from config)

        Returns:
            Dictionary with scraping statistics
        """
        start_version = start_version or START_VERSION
        end_version = end_version or END_VERSION

        logger.info(f"Starting to scrape versions from {start_version} to {end_version}")

        versions = parse_version_range(start_version, end_version)
        total = len(versions)

        logger.info(f"Found {total} versions to scrape")

        successful = 0
        failed = 0
        skipped = 0

        start_time = time.time()

        for i, version in enumerate(versions, 1):
            # Check if already scraped
            if version in self.progress["scraped_versions"]:
                logger.info(f"[{i}/{total}] Skipping already scraped version: {version}")
                skipped += 1
                continue

            # Check if file already exists
            filename = version_to_filename(version)
            output_path = Path(OUTPUT_DIR) / filename
            if output_path.exists():
                logger.info(f"[{i}/{total}] File already exists for version: {version}")
                if version not in self.progress["scraped_versions"]:
                    self.progress["scraped_versions"].append(version)
                skipped += 1
                continue

            logger.info(f"[{i}/{total}] Scraping version: {version}")

            if self.scrape_version(version):
                successful += 1
            else:
                failed += 1
                if version not in self.progress["failed_versions"]:
                    self.progress["failed_versions"].append(version)

            # Save progress periodically
            if i % CHECKPOINT_INTERVAL == 0:
                save_progress(PROGRESS_FILE, self.progress)
                logger.info(f"Progress saved: {successful} successful, {failed} failed, {skipped} skipped")

        # Final progress save
        save_progress(PROGRESS_FILE, self.progress)

        elapsed = time.time() - start_time

        stats = {
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "elapsed_time": format_duration(elapsed)
        }

        logger.info(f"Scraping completed: {stats}")

        return stats

    def scrape_single(self, version: str) -> bool:
        """
        Scrape a single version (convenience method).

        Args:
            version: Version string (e.g., "1.36.0")

        Returns:
            True if successful, False otherwise
        """
        return self.scrape_version(version)


def main():
    """Main entry point for the scraper."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Boost release notes")
    parser.add_argument("--version", type=str, help="Scrape a single version (e.g., 1.36.0)")
    parser.add_argument("--start", type=str, help="Start version for range scraping")
    parser.add_argument("--end", type=str, help="End version for range scraping")
    parser.add_argument("--list", type=str, nargs="+", help="List of specific versions to scrape (e.g., 1.36.0 1.37.0 1.85.0)")
    parser.add_argument("--delay", type=float, default=RECOMMENDED_DELAY_SECONDS,
                       help=f"Delay between requests (default: {RECOMMENDED_DELAY_SECONDS})")

    args = parser.parse_args()

    scraper = BoostReleaseNoteScraper(delay=args.delay)
    versions = [f"1.{i}.{j}" for i in range(65, 66) for j in range(2)]
    if args.version:
        # Scrape single version
        success = scraper.scrape_single(args.version)
        if success:
            logger.info(f"Successfully scraped version {args.version}")
        else:
            logger.error(f"Failed to scrape version {args.version}")
            exit(1)
    elif args.list:
        # Scrape list of versions
        stats = scraper.scrape_list(args.list)
        logger.info(f"Final statistics: {stats}")
    else:
        # Scrape range
        stats = scraper.scrape_list(versions)
        logger.info(f"Final statistics: {stats}")


if __name__ == "__main__":
    main()

