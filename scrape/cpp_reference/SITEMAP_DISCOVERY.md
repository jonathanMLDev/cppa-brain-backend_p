# Sitemap URL Discovery for cppreference.com

## Current Status

**⚠️ Important Finding**: The standard sitemap URL (`https://en.cppreference.com/w/sitemap.xml`) returns **404 Not Found**.

This means cppreference.com does **not** provide a standard XML sitemap file.

## Discovery Results

### Method 1: robots.txt
- **URL**: `https://en.cppreference.com/robots.txt`
- **Result**: ✅ Accessible, but **no Sitemap declaration**
- **Content**: Permissive (allows all crawlers)

### Method 2: Common Sitemap Locations
All tested locations return **404**:
- ❌ `https://en.cppreference.com/sitemap.xml`
- ❌ `https://en.cppreference.com/w/sitemap.xml`
- ❌ `https://en.cppreference.com/sitemap_index.xml`
- ❌ `https://en.cppreference.com/sitemaps/sitemap.xml`

### Method 3: HTML Meta Tags
- **Result**: No sitemap references found

## Why No Sitemap?

cppreference.com is built on **MediaWiki**, which:
- May not generate standard sitemap.xml files by default
- Uses special: pages for exports
- May require special extensions for sitemap generation

## Alternative URL Discovery Methods

Since there's no sitemap, you have these options:

### Option 1: MediaWiki Special Pages (Recommended)

MediaWiki provides special pages that can list all pages:

1. **All Pages**: `https://en.cppreference.com/w/Special:AllPages`
2. **Export**: `https://en.cppreference.com/w/Special:Export`
3. **Recent Changes**: `https://en.cppreference.com/w/Special:RecentChanges`

**Implementation Strategy:**
```python
# Use Special:AllPages to get page list
special_pages = [
    "https://en.cppreference.com/w/Special:AllPages",
    "https://en.cppreference.com/w/Special:AllPages?from=vector",  # Paginated
]
```

### Option 2: Index-Based Discovery (Current Fallback)

The scraper already implements this as a fallback:
- Start from main index pages
- Follow links recursively
- Extract all `/w/cpp/` URLs

**Pros:**
- Works reliably
- No special endpoints needed

**Cons:**
- Slower (requires many requests)
- May miss some pages

### Option 3: Category Pages

MediaWiki organizes content by categories:
- `https://en.cppreference.com/w/Category:Cpp`
- `https://en.cppreference.com/w/Category:Cpp_reference`

**Implementation:**
```python
category_pages = [
    "https://en.cppreference.com/w/Category:Cpp",
    "https://en.cppreference.com/w/Category:Cpp_reference",
]
```

### Option 4: API-Based Discovery

MediaWiki provides an API that can list all pages:

**API Endpoint**: `https://en.cppreference.com/w/api.php`

**Example Query:**
```
https://en.cppreference.com/w/api.php?action=query&list=allpages&aplimit=500&apnamespace=0
```

This returns JSON with all page titles, which can be converted to URLs.

## Recommended Solution

Since there's no sitemap, **update the scraper to use MediaWiki API or Special:AllPages**:

### Using MediaWiki API

```python
def discover_urls_from_api(self) -> List[str]:
    """Discover URLs using MediaWiki API."""
    api_url = "https://en.cppreference.com/w/api.php"
    urls = []
    continue_token = None
    
    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'aplimit': 500,  # Max per request
            'apnamespace': 0,  # Main namespace
            'format': 'json'
        }
        
        if continue_token:
            params['apcontinue'] = continue_token
        
        response = self.session.get(api_url, params=params)
        data = response.json()
        
        # Extract page titles
        pages = data.get('query', {}).get('allpages', [])
        for page in pages:
            title = page['title']
            # Convert to URL
            url = f"https://en.cppreference.com/w/{title.replace(' ', '_')}"
            if '/w/cpp/' in url or url.endswith('/cpp'):
                urls.append(url)
        
        # Check for continuation
        if 'continue' in data:
            continue_token = data['continue']['apcontinue']
        else:
            break
    
    return urls
```

### Using Special:AllPages

```python
def discover_urls_from_special_pages(self) -> List[str]:
    """Discover URLs from Special:AllPages."""
    base_url = "https://en.cppreference.com/w/Special:AllPages"
    urls = []
    
    # Special:AllPages is paginated
    # Need to parse HTML and follow "next" links
    # Extract links from <ul class="mw-allpages-chunk">
    
    # Implementation would parse HTML and extract page links
    return urls
```

## Updated Configuration

Since sitemap doesn't exist, update `config.py`:

```python
# Sitemap (NOT AVAILABLE - returns 404)
# SITEMAP_URL = "https://en.cppreference.com/w/sitemap.xml"  # Does not exist

# MediaWiki API (Alternative)
MEDIAWIKI_API_URL = "https://en.cppreference.com/w/api.php"

# Special Pages (Alternative)
SPECIAL_ALL_PAGES_URL = "https://en.cppreference.com/w/Special:AllPages"
```

## Conclusion

**The sitemap URL in config.py is incorrect** - it doesn't exist on cppreference.com.

**Recommended Action:**
1. Remove or comment out sitemap-based discovery
2. Implement MediaWiki API-based discovery (most reliable)
3. Keep index-based discovery as fallback
4. Update scraper to use API method first

## Next Steps

1. Implement `discover_urls_from_api()` method
2. Update `main()` to try API first, then index-based
3. Test with small subset
4. Run full collection


