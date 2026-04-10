"""
Script to process multilingual HTML files and prepare for RAG database.

This script demonstrates how to:
1. Extract content from both English and Chinese HTML files
2. Process them with language metadata
3. Prepare for chunking and embedding generation
"""

import logging
from pathlib import Path
from extractor import process_raw_html_files, CppReferenceExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main processing function."""
    logger.info("Starting multilingual HTML processing...")
    
    # Process both English and Chinese HTML files
    # This will automatically detect and process:
    # - data/raw/cppreference/ (English)
    # - data/raw/cn/cppreference/ (Chinese)
    
    process_raw_html_files(
        raw_dirs=None,  # Auto-detect directories
        output_dir="data/parsed",
        language_mapping={
            "cppreference": "en",
            "cn/cppreference": "zh"
        }
    )
    
    logger.info("Processing complete!")
    logger.info("Extracted JSON files are saved in:")
    logger.info("  - data/parsed/en/ (English documents)")
    logger.info("  - data/parsed/zh/ (Chinese documents)")


if __name__ == "__main__":
    main()

