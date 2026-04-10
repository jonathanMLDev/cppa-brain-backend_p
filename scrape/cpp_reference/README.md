# cppreference.com Scraper

This project collects C++ reference documentation from cppreference.com live site.

## Overview

Since the official offline archives are blocked, this scraper collects data directly from the live website at https://en.cppreference.com/w/

## Project Structure

```
scrape/cpp_reference/
├── README.md                  # This file
├── DATA_COLLECTION_REPORT.md  # Comprehensive collection strategy report
├── scraper.py                 # Main scraper implementation (to be created)
├── extractor.py               # Content extraction logic (to be created)
├── utils.py                   # Utility functions (to be created)
├── config.py                  # Configuration settings (to be created)
├── requirements.txt           # Python dependencies (to be created)
└── data/                      # Collected data
    ├── raw/                   # Raw HTML files
    ├── parsed/                # Extracted JSON files
    └── logs/                  # Scraping logs
```

## Quick Start

1. **Read the Report**: Review `DATA_COLLECTION_REPORT.md` for detailed strategy
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Configure**: Update `config.py` with your settings
4. **Test**: Run scraper on small subset first
5. **Collect**: Begin full collection

## Important Notes

⚠️ **Site Maintenance**: The site will be in read-only mode in the next few weeks (as of March 30, 2025). Plan collection accordingly.

## License

Respect cppreference.com's license (CC-BY-SA 3.0 and GFDL). See `DATA_COLLECTION_REPORT.md` for details.

