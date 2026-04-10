# cppreference.com Data Collection Report

**Generated**: March 2025  
**Target Site**: https://en.cppreference.com/w/  
**Collection Method**: Live Site Scraping

## Executive Summary

This report documents the data collection strategy for scraping cppreference.com from the live site. Since the official offline archives are blocked, we must collect data directly from the live website. This report covers site structure analysis, collection methods, implementation strategies, and best practices.

### ⚠️ Important Notice

According to the [cppreference.com main page](https://en.cppreference.com/w/), **the site will be in temporary read-only mode in the next few weeks** (as of March 30, 2025) to facilitate software updates. This may affect scraping operations. Plan accordingly and consider completing the collection before the maintenance period.

---

## 1. Site Analysis

### 1.1 Site Structure

**Base URL**: `https://en.cppreference.com/w/`

**Key Characteristics:**
- **Platform**: MediaWiki-based
- **Total Pages**: ~15,000 static HTML pages
- **Content Coverage**: C++98 → C++26 (all major standard versions)
- **Content Types**:
  - Language reference pages
  - Standard library documentation
  - Code examples (>25,000 snippets)
  - Compiler support tables
  - Feature test macros

**URL Patterns:**
- Main pages: `https://en.cppreference.com/w/cpp/...`
- Headers: `https://en.cppreference.com/w/cpp/header/...`
- Containers: `https://en.cppreference.com/w/cpp/container/...`
- Algorithms: `https://en.cppreference.com/w/cpp/algorithm/...`

### 1.2 HTML Structure

**Main Content Selectors:**
- Main content: `<div id="mw-content-text">`
- Page title: `<h1 class="firstHeading">`
- Code blocks: `<pre class="programlisting">`, `<pre class="t-dcl">`
- Tables: `<table class="t-dcl-begin">`, `<table class="t-dcl">`
- Version markers: `<span class="t-mark-rev t-mark-cppXX">` (e.g., `t-mark-cpp11`, `t-mark-cpp20`)
- Cross-references: `<a href="/w/cpp/...">` (relative links)

### 1.3 Robots.txt Analysis

**Status**: Fully permissive
```
User-agent: *
Disallow:
```

- No restrictions on crawling
- Still recommended to be respectful with rate limiting

---

## 2. Collection Strategies

### 2.1 Strategy 1: Sitemap-Based Collection (Recommended)

**Advantages:**
- Complete coverage of all pages
- Efficient discovery
- No need to follow links recursively

**Implementation:**
- Fetch sitemap: `https://en.cppreference.com/w/sitemap.xml`
- Parse XML to extract all URLs
- Process each URL sequentially

**Estimated Pages**: ~15,000

### 2.2 Strategy 2: Index-Based Discovery

**Advantages:**
- Can start from specific categories
- Good for incremental updates
- Allows filtering by category

**Starting Points:**
- `https://en.cppreference.com/w/cpp` - Main C++ index
- `https://en.cppreference.com/w/cpp/header` - Header index
- `https://en.cppreference.com/w/cpp/container` - Container index
- `https://en.cppreference.com/w/cpp/algorithm` - Algorithm index

**Implementation:**
- Start from index pages
- Extract all links matching `/w/cpp/...` pattern
- Recursively follow links (with depth limit)

### 2.3 Strategy 3: Category-Based Collection

**Advantages:**
- Organized by topic
- Can prioritize important categories
- Easier to track progress

**Categories:**
- Language features
- Standard library headers
- Containers
- Algorithms
- Utilities
- I/O
- Threading
- Templates

---

## 3. Rate Limiting and Ethics

### 3.1 Rate Limiting Guidelines

**Minimum Requirements:**
- **Minimum delay**: 1 second between requests
- **Recommended delay**: 1.5-2 seconds (to be respectful)
- **Burst handling**: Use exponential backoff on errors

**Rationale:**
- Prevents server overload
- Reduces risk of IP blocking
- Maintains good relationship with site operators
- Respects the site's resources

### 3.2 User-Agent Requirements

**Format**: `ProjectName/Version (+https://yourproject.com/bot)`

**Example**: `CppCopilotBot/1.0 (+https://github.com/yourorg/cpp-copilot)`

**Why Important:**
- Identifies your project to site administrators
- Allows them to contact you if needed
- Demonstrates responsible scraping practices
- May prevent blocking if issues arise

### 3.3 Error Handling

**HTTP Status Codes to Handle:**
- **429 (Too Many Requests)**: Increase delay, implement exponential backoff
- **503 (Service Unavailable)**: Wait and retry (may indicate maintenance)
- **404 (Not Found)**: Log and skip
- **500 (Server Error)**: Retry with backoff

**Retry Strategy:**
- Initial retry: Wait 2 seconds
- Second retry: Wait 4 seconds
- Third retry: Wait 8 seconds
- Maximum retries: 3 attempts

---

## 4. Data Extraction Methods

### 4.1 Content Extraction

**Extract the Following:**

1. **Page Metadata:**
   - Title (`<h1 class="firstHeading">`)
   - URL
   - Last modified date (if available)

2. **Main Content:**
   - Text content from `#mw-content-text`
   - Preserve structure (headings, paragraphs, lists)

3. **Code Examples:**
   - All `<pre class="programlisting">` blocks
   - All `<pre class="t-dcl">` blocks
   - Preserve code formatting

4. **Tables:**
   - Compiler support tables
   - "Since C++XX" tables
   - Function signature tables

5. **Version Information:**
   - Extract C++ standard versions (e.g., `t-mark-cpp11`, `t-mark-cpp20`)
   - "Since C++XX" annotations

6. **Cross-References:**
   - Internal links to other cppreference pages
   - External links (for reference)

### 4.2 Data Structure

**Recommended Output Format (JSON):**

```json
{
  "title": "std::vector",
  "url": "https://en.cppreference.com/w/cpp/container/vector",
  "text": "Main content text...",
  "code_blocks": [
    "code example 1",
    "code example 2"
  ],
  "tables": [
    "table content"
  ],
  "signatures": [
    "template<class T, class Allocator> class vector;"
  ],
  "versions": ["cpp98", "cpp11", "cpp17"],
  "since_info": ["Since C++98"],
  "categories": ["container", "vector"],
  "cross_references": [
    "/w/cpp/container/array",
    "/w/cpp/algorithm/sort"
  ],
  "extracted_at": "2025-03-30T12:00:00Z"
}
```

---

## 5. Implementation Architecture

### 5.1 Project Structure

```
scrape/cpp_reference/
├── DATA_COLLECTION_REPORT.md  (this file)
├── scraper.py                 (main scraper implementation)
├── extractor.py               (content extraction logic)
├── utils.py                   (utility functions)
├── config.py                  (configuration settings)
├── requirements.txt           (Python dependencies)
├── data/                      (collected data)
│   ├── raw/                   (raw HTML files)
│   ├── parsed/                (extracted JSON files)
│   └── logs/                  (scraping logs)
└── README.md                  (project documentation)
```

### 5.2 Core Components

**1. Scraper (`scraper.py`)**
- URL discovery (sitemap/index-based)
- HTTP requests with rate limiting
- Error handling and retries
- Progress tracking

**2. Extractor (`extractor.py`)**
- HTML parsing
- Content extraction
- Data normalization
- Quality validation

**3. Utilities (`utils.py`)**
- Rate limiting decorators
- Retry logic
- Logging utilities
- Progress reporting

**4. Configuration (`config.py`)**
- Rate limiting settings
- User-Agent string
- Output directories
- Retry parameters

---

## 6. Implementation Details

### 6.1 Session Management

**Best Practices:**
- Use `requests.Session()` for connection pooling
- Set appropriate timeouts (10 seconds recommended)
- Handle cookies if needed
- Maintain session across requests

### 6.2 Progress Tracking

**Track:**
- Total pages discovered
- Pages successfully scraped
- Pages failed
- Current progress percentage
- Estimated time remaining
- Errors encountered

**Storage:**
- Save progress to JSON file periodically
- Allow resuming from last checkpoint
- Log all activities

### 6.3 Data Persistence

**Storage Strategy:**
1. **Raw HTML**: Save original HTML for backup/reprocessing
2. **Parsed JSON**: Store extracted content in structured format
3. **Metadata**: Track collection statistics

**File Naming:**
- Use URL-safe filenames
- Include timestamp for versioning
- Organize by category if needed

---

## 7. Quality Assurance

### 7.1 Validation Checks

**Content Validation:**
- Verify main content exists
- Check for minimum content length
- Validate code block extraction
- Ensure version information captured

**Data Quality:**
- Check for duplicate pages
- Validate JSON structure
- Verify URL correctness
- Check for broken links

### 7.2 Error Recovery

**Handling Strategies:**
- Log all errors with context
- Retry failed pages at end
- Generate error report
- Allow manual review of failures

---

## 8. Performance Considerations

### 8.1 Estimated Collection Time

**Assumptions:**
- 15,000 pages total
- 1.5 seconds delay between requests
- ~95% success rate

**Calculation:**
- Time per page: ~1.5 seconds
- Total time: 15,000 × 1.5 = 22,500 seconds ≈ **6.25 hours**

**With Errors and Retries:**
- Estimated total: **7-8 hours** for complete collection

### 8.2 Resource Requirements

**Storage:**
- Raw HTML: ~500-700 MB
- Parsed JSON: ~200-300 MB
- Logs: ~10-20 MB
- **Total**: ~800 MB - 1 GB

**Network:**
- Bandwidth: Moderate (depends on connection)
- Concurrent requests: 1 (sequential recommended)

---

## 9. Legal and Ethical Considerations

### 9.1 License Compliance

**cppreference.com License:**
- CC-BY-SA 3.0 and GFDL
- Requires attribution
- Share-alike for derivatives
- Commercial use: Check specific terms

**Reference**: https://en.cppreference.com/w/Cppreference:Copyright

### 9.2 Ethical Guidelines

**Do:**
- ✅ Respect rate limits
- ✅ Identify your project clearly
- ✅ Use collected data responsibly
- ✅ Provide attribution
- ✅ Contact site admins if issues arise

**Don't:**
- ❌ Overwhelm the server
- ❌ Scrape without identification
- ❌ Ignore robots.txt (even if permissive)
- ❌ Use data without proper attribution
- ❌ Redistribute without compliance

---

## 10. Monitoring and Maintenance

### 10.1 Monitoring During Collection

**Metrics to Track:**
- Requests per minute
- Success rate
- Error rate by type
- Average response time
- Bandwidth usage

### 10.2 Maintenance Considerations

**Regular Tasks:**
- Check for site updates
- Monitor for structural changes
- Update selectors if HTML changes
- Review and update rate limits
- Archive old data

---

## 11. Risk Assessment

### 11.1 Potential Risks

1. **Site Maintenance**: Site going read-only (announced for upcoming weeks)
2. **IP Blocking**: If rate limits are exceeded
3. **Structure Changes**: HTML structure may change
4. **Network Issues**: Connection problems during collection
5. **Data Inconsistency**: Some pages may be updated during collection

### 11.2 Mitigation Strategies

1. **Complete collection before maintenance period**
2. **Implement proper rate limiting**
3. **Use robust selectors (multiple fallbacks)**
4. **Implement resume capability**
5. **Validate data consistency**

---

## 12. Next Steps

### 12.1 Immediate Actions

1. ✅ Review this report
2. ⬜ Set up project structure
3. ⬜ Implement scraper with rate limiting
4. ⬜ Test on small subset (10-20 pages)
5. ⬜ Validate extracted data quality
6. ⬜ Begin full collection

### 12.2 Post-Collection

1. Validate all collected data
2. Process and normalize data
3. Generate collection statistics
4. Archive raw data
5. Prepare for next phase (parsing/chunking)

---

## 13. References

- [cppreference.com Main Page](https://en.cppreference.com/w/)
- [cppreference.com Archives](https://en.cppreference.com/w/Cppreference:Archives)
- [cppreference.com Copyright](https://en.cppreference.com/w/Cppreference:Copyright)
- [Sitemap](https://en.cppreference.com/w/sitemap.xml)

---

## Appendix A: Quick Start Checklist

- [ ] Install dependencies (`requests`, `beautifulsoup4`, `lxml`)
- [ ] Configure User-Agent string
- [ ] Set up output directories
- [ ] Test sitemap access
- [ ] Test single page extraction
- [ ] Implement rate limiting
- [ ] Add error handling
- [ ] Set up logging
- [ ] Test on 10 pages
- [ ] Validate output format
- [ ] Begin full collection

---

**Report Status**: Ready for Implementation  
**Last Updated**: March 2025  
**Next Review**: After initial collection test

