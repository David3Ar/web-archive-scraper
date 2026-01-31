"""
Moodle platform scraper.
"""
import re
from urllib.parse import urlparse, urljoin
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from components.base import BaseScraper, BaseConfig
from components.utils import full_url


class MoodleScraper(BaseScraper):
    """
    Scraper for Moodle learning platforms.
    
    Collects resource pages (/mod/resource/view.php?id=...) and extracts
    actual download links (pluginfile.php URLs) from those pages.
    """
    
    def __init__(self, cfg: BaseConfig, resource_module_patterns: tuple[str, ...] = None):
        """
        Args:
            cfg: Base configuration
            resource_module_patterns: URL patterns to match Moodle resource modules.
                                     Default: ("/mod/resource/view.php", "/mod/folder/view.php")
        """
        super().__init__(cfg)
        if resource_module_patterns is None:
            resource_module_patterns = ("/mod/resource/view.php", "/mod/folder/view.php")
        self.resource_module_patterns = resource_module_patterns
    
    def ensure_logged_in(self, page: Page) -> None:
        """Ensure user is logged in to Moodle."""
        if self._is_login_page(page):
            self._login(page)
    
    def collect_item_pages(self, page: Page) -> list[str]:
        """
        Collect Moodle resource page URLs from the course overview.
        Looks for links matching resource_module_patterns.
        """
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )
        
        links = []
        base_url = self.cfg.base
        
        for h in hrefs:
            url = full_url(base_url, h)
            
            # Check if URL matches any resource module pattern
            for pattern in self.resource_module_patterns:
                if pattern in url:
                    links.append(url)
                    break
        
        return list(dict.fromkeys(links))  # unique, order-preserving
    
    def collect_attachments(self, page: Page) -> list[str]:
        """
        Extract actual download URLs from a Moodle resource page.
        
        Strategy:
        1. Look for direct links to pluginfile.php (the actual file URLs)
        2. Look for links with forcedownload=1 parameter
        3. If page redirects, check final URL
        4. Try to find download button/link on page
        
        Returns:
            List of actual download URLs (pluginfile.php URLs)
        """
        current_url = page.url
        base_url = self.cfg.base
        download_urls = []
        
        # Wait for page to be fully loaded
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass  # Continue anyway
        
        # Strategy 1: Look for pluginfile.php links directly on the page
        pluginfile_links = page.eval_on_selector_all(
            'a[href*="pluginfile.php"]',
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )
        
        for link in pluginfile_links:
            url = full_url(base_url, link)
            # Filter by allowed hosts
            host = urlparse(url).netloc
            if host in self.cfg.allowed_resource_hosts:
                download_urls.append(url)
        
        # Strategy 2: Look for links with forcedownload=1
        forcedownload_links = page.eval_on_selector_all(
            'a[href*="forcedownload=1"]',
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )
        
        for link in forcedownload_links:
            url = full_url(base_url, link)
            host = urlparse(url).netloc
            if host in self.cfg.allowed_resource_hosts:
                download_urls.append(url)
        
        # Strategy 3: Check if current page URL is already a pluginfile.php URL
        # (happens when resource page redirects directly to file)
        if "pluginfile.php" in current_url:
            host = urlparse(current_url).netloc
            if host in self.cfg.allowed_resource_hosts:
                download_urls.append(current_url)
        
        # Strategy 3b: Check response URL (in case of redirects)
        # Some Moodle resources redirect immediately to the file
        try:
            response = page.request.get(current_url, timeout=5000)
            if response.ok:
                final_url = response.url
                if "pluginfile.php" in final_url and final_url != current_url:
                    host = urlparse(final_url).netloc
                    if host in self.cfg.allowed_resource_hosts:
                        download_urls.append(final_url)
        except:
            pass  # Ignore errors, continue with other strategies
        
        # Strategy 4: Look for download buttons/links with specific classes or IDs
        # Moodle often uses classes like "resourceworkaround", "download", etc.
        download_selectors = [
            'a.resourceworkaround',
            'a.download',
            'a[class*="download"]',
            'a[title*="Download"]',
            'a[title*="download"]',
            'button[type="submit"]',
        ]
        
        for selector in download_selectors:
            try:
                elements = page.query_selector_all(selector)
                for el in elements:
                    href = el.get_attribute("href")
                    if href:
                        url = full_url(base_url, href)
                        if "pluginfile.php" in url or "forcedownload=1" in url:
                            host = urlparse(url).netloc
                            if host in self.cfg.allowed_resource_hosts:
                                download_urls.append(url)
            except:
                continue
        
        # Strategy 5: If no direct links found, try to extract from iframe or embedded content
        # Some Moodle resources embed files in iframes
        try:
            iframes = page.query_selector_all("iframe[src]")
            for iframe in iframes:
                src = iframe.get_attribute("src")
                if src and ("pluginfile.php" in src or "forcedownload=1" in src):
                    url = full_url(base_url, src)
                    host = urlparse(url).netloc
                    if host in self.cfg.allowed_resource_hosts:
                        download_urls.append(url)
        except:
            pass
        
        # Strategy 6: Check response headers or meta tags for download URL
        # Some Moodle pages have meta refresh or redirect headers
        try:
            # Check for meta refresh
            meta_refresh = page.query_selector('meta[http-equiv="refresh"]')
            if meta_refresh:
                content = meta_refresh.get_attribute("content")
                if content:
                    # Parse: "0;url=http://..."
                    match = re.search(r'url=([^\s;]+)', content, re.IGNORECASE)
                    if match:
                        url = match.group(1)
                        if "pluginfile.php" in url:
                            host = urlparse(url).netloc
                            if host in self.cfg.allowed_resource_hosts:
                                download_urls.append(url)
        except:
            pass
        
        # Filter by file type if configured
        filtered_urls = []
        for url in download_urls:
            url_lower = url.lower()
            
            # Apply filters based on config
            should_include = False
            
            if self.cfg.include_pdfs and url_lower.endswith(".pdf"):
                should_include = True
            elif self.cfg.include_archive_zip and url_lower.endswith(".zip"):
                should_include = True
            elif self.cfg.include_archive_tgz and url_lower.endswith((".tgz", ".tar.gz", ".gz")):
                should_include = True
            elif self.cfg.include_images and url_lower.endswith((".png", ".jpg", ".jpeg", ".gif")):
                should_include = True
            elif self.cfg.include_mode_dl or self.cfg.include_mode_raw:
                # If mode flags are set, include any pluginfile.php URL
                should_include = True
            else:
                # Default: include PDFs and common document formats
                if url_lower.endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx")):
                    should_include = True
            
            if should_include:
                filtered_urls.append(url)
        
        # If no filtered URLs but we have pluginfile URLs, include them anyway
        # (user might want all resources)
        if not filtered_urls and download_urls:
            filtered_urls = download_urls
        
        return list(dict.fromkeys(filtered_urls))  # unique, order-preserving

