# Boost Release Notes Scraper

This project scrapes release notes from Boost.org release pages and converts them to Markdown format.

## Features

- Scrapes release notes from URLs like `https://www.boost.org/releases/1.xx.x/`
- Extracts content from `<main>` tag (with fallback to other selectors)
- Converts HTML to Markdown format
- Saves Markdown files to `data/release_note/`
- Progress tracking and resumable scraping
- Rate limiting and retry logic

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Scrape a single version:
```bash
python scraper.py --version 1.36.0
```

### Scrape a range of versions:
```bash
python scraper.py --start 1.36.0 --end 1.85.0
```

### Scrape a specific list of versions:
```bash
python scraper.py --list 1.36.0 1.37.0 1.85.0
```

### Scrape with custom delay:
```bash
python scraper.py --start 1.36.0 --end 1.85.0 --delay 3.0
```

### Using as a Python module:
```python
from scraper import BoostReleaseNoteScraper

scraper = BoostReleaseNoteScraper()

# Scrape single version
scraper.scrape_single("1.36.0")

# Scrape range
stats = scraper.scrape_range("1.36.0", "1.85.0")
print(stats)
```

## Configuration

Edit `config.py` to customize:
- Version range (START_VERSION, END_VERSION)
- Rate limiting delays
- Output directory
- HTML selectors
- Logging settings

## Output

Markdown files are saved to `data/release_note/` with naming format:
- `1_36_0.md` for version 1.36.0
- `1_85_0.md` for version 1.85.0
- etc.

Each file includes:
- Header with version and source URL
- Scraped timestamp
- Full release notes content in Markdown format

## Progress Tracking

Progress is saved to `data/progress_release_notes.json` and includes:
- List of successfully scraped versions
- List of failed versions
- Last update timestamp

The scraper automatically skips already-scraped versions on subsequent runs.

## Logging

Logs are written to `data/logs/release_note_scraper.log` and also displayed in the console.

## Notes

- The scraper respects rate limits to avoid overloading the server
- Failed requests are automatically retried with exponential backoff
- If a `<main>` tag is not found, the scraper falls back to other content selectors
- The scraper can be interrupted and resumed - it will skip already-scraped versions

