"""
Configuration for feed scraper (RSS/Atom via feedparser).
"""

# Output
OUTPUT_DIR = "data/blog-posts/Scott Meyers"
# Filename for a single feed: {sanitized_feed_name}.json or {url_hash}.json

# HTML to Markdown conversion
CONVERT_HTML_TO_MARKDOWN = True  # Set to False to keep original HTML

# Rate limiting (seconds between feed requests)
REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30  # seconds

# User-Agent (some feeds require a proper UA)
USER_AGENT = "CppCopilotFeed/1.0 (+https://github.com/yourorg/cpp-copilot)"

# Optional: list of feed URLs to scrape by default (can override via CLI)
FEED_URLS = [
    f"https://scottmeyers.blogspot.com/feeds/posts/default?start-index={start_index}&max-results=100"
    for start_index in range(1, 500, 100)
]


# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
