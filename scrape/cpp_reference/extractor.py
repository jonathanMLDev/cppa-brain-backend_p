"""
Content extraction logic for cppreference.com pages
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from urllib.parse import urlparse

from config import SELECTORS, MIN_CONTENT_LENGTH, MIN_CODE_BLOCK_LENGTH
from utils import url_to_filename

logger = logging.getLogger(__name__)


class CppReferenceExtractor:
    """
    Extracts structured content from cppreference.com HTML pages.
    """
    
    def __init__(self):
        """Initialize extractor."""
    
    def extract(self, html: str, url: str, language: str = None) -> Optional[Dict]:
        """
        Extract content from HTML.
        
        Args:
            html: HTML content
            url: Source URL
            language: Language code ('en' or 'zh') - auto-detected if None
            
        Returns:
            Dictionary with extracted content or None if extraction failed
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Auto-detect language if not provided
            if language is None:
                html_tag = soup.find('html')
                if html_tag:
                    lang_attr = html_tag.get('lang', '')
                    if 'zh' in lang_attr.lower():
                        language = 'zh'
                    else:
                        language = 'en'
                else:
                    # Fallback: detect from URL or filename
                    if '/cn/' in url or 'cppreference.tw' in url:
                        language = 'zh'
                    else:
                        language = 'en'
            
            # Extract main content
            content_div = soup.find('div', id='mw-content-text')
            if not content_div:
                logger.warning(f"No main content found for {url}")
                return None
            
            # Extract title
            title_elem = soup.find('h1', class_='firstHeading')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Extract code blocks
            code_blocks = self._extract_code_blocks(content_div)
            
            # Extract tables
            tables = self._extract_tables(content_div)
            
            # Extract version information
            versions = self._extract_versions(content_div)
            
            # Extract function/class signatures
            signatures = self._extract_signatures(content_div)
            
            # Extract "Since C++XX" information
            since_info = self._extract_since_info(content_div)
            
            # Extract categories/tags
            categories = self._extract_categories(content_div)
            
            # Extract cross-references
            cross_refs = self._extract_cross_references(content_div)
            
            # Clean and extract text content
            text_content = self._extract_text_content(content_div)
            
            # Validate minimum content
            if len(text_content) < MIN_CONTENT_LENGTH:
                logger.warning(f"Content too short for {url}: {len(text_content)} chars")
                return None
            
            # Build result
            result = {
                'title': title,
                'url': url,
                'language': language,  # Add language metadata
                'text': text_content,
                'code_blocks': code_blocks,
                'tables': tables,
                'signatures': signatures,
                'versions': sorted(list(versions)),
                'since_info': since_info,
                'categories': list(set(categories)),
                'cross_references': cross_refs,
                'extracted_at': datetime.now().isoformat(),
                'code_block_count': len(code_blocks),
                'table_count': len(tables),
                'text_length': len(text_content)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    def _extract_code_blocks(self, content: Tag) -> List[str]:
        """Extract code blocks from content."""
        code_blocks = []
        
        for selector in SELECTORS['code_blocks']:
            for pre in content.find_all('pre', class_=selector.split('.')[1] if '.' in selector else None):
                code = pre.get_text()
                # Clean up code
                code = re.sub(r'\s+', ' ', code).strip()
                if len(code) >= MIN_CODE_BLOCK_LENGTH:
                    code_blocks.append(code)
        
        return code_blocks
    
    def _extract_tables(self, content: Tag) -> List[str]:
        """Extract tables from content."""
        tables = []
        
        for selector in SELECTORS['tables']:
            for table in content.find_all('table', class_=selector.split('.')[1] if '.' in selector else None):
                table_text = self._table_to_text(table)
                if table_text:
                    tables.append(table_text)
        
        return tables
    
    def _table_to_text(self, table: Tag) -> str:
        """Convert HTML table to readable text format."""
        rows = []
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                rows.append(' | '.join(cells))
        return '\n'.join(rows)
    
    def _extract_versions(self, content: Tag) -> set:
        """Extract C++ version information."""
        versions = set()
        
        # Find version markers
        for span in content.find_all('span', class_=lambda x: x and 't-mark-cpp' in str(x)):
            classes = span.get('class', [])
            for cls in classes:
                if 't-mark-cpp' in cls:
                    version = cls.replace('t-mark-', '')
                    versions.add(version)
        
        return versions
    
    def _extract_signatures(self, content: Tag) -> List[str]:
        """Extract function/class signatures."""
        signatures = []
        
        for code_elem in content.find_all('code', class_='t-dcl'):
            sig = code_elem.get_text(strip=True)
            # Likely a function or template if contains parentheses or angle brackets
            if '(' in sig or '<' in sig:
                signatures.append(sig)
        
        return signatures
    
    def _extract_since_info(self, content: Tag) -> List[str]:
        """Extract 'Since C++XX' information (supports both English and Chinese)."""
        since_info = []
        
        # English pattern
        pattern_en = re.compile(r'Since C\+\+\d+')
        # Chinese pattern (自 C++XX 起)
        pattern_zh = re.compile(r'自 C\+\+\d+')
        
        for elem in content.find_all(['span', 'td']):
            text = elem.get_text(strip=True)
            if pattern_en.search(text) or pattern_zh.search(text):
                since_info.append(text)
        
        return since_info
    
    def _extract_categories(self, content: Tag) -> List[str]:
        """Extract categories/tags from links."""
        categories = []
        
        for link in content.find_all('a', href=re.compile(r'/w/cpp/(\w+)')):
            category = link.get_text(strip=True)
            if category:
                categories.append(category)
        
        return categories
    
    def _extract_cross_references(self, content: Tag) -> List[str]:
        """Extract cross-references to other cppreference pages."""
        cross_refs = []
        
        for link in content.find_all('a', href=re.compile(r'/w/cpp/')):
            href = link.get('href', '')
            if href:
                # Normalize to relative path
                if href.startswith('/w/cpp/'):
                    cross_refs.append(href)
                elif href.startswith('http'):
                    # Extract path from full URL
                    parsed = urlparse(href)
                    if '/w/cpp/' in parsed.path:
                        cross_refs.append(parsed.path)
        
        return list(set(cross_refs))  # Remove duplicates
    
    def _extract_text_content(self, content: Tag) -> str:
        """Extract and clean text content."""
        # Remove script and style elements
        for elem in content.find_all(['script', 'style', 'nav', 'aside']):
            elem.decompose()
        
        # Get text content
        text = content.get_text(separator='\n', strip=True)
        
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text.strip()
    
    def save_extracted(self, data: Dict, output_dir: str = "data/parsed"):
        """
        Save extracted data to JSON file.
        
        Args:
            data: Extracted data dictionary
            output_dir: Output directory
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        filename = url_to_filename(data['url'])
        filepath = Path(output_dir) / f"{filename}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved extracted data: {filepath}")


def process_raw_html_files(
    raw_dirs: List[str] = None, 
    output_dir: str = "data/parsed",
    language_mapping: Dict[str, str] = None
):
    """
    Process all raw HTML files from multiple language directories.
    
    Args:
        raw_dirs: List of directories to process, or None for auto-detection
        output_dir: Directory to save extracted JSON files
        language_mapping: Dict mapping directory paths to language codes
    """
    if raw_dirs is None:
        # Auto-detect directories
        base_path = Path("data/raw")
        raw_dirs = []
        if (base_path / "cppreference").exists():
            raw_dirs.append(str(base_path / "cppreference"))
        if (base_path / "cn" / "cppreference").exists():
            raw_dirs.append(str(base_path / "cn" / "cppreference"))
    
    if language_mapping is None:
        language_mapping = {
            "cppreference": "en",
            "cn/cppreference": "zh"
        }
    
    extractor = CppReferenceExtractor()
    processed_total = 0
    failed_total = 0
    
    for raw_dir in raw_dirs:
        # Determine language from path
        language = "en"  # default
        for key, lang in language_mapping.items():
            if key in raw_dir.replace("\\", "/"):
                language = lang
                break
        
        raw_path = Path(raw_dir)
        # Use rglob to find all HTML files recursively
        html_files = list(raw_path.rglob("*.html"))
        total = len(html_files)
        
        logger.info(f"Processing {total} HTML files from {raw_dir} (language: {language})...")
        
        processed = 0
        failed = 0
        
        for i, html_file in enumerate(html_files, 1):
            try:
                # Read HTML
                with open(html_file, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                # Reconstruct URL based on language
                # Remove the directory path to get relative filename
                rel_path = html_file.relative_to(raw_path)
                filename_stem = rel_path.stem
                
                if language == 'zh':
                    url = f"https://cppreference.tw/w/{filename_stem.replace('_', '/')}"
                else:
                    url = f"https://en.cppreference.com/w/{filename_stem.replace('_', '/')}"
                
                # Extract content with language
                data = extractor.extract(html, url, language=language)
                
                if data:
                    # Save to language-specific subdirectory
                    lang_output_dir = Path(output_dir) / language
                    extractor.save_extracted(data, str(lang_output_dir))
                    processed += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to extract content from {html_file}")
                
                if i % 100 == 0:
                    logger.info(f"Processed {i}/{total} files ({processed} successful, {failed} failed)")
            
            except Exception as e:
                logger.error(f"Error processing {html_file}: {e}")
                failed += 1
        
        processed_total += processed
        failed_total += failed
        logger.info(f"Completed {raw_dir}: {processed} successful, {failed} failed")
    
    logger.info(f"Total processing complete: {processed_total} successful, {failed_total} failed")


if __name__ == "__main__":
    # Process raw HTML files from both English and Chinese directories
    process_raw_html_files()

