"""
Utility script to discover and verify the correct sitemap URL for cppreference.com
"""

import requests
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

BASE_URL = "https://en.cppreference.com"


def check_robots_txt(base_url: str = BASE_URL) -> list:
    """
    Check robots.txt for sitemap declaration.
    
    Args:
        base_url: Base URL of the site
        
    Returns:
        List of sitemap URLs found in robots.txt
    """
    robots_url = urljoin(base_url, "/robots.txt")
    sitemaps = []
    
    try:
        response = requests.get(robots_url, timeout=10)
        response.raise_for_status()
        
        print(f"[OK] Successfully fetched robots.txt from {robots_url}")
        print("\nrobots.txt content:")
        print("-" * 60)
        print(response.text)
        print("-" * 60)
        
        # Parse robots.txt for Sitemap declarations
        for line in response.text.split('\n'):
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                sitemaps.append(sitemap_url)
                print(f"\n[OK] Found sitemap in robots.txt: {sitemap_url}")
        
        if not sitemaps:
            print("\n[WARNING] No Sitemap declaration found in robots.txt")
        
    except Exception as e:
        print(f"[ERROR] Error fetching robots.txt: {e}")
    
    return sitemaps


def try_common_sitemap_locations(base_url: str = BASE_URL) -> list:
    """
    Try common sitemap URL locations.
    
    Args:
        base_url: Base URL of the site
        
    Returns:
        List of working sitemap URLs
    """
    common_paths = [
        "/sitemap.xml",
        "/w/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemaps/sitemap.xml",
    ]
    
    working_sitemaps = []
    
    print("\nTrying common sitemap locations:")
    print("-" * 60)
    
    for path in common_paths:
        sitemap_url = urljoin(base_url, path)
        try:
            response = requests.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                # Check if it's valid XML
                try:
                    ET.fromstring(response.content)
                    working_sitemaps.append(sitemap_url)
                    print(f"[OK] Found working sitemap: {sitemap_url}")
                except ET.ParseError:
                    print(f"[FAIL] {sitemap_url} - Not valid XML")
            else:
                print(f"[FAIL] {sitemap_url} - HTTP {response.status_code}")
        except Exception as e:
            print(f"[FAIL] {sitemap_url} - Error: {e}")
    
    return working_sitemaps


def verify_sitemap(sitemap_url: str) -> dict:
    """
    Verify a sitemap URL and get statistics.
    
    Args:
        sitemap_url: URL to verify
        
    Returns:
        Dictionary with verification results
    """
    result = {
        'url': sitemap_url,
        'accessible': False,
        'valid_xml': False,
        'total_urls': 0,
        'cpp_urls': 0,
        'error': None
    }
    
    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
        result['accessible'] = True
        
        # Try to parse as XML
        try:
            root = ET.fromstring(response.content)
            result['valid_xml'] = True
            
            # Count URLs
            namespace = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = root.findall('.//sitemap:loc', namespace)
            result['total_urls'] = len(urls)
            
            # Count C++ related URLs
            cpp_urls = [url for url in urls if url.text and '/w/cpp/' in url.text]
            result['cpp_urls'] = len(cpp_urls)
            
            print(f"\n[OK] Sitemap verification successful!")
            print(f"  Total URLs: {result['total_urls']}")
            print(f"  C++ URLs: {result['cpp_urls']}")
            
            # Show sample URLs
            if cpp_urls:
                print(f"\n  Sample C++ URLs (first 5):")
                for url_elem in cpp_urls[:5]:
                    print(f"    - {url_elem.text}")
            
        except ET.ParseError as e:
            result['error'] = f"Invalid XML: {e}"
            print(f"[ERROR] Sitemap is not valid XML: {e}")
    
    except requests.RequestException as e:
        result['error'] = str(e)
        print(f"[ERROR] Cannot access sitemap: {e}")
    
    return result


def check_html_meta(base_url: str = BASE_URL) -> list:
    """
    Check HTML meta tags for sitemap references (less common).
    
    Args:
        base_url: Base URL of the site
        
    Returns:
        List of sitemap URLs found
    """
    sitemaps = []
    
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for sitemap in meta tags or links
        for link in soup.find_all('link', rel='alternate'):
            if 'sitemap' in link.get('type', '').lower():
                href = link.get('href')
                if href:
                    sitemap_url = urljoin(base_url, href)
                    sitemaps.append(sitemap_url)
                    print(f"[OK] Found sitemap in HTML: {sitemap_url}")
    
    except Exception as e:
        print(f"[ERROR] Error checking HTML: {e}")
    
    return sitemaps


def main():
    """Main function to discover sitemap URL."""
    print("=" * 60)
    print("cppreference.com Sitemap Discovery Tool")
    print("=" * 60)
    
    # Method 1: Check robots.txt
    print("\n[Method 1] Checking robots.txt...")
    robots_sitemaps = check_robots_txt()
    
    # Method 2: Try common locations
    print("\n[Method 2] Trying common sitemap locations...")
    common_sitemaps = try_common_sitemap_locations()
    
    # Method 3: Check HTML meta
    print("\n[Method 3] Checking HTML meta tags...")
    html_sitemaps = check_html_meta()
    
    # Combine all found sitemaps
    all_sitemaps = list(set(robots_sitemaps + common_sitemaps + html_sitemaps))
    
    # Verify each sitemap
    print("\n" + "=" * 60)
    print("Verification Results")
    print("=" * 60)
    
    if not all_sitemaps:
        print("\n[WARNING] No sitemaps found using standard methods.")
        print("\nTrying the configured URL from config.py...")
        configured_url = "https://en.cppreference.com/w/sitemap.xml"
        verify_sitemap(configured_url)
    else:
        for sitemap_url in all_sitemaps:
            print(f"\nVerifying: {sitemap_url}")
            result = verify_sitemap(sitemap_url)
            
            if result['accessible'] and result['valid_xml']:
                print(f"\n[SUCCESS] RECOMMENDED SITEMAP_URL: {sitemap_url}")
                print(f"   Use this in config.py: SITEMAP_URL = \"{sitemap_url}\"")


if __name__ == "__main__":
    main()

