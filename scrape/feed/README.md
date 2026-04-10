# Feed Scraper

Scrapes RSS/Atom feeds from given URLs using [feedparser](https://feedparser.readthedocs.io/), then writes each feed (metadata + entries) to a JSON file.

## Features

- Fetches any RSS or Atom feed URL
- Converts feed and entries to JSON-serializable data (dates as ISO 8601 strings)
- Saves one JSON file per feed under `data/feed/` (or a custom output dir)
- Rate limiting between requests
- Optional config list of default feed URLs

## Installation

From the project root or from `scrape/feed`:

```bash
pip install -r requirements.txt
```

## Usage

### Command line

Run from `scrape/feed` (so `config` and `utils` resolve):

```bash
cd scrape/feed
python scraper.py
```

Use config default URLs (`config.FEED_URLS`):

```bash
python scraper.py
```

Scrape specific URLs:

```bash
python scraper.py "https://www.boost.org/feed/" "https://isocpp.org/feed"
```

Custom output directory:

```bash
python scraper.py -o data/my_feeds "https://example.com/feed.xml"
```

### As a module

```python
from pathlib import Path
from scraper import scrape_feed, scrape_feeds

# Single feed
data = scrape_feed("https://www.boost.org/feed/")
# Writes data/feed/<title_or_url_base>.json

# Multiple feeds (uses config.FEED_URLS if urls is None)
results = scrape_feeds(
    urls=["https://example.com/feed.xml"],
    output_dir=Path("data/feed"),
)
```

## Configuration

Edit `config.py`:

- **OUTPUT_DIR** – Directory for JSON files (default: `data/feed`)
- **REQUEST_DELAY** – Seconds between feed requests (default: `1.0`)
- **REQUEST_TIMEOUT** – Request timeout in seconds (default: `30`)
- **USER_AGENT** – User-Agent header sent with requests
- **FEED_URLS** – Default list of feed URLs when none are passed on the CLI

## Output format

Each JSON file contains:

- **feed_url** – URL that was fetched
- **bozo** – Whether the feed had parse errors
- **bozo_exception** – Parse error message if any
- **feed** – Feed-level metadata (title, link, description, etc.)
- **entries** – List of entries (title, link, published, summary, content, etc.)

Dates (e.g. `published_parsed`, `updated_parsed`) are converted to ISO 8601 strings. Raw HTML in summaries or content is kept as-is in the JSON.

## File naming

- If the feed has a **title**, the file is named from a sanitized version of it (e.g. `Boost_News.json`).
- Otherwise the filename is derived from the **URL** (e.g. `www_boost_org_feed.json`).
