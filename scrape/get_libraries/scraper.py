"""
Main scraper implementation for Boost libraries list
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import json
from pathlib import Path
from typing import Optional, Set, List, Dict
from urllib.parse import urljoin

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


class BoostLibrariesScraper:
    """
    Scraper for Boost.org libraries list pages.
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

    def extract_libraries_table(self, html: str) -> Optional[BeautifulSoup]:
        """
        Extract the libraries table from HTML.

        Args:
            html: HTML content as string

        Returns:
            BeautifulSoup object of the table or None if not found
        """
        soup = BeautifulSoup(html, 'lxml')

        # Try to find table with class "table-auto w-full"
        table = soup.find('table', class_=SELECTORS["table_class"].split())
        if table:
            logger.debug("Found libraries table")
            return table

        # Fallback: try to find table with either class
        table = soup.find('table', class_='table-auto')
        if table:
            logger.debug("Found table with table-auto class")
            return table

        table = soup.find('table', class_='w-full')
        if table:
            logger.debug("Found table with w-full class")
            return table

        # Last resort: find any table
        table = soup.find('table')
        if table:
            logger.warning("Found generic table (may not be the libraries table)")
            return table

        logger.error("Could not find libraries table")
        return None

    def parse_table_row(self, row) -> Optional[Dict[str, str]]:
        """
        Parse a table row to extract library information.

        Args:
            row: BeautifulSoup row element

        Returns:
            Dictionary with library information or None if invalid
        """
        cells = row.find_all(['td', 'th'])
        if not cells:
            return None

        # Extract text from each cell
        cell_texts = [cell.get_text(strip=True) for cell in cells]

        # Extract links from cells
        links = []
        for cell in cells:
            link = cell.find('a')
            if link:
                href = link.get('href', '')
                # Make absolute URL if relative
                # if href and not href.startswith('http'):
                    # Make absolute URL if relative
                base_url = "https://www.boost.org"
                if href.startswith('/'):
                    href = base_url + href
                elif not href.startswith('http'):
                    # Relative URL, join with base
                    href = urljoin(base_url + '/', href)
                links.append({
                    'text': link.get_text(strip=True),
                    'href': href
                })
            else:
                links.append(None)

        library_info = {}

        # If we have at least one cell, try to extract meaningful data
        if len(cell_texts) >= 5:
            # First cell is often the library name
            library_info['name'] = cell_texts[0] if cell_texts else ''
            if links[0]:
                library_info['name_link'] = links[0]['href']
            library_info["c++_version"] = cell_texts[1]
            library_info['description'] = ' '.join(cell_texts[2:])

        return library_info

    def extract_libraries(self, html: str) -> List[Dict[str, str]]:
        """
        Extract all libraries from the HTML table.

        Args:
            html: HTML content as string

        Returns:
            List of dictionaries containing library information
        """
        table = self.extract_libraries_table(html)
        if not table:
            return []

        libraries = []
        rows = table.find_all('tr')

        # Check if first row is header
        header_row = None
        if rows:
            first_row_cells = rows[0].find_all(['th', 'td'])
            # If first row has 'th' tags, it's likely a header
            if first_row_cells and rows[0].find('th'):
                header_row = rows[0]
                header_texts = [cell.get_text(strip=True) for cell in first_row_cells]
                logger.debug(f"Found header row: {header_texts}")
                rows = rows[1:]  # Skip header row

        for row in rows:
            library_info = self.parse_table_row(row)
            if library_info:
                libraries.append(library_info)

        logger.info(f"Extracted {len(libraries)} libraries from table")
        return libraries

    def scrape_version(self, version: str) -> bool:
        """
        Scrape libraries for a single version.

        Args:
            version: Version string (e.g., "1.36.0")

        Returns:
            True if successful, False otherwise
        """
        url = version_to_url(version)
        logger.info(f"Scraping libraries for version {version}: {url}")

        response = self.get_page(url)
        if not response:
            logger.error(f"Failed to fetch {url}")
            return False

        # Optionally save raw HTML
        if RAW_HTML_DIR:
            raw_filename = version_to_filename(version, "html")
            raw_path = Path(RAW_HTML_DIR) / raw_filename
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.debug(f"Saved raw HTML to {raw_path}")

        # Extract libraries
        libraries = self.extract_libraries(response.text)
        if not libraries:
            logger.warning(f"No libraries found for version {version}")
            return False

        # Prepare output data
        output_data = {
            'version': version,
            'url': url,
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'libraries_count': len(libraries),
            'libraries': libraries
        }

        # Save to JSON file
        filename = version_to_filename(version, "json")
        output_path = Path(OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(libraries)} libraries for version {version} to {output_path}")

        # Update progress
        if version not in self.progress["scraped_versions"]:
            self.progress["scraped_versions"].append(version)
        self.progress["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')

        return True

    def scrape_list(self, versions: List[str]) -> dict:
        """
        Scrape libraries for a specific list of versions.

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
            filename = version_to_filename(version, "json")
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
        Scrape libraries for a range of versions.

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
            filename = version_to_filename(version, "json")
            output_path = Path(OUTPUT_DIR) / filename
            # if output_path.exists():
            #     logger.info(f"[{i}/{total}] File already exists for version: {version}")
            #     if version not in self.progress["scraped_versions"]:
            #         self.progress["scraped_versions"].append(version)
            #     skipped += 1
            #     continue

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

    parser = argparse.ArgumentParser(description="Scrape Boost libraries list")
    parser.add_argument("--version", type=str, help="Scrape a single version (e.g., 1.36.0)")
    parser.add_argument("--start", type=str, help="Start version for range scraping")
    parser.add_argument("--end", type=str, help="End version for range scraping")
    parser.add_argument("--list", type=str, nargs="+", help="List of specific versions to scrape (e.g., 1.36.0 1.37.0 1.85.0)")
    parser.add_argument("--delay", type=float, default=RECOMMENDED_DELAY_SECONDS,
                       help=f"Delay between requests (default: {RECOMMENDED_DELAY_SECONDS})")

    args = parser.parse_args()

    scraper = BoostLibrariesScraper(delay=args.delay)

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
        stats = scraper.scrape_range(
            start_version=args.start,
            end_version=args.end
        )
        logger.info(f"Final statistics: {stats}")


if __name__ == "__main__":
    main()

