"""
Roeselite platform scraper (formerly SE scraper).
"""
import re
from urllib.parse import urlparse
from playwright.sync_api import Page

from components.base import BaseScraper, BaseConfig
from components.utils import full_url


class RoeseliteScraper(BaseScraper):
    """
    Scraper for the Roeselite assignment platform (se.cs.ovgu.de).
    
    Collects assignment pages based on allow_path_regex and downloads
    attachments using mode=dl, mode=raw, and file extensions.
    """
    
    def __init__(self, cfg: BaseConfig, allow_path_regex: str):
        """
        Args:
            cfg: Base configuration
            allow_path_regex: Regex pattern to match assignment URLs (e.g., r"^/assignment/view/")
        """
        super().__init__(cfg)
        self.allow = re.compile(allow_path_regex)
    
    def ensure_logged_in(self, page: Page) -> None:
        """Ensure user is logged in to SE platform."""
        if self._is_login_page(page):
            self._login(page)
    
    def collect_item_pages(self, page: Page) -> list[str]:
        """
        Collect assignment page URLs from the start page.
        Filters by allow_path_regex pattern.
        """
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )
        
        links = []
        for h in hrefs:
            path = h[len(self.cfg.base):] if h.startswith(self.cfg.base) else h
            if self.allow.match(path):
                links.append(full_url(self.cfg.base, h))
        
        return list(dict.fromkeys(links))  # unique, order-preserving
    
    def collect_attachments(self, page: Page) -> list[str]:
        """
        Collect attachment/resource URLs from current SE assignment page.
        Looks for mode=dl, mode=raw, archives, PDFs, images based on config flags.
        """
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )
        
        out = []
        
        for h in hrefs:
            url = full_url(self.cfg.base, h)
            
            # Download from allowed hosts only!
            host = urlparse(url).netloc
            if host not in self.cfg.allowed_resource_hosts:
                continue
            
            u = url.lower()
            
            # mode=dl
            if self.cfg.include_mode_dl and "mode=dl" in u:
                out.append(url)
            
            # mode=raw
            if self.cfg.include_mode_raw and "mode=raw" in u:
                out.append(url)
            
            # archive: zip
            if self.cfg.include_archive_zip and u.endswith(".zip"):
                out.append(url)
            
            # archive: tgz
            if self.cfg.include_archive_tgz and u.endswith((".tgz", ".tar.gz", ".gz")):
                out.append(url)
            
            # PDFs
            if self.cfg.include_pdfs and u.endswith(".pdf"):
                out.append(url)
            
            # img
            if self.cfg.include_images and u.endswith((".png", ".jpg", ".jpeg")):
                out.append(url)
        
        # unique, order-preserving
        return list(dict.fromkeys(out))

