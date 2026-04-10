"""
Configuration settings for cppreference.com scraper
"""

# Base URL
BASE_URL = "https://cppreference.tw/w/"

# Rate Limiting
MIN_DELAY_SECONDS = 1.0
RECOMMENDED_DELAY_SECONDS = 1.5
MAX_DELAY_SECONDS = 2.0

# User-Agent
USER_AGENT = "CppCopilotBot/1.0 (+https://github.com/yourorg/cpp-copilot)"

# Request Settings
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0  # Exponential backoff multiplier

# Output Directories
OUTPUT_DIR = "data"
RAW_DIR = "data/blog-posts/Jonathan Boccara"
# Subdirs under RAW_DIR for scraped content (HTML and Markdown)
RAW_HTML_DIR = f"{RAW_DIR}/html"
RAW_MD_DIR = f"{RAW_DIR}/md"
PARSED_JSON_DIR = "data/parsed"
LOGS_DIR = "data/logs"

# Progress Tracking
PROGRESS_FILE = "data/progress.json"
CHECKPOINT_INTERVAL = 100  # Save progress every N pages

# Sitemap (NOT AVAILABLE - returns 404)
# SITEMAP_URL = "https://en.cppreference.com/w/sitemap.xml"  # Does not exist

# MediaWiki API (Primary discovery method)
MEDIAWIKI_API_URL = "https://en.cppreference.com/w/api.php"

# Index Pages (for index-based discovery)
INDEX_PAGES = [
    "https://www.fluentcpp.com/",
]

# HTML Selectors
SELECTORS = {
    "main_content": "#mw-content-text",
    "title": "h1.firstHeading",
    "code_blocks": ["pre.programlisting", "pre.t-dcl"],
    "tables": ["table.t-dcl-begin", "table.t-dcl"],
    "version_markers": "span.t-mark-rev",
    "links": "a[href^='/w/cpp/']",
}

# Data Validation
MIN_CONTENT_LENGTH = 50  # Minimum characters for valid page
MIN_CODE_BLOCK_LENGTH = 10  # Minimum characters for valid code block

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "data/logs/scraper.log"
