"""
Configuration settings for Boost release notes scraper
"""

# Base URL pattern
BASE_URL_PATTERN = "https://www.boost.org/releases/{version}/"

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
OUTPUT_DIR = "data/release_note"
RAW_HTML_DIR = "data/release_note"  # Optional: save raw HTML too

# Progress Tracking
PROGRESS_FILE = "data/progress_release_notes.json"
CHECKPOINT_INTERVAL = 10  # Save progress every N pages

# HTML Selectors
SELECTORS = {
    "main_content": "main",
    "fallback_content": "section.content",  # Fallback if main tag not found
}

# Data Validation
MIN_CONTENT_LENGTH = 100  # Minimum characters for valid page

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "data/logs/release_note_scraper.log"

# Version range to scrape (can be customized)
# Format: major.minor.patch (e.g., "1.36.0")
# Will scrape from START_VERSION to END_VERSION
START_VERSION = "1.36.0"
END_VERSION = "1.85.0"  # Update as needed

