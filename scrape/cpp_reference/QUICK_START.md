# Quick Start Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure settings:**
   - Edit `config.py` to customize:
     - User-Agent string (identify your project)
     - Rate limiting delays
     - Output directories

## Usage

### Step 1: Test on Small Subset

Before running the full collection, test on a small number of pages:

```python
from scraper import CppReferenceScraper

# Initialize scraper
scraper = CppReferenceScraper(delay=1.5)

# Get a few URLs for testing
urls = scraper.discover_urls_from_sitemap()[:10]  # First 10 URLs

# Scrape test set
scraper.scrape_urls(urls, save_raw=True)
```

### Step 2: Extract Content from Raw HTML

After scraping, extract structured content:

```python
from extractor import process_raw_html_files

# Process all raw HTML files
process_raw_html_files(raw_dir="data/raw", output_dir="data/parsed")
```

### Step 3: Full Collection

Once testing is successful, run full collection:

```bash
python scraper.py
```

This will:
- Discover all URLs from sitemap
- Scrape each page with rate limiting
- Save raw HTML files
- Track progress and allow resuming

### Step 4: Process Extracted Data

After collection completes:

```bash
python extractor.py
```

This processes all raw HTML files and creates structured JSON files.

## Monitoring Progress

- Check `data/progress.json` for current status
- View logs in `data/logs/scraper.log`
- Progress is saved every 100 pages (configurable)

## Resuming Interrupted Collection

The scraper automatically tracks progress. If interrupted:

1. Run `python scraper.py` again
2. It will skip already-visited URLs
3. Continue from where it left off

## Important Notes

⚠️ **Site Maintenance**: The site will be in read-only mode soon. Complete collection before maintenance period.

⚠️ **Rate Limiting**: Default delay is 1.5 seconds. Don't reduce below 1 second.

⚠️ **Legal Compliance**: Ensure you comply with CC-BY-SA 3.0 and GFDL licenses.

## Troubleshooting

**Problem**: Getting 429 (Too Many Requests) errors
- **Solution**: Increase delay in `config.py` (RECOMMENDED_DELAY_SECONDS)

**Problem**: Some pages fail to extract
- **Solution**: Check logs for specific errors, may indicate HTML structure changes

**Problem**: Collection interrupted
- **Solution**: Simply rerun - it will resume from last checkpoint

## Next Steps

After collection:
1. Validate data quality
2. Process and normalize
3. Generate statistics
4. Prepare for chunking/embedding phase

