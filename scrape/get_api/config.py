"""
Configuration for get_api (WordPress REST API and similar JSON APIs).
"""

# Output
OUTPUT_DIR = "data/blog-posts/Eric Niebler"
# Saved JSON: one file per API URL (sanitized name) or per run

# Request
REQUEST_TIMEOUT = 30  # seconds
REQUEST_DELAY = 0.5  # seconds between page requests (pagination)
USER_AGENT = "CppCopilotBot/1.0 (+https://github.com/yourorg/cpp-copilot)"

# WordPress REST API defaults (can override via CLI)
DEFAULT_PER_PAGE = 100
DEFAULT_MAX_PAGES = None  # None = fetch all pages until empty

# Example API URL (WordPress posts)
# "https://www.fluentcpp.com/wp-json/wp/v2/posts?per_page=2&page=1"
API_URLS = [
    "https://ericniebler.com/wp-json/wp/v2/posts",
]

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
