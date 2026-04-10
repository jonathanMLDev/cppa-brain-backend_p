# Boost Libraries Scraper

This project scrapes the list of Boost libraries from Boost.org libraries list pages and extracts information from the libraries table.

## Features

- Scrapes libraries list from URLs like `https://www.boost.org/libraries/1.xx.x/list/`
- Extracts data from `<table class="table-auto w-full">` elements
- Saves library information as JSON files to `data/libraries/`
- Progress tracking and resumable scraping
- Rate limiting and retry logic
- Optional raw HTML saving

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Scrape a single version:
```bash
python scraper.py --version 1.75.0
```

### Scrape a range of versions:
```bash
python scraper.py --start 1.36.0 --end 1.90.0
```

### Scrape a specific list of versions:
```bash
python scraper.py --list 1.75.0 1.80.0 1.85.0
```

### Scrape with custom delay:
```bash
python scraper.py --start 1.36.0 --end 1.90.0 --delay 3.0
```

### Using as a Python module:
```python
from scraper import BoostLibrariesScraper

scraper = BoostLibrariesScraper()

# Scrape single version
scraper.scrape_single("1.75.0")

# Scrape range
stats = scraper.scrape_range("1.36.0", "1.90.0")
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

JSON files are saved to `data/libraries/` with naming format:
- `1_75_0.json` for version 1.75.0
- `1_90_0.json` for version 1.90.0
- etc.

Each JSON file contains:
- Version information
- Source URL
- Scraped timestamp
- Libraries count
- Array of libraries with:
  - Library name
  - Links (if available)
  - Description/cells data
  - Raw cell data

Example structure:
```json
{
  "version": "1.75.0",
  "url": "https://www.boost.org/libraries/1.75.0/list/",
  "scraped_at": "2025-12-13 10:00:00",
  "libraries_count": 150,
  "libraries": [
    {
      "name": "JSON",
      "name_link": "https://www.boost.org/libs/json/",
      "description": "...",
      "cells": ["JSON", "..."],
      "links": [...]
    },
    ...
  ]
}
```

Raw HTML files (optional) are saved to `data/libraries/raw/` if enabled in config.

## Progress Tracking

Progress is saved to `data/progress_libraries.json` and includes:
- List of successfully scraped versions
- List of failed versions
- Last update timestamp

The scraper automatically skips already-scraped versions on subsequent runs.

## Logging

Logs are written to `data/logs/libraries_scraper.log` and also displayed in the console.

## Notes

- The scraper respects rate limits to avoid overloading the server
- Failed requests are automatically retried with exponential backoff
- The scraper extracts data from table rows, identifying library names, links, and descriptions
- The scraper can be interrupted and resumed - it will skip already-scraped versions
- Table structure may vary between versions, but the scraper attempts to handle common patterns

