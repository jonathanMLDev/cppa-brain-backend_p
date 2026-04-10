# Action Plan: What to Do When Sitemap is Not Found

## ✅ Completed Actions

### 1. **Updated Configuration** (`config.py`)
- Commented out the non-existent `SITEMAP_URL`
- Added `MEDIAWIKI_API_URL` for API-based discovery

### 2. **Implemented MediaWiki API Discovery** (`scraper.py`)
- Added `discover_urls_from_api()` method
- Uses MediaWiki API to fetch all pages efficiently
- Filters for C++ related pages (`/w/cpp/` or starting with `cpp`)
- Handles pagination automatically
- Includes proper rate limiting

### 3. **Updated Main Discovery Flow** (`scraper.py`)
The scraper now tries methods in this order:
1. **MediaWiki API** (primary - most complete and efficient)
2. **Index-based discovery** (fallback - slower but reliable)
3. **Sitemap** (kept for compatibility, will always fail)

### 4. **Created Discovery Tools**
- `discover_sitemap.py` - Utility to test and discover sitemap URLs
- `SITEMAP_DISCOVERY.md` - Documentation of findings

## 🚀 How to Use

### Run the Scraper

The scraper is now ready to use. It will automatically:
1. Try MediaWiki API first (recommended)
2. Fall back to index-based discovery if API fails
3. Log all actions for debugging

```bash
cd scrape/cpp_reference
python scraper.py
```

### Test API Discovery Only

To test just the API discovery method:

```python
from scraper import CppReferenceScraper

scraper = CppReferenceScraper()
urls = scraper.discover_urls_from_api()
print(f"Found {len(urls)} URLs")
```

## 📊 Expected Results

### MediaWiki API Method
- **Speed**: Fast (500 pages per request)
- **Coverage**: Complete (all pages in main namespace)
- **Reliability**: High (official API)
- **Estimated Time**: ~5-10 minutes for ~15,000 pages

### Index-Based Method (Fallback)
- **Speed**: Slower (requires many page fetches)
- **Coverage**: Good (may miss some pages)
- **Reliability**: Medium (depends on link structure)
- **Estimated Time**: ~30-60 minutes

## 🔍 Verification

To verify the API method works:

```bash
cd scrape/cpp_reference
python -c "from scraper import CppReferenceScraper; s = CppReferenceScraper(); urls = s.discover_urls_from_api(); print(f'Found {len(urls)} URLs'); print('Sample:', urls[:5])"
```

## 📝 Next Steps

1. **Run a test scrape** with a small subset:
   ```python
   # In scraper.py main(), limit URLs for testing:
   urls = urls[:100]  # Test with first 100 URLs
   ```

2. **Monitor the logs** in `data/logs/scraper.log`

3. **Check progress** in `data/progress.json`

4. **Once verified**, run full scrape

## ⚠️ Important Notes

- The sitemap method will always fail (sitemap doesn't exist)
- API method is now the primary discovery method
- Rate limiting is built-in (1.5 seconds between API requests)
- All discovered URLs are filtered for C++ content (`/w/cpp/`)

## 🐛 Troubleshooting

### If API method fails:
- Check internet connection
- Verify `MEDIAWIKI_API_URL` is correct
- Check logs for specific error messages
- Fallback to index-based method will activate automatically

### If no URLs are discovered:
- Check that filter logic is correct
- Verify BASE_URL in config.py
- Review logs for error messages


