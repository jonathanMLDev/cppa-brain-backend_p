"""
Configuration settings for Boost libraries scraper
"""

# Base URL pattern
BASE_URL_PATTERN = "https://www.boost.org/libraries/{version}/list/"

# Rate Limiting
MIN_DELAY_SECONDS = 1.0
RECOMMENDED_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 3.0

# User-Agent
USER_AGENT = "CppCopilotBot/1.0 (+https://github.com/yourorg/cpp-copilot)"

# Request Settings
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0  # Exponential backoff multiplier

# Output Directories
OUTPUT_DIR = "data/libraries"
RAW_HTML_DIR = "data/libraries/raw"  # Optional: save raw HTML too

# Progress Tracking
PROGRESS_FILE = "data/progress_libraries.json"
CHECKPOINT_INTERVAL = 10  # Save progress every N pages

# HTML Selectors
SELECTORS = {
    "libraries_table": "table.table-auto.w-full",
    "table_class": "table-auto w-full",
}

# Data Validation
MIN_LIBRARIES_COUNT = 1  # Minimum number of libraries expected

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "data/logs/libraries_scraper.log"

# Version range to scrape (can be customized)
# Format: major.minor.patch (e.g., "1.36.0")
# Will scrape from START_VERSION to END_VERSION
START_VERSION = "1.16.0"
END_VERSION = "1.90.0"  # Update as needed

