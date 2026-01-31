"""
Downloader implementations for downloading resources.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from app.components.utils import suggest_filename, safe_filename

if TYPE_CHECKING:
    from app.base_config.base_config import BaseConfig


class Downloader(ABC):
    """Abstract base class for downloaders."""
    
    def __init__(self, config: Optional['BaseConfig'] = None):
        """
        Initialize downloader with optional config.
        
        Args:
            config: BaseConfig instance (optional, for file replacement policy)
        """
        self.config = config
    
    @abstractmethod
    def download(self, page: Page, url: str, target_dir: Path, preferred_title: str | None = None) -> Optional[str]:
        """
        Download a resource from the given URL.
        
        Args:
            page: Playwright page (for session/cookies)
            url: URL to download
            target_dir: Directory to save the file in
            preferred_title: Preferred filename (from link text, without extension)
        
        Returns:
            Filename of saved file, or None if download failed
        """
        pass
    
    def _get_unique_filename(self, base_filename: str, target_dir: Path) -> Optional[Path]:
        """
        Get a filename based on replacement policy.
        
        If replace_existing_files is True, returns the target path (allowing overwrite).
        If replace_existing_files is False and file exists, returns None (skip download).
        If file doesn't exist, returns the target path.
        
        Args:
            base_filename: Proposed filename
            target_dir: Target directory
        
        Returns:
            Path to filename (or None if file exists and should be skipped)
        """
        target = target_dir / base_filename
        
        if not target.exists():
            return target
        
        # File exists - check replacement policy
        if self.config and self.config.replace_existing_files:
            # Replace existing file
            return target
        else:
            # Skip download if file exists
            return None


class RequestDownloader(Downloader):
    """
    Downloads resources using page.request.get().
    Preserves cookies and session automatically.
    """
    
    def download(self, page: Page, url: str, target_dir: Path, preferred_title: str | None = None) -> Optional[str]:
        """Download using HTTP request."""
        try:
            resp = page.request.get(url, timeout=30_000)
            if not resp.ok:
                print(f"  ⚠ skip (HTTP {resp.status}): {url}")
                return None
            
            # Determine filename
            filename = self._extract_filename(url, resp, target_dir, preferred_title)
            target = self._get_unique_filename(filename, target_dir)
            
            # Check if download should be skipped
            if target is None:
                print(f"  ⊘ skip (file exists): {filename}")
                return None
            
            # Determine content type
            ctype = (resp.headers.get("content-type") or "").lower()
            
            # Save as text or binary
            if "text" in ctype or "json" in ctype or url.lower().endswith((".md", ".txt")) or "mode=raw" in url.lower():
                target.write_text(resp.text(), encoding="utf-8")
            else:
                target.write_bytes(resp.body())
            
            return filename
        except Exception as e:
            print(f"  ⚠ RequestDownloader failed: {url} ({e})")
            return None
    
    def _extract_filename(self, url: str, resp, target_dir: Path, preferred_title: str | None = None) -> str:
        """Extract filename from preferred_title, Content-Disposition header, URL, or use heuristic."""
        # Priority 1: Use preferred_title if provided
        if preferred_title:
            # Determine extension from Content-Disposition or URL
            ext = ""
            content_disposition = resp.headers.get("content-disposition", "")
            if content_disposition:
                import re
                match = re.search(r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\';]+)', content_disposition)
                if match:
                    suggested_name = match.group(1).strip()
                    _, ext = os.path.splitext(suggested_name)
            else:
                # Try to get extension from URL
                from urllib.parse import urlparse
                parsed = urlparse(url)
                _, ext = os.path.splitext(parsed.path)
            
            # If no extension found, default to .pdf for PDF content
            if not ext:
                ctype = (resp.headers.get("content-type") or "").lower()
                if "pdf" in ctype:
                    ext = ".pdf"
                elif "zip" in ctype:
                    ext = ".zip"
                else:
                    # Try to infer from URL
                    url_lower = url.lower()
                    if url_lower.endswith(".pdf"):
                        ext = ".pdf"
                    elif url_lower.endswith(".zip"):
                        ext = ".zip"
                    elif url_lower.endswith((".doc", ".docx")):
                        ext = os.path.splitext(url_lower)[1]
                    else:
                        ext = ""  # No extension
            
            filename = safe_filename(preferred_title) + ext
            return filename
        
        # Priority 2: Try Content-Disposition header
        content_disposition = resp.headers.get("content-disposition", "")
        if content_disposition:
            # Parse: attachment; filename="file.pdf" or filename*=UTF-8''file.pdf
            import re
            match = re.search(r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\';]+)', content_disposition)
            if match:
                filename = match.group(1).strip()
                # Decode if needed
                if filename.startswith("UTF-8''"):
                    from urllib.parse import unquote
                    filename = unquote(filename[7:])
                return safe_filename(filename)
        
        # Priority 3: Fallback to URL-based filename
        return suggest_filename(url, target_dir)


class ClickDownloader(Downloader):
    """
    Downloads resources by clicking on links and using Playwright's download API.
    Useful for downloads that require JavaScript or special handling.
    """
    
    def download(self, page: Page, url: str, target_dir: Path, preferred_title: str | None = None) -> Optional[str]:
        """Download by clicking link and waiting for download."""
        try:
            # Navigate to URL if not already there, or find link on page
            current_url = page.url
            
            # Try to find a link on the page that matches the URL
            try:
                # Wait a bit for page to be ready
                page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            # Try to find link element
            link_selector = f'a[href*="{urlparse(url).path}"]'
            try:
                link = page.query_selector(link_selector)
                if link:
                    # Click and wait for download
                    with page.expect_download(timeout=30_000) as download_info:
                        link.click()
                    download = download_info.value
                else:
                    # If link not found, try navigating directly and looking for download trigger
                    # This is a fallback - might not work for all cases
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    # Look for any download link or button
                    download_links = page.query_selector_all('a[href*="pluginfile"], a[href*="forcedownload"], a[download]')
                    if download_links:
                        with page.expect_download(timeout=30_000) as download_info:
                            download_links[0].click()
                        download = download_info.value
                    else:
                        # No download link found on page
                        print(f"  ⚠ ClickDownloader: No download link found on page: {url}")
                        return None
            except PlaywrightTimeoutError:
                print(f"  ⚠ ClickDownloader timeout: {url}")
                return None
            except Exception as e:
                print(f"  ⚠ ClickDownloader failed to find/click link: {url} ({e})")
                return None
            
            # Determine filename: use preferred_title if available, otherwise use download suggestion
            if preferred_title:
                # Get extension from suggested filename or URL
                suggested_name = download.suggested_filename or "download"
                _, ext = os.path.splitext(suggested_name)
                if not ext:
                    # Try to infer from URL
                    url_lower = url.lower()
                    if url_lower.endswith(".pdf"):
                        ext = ".pdf"
                    elif url_lower.endswith(".zip"):
                        ext = ".zip"
                    else:
                        ext = os.path.splitext(url_lower)[1] or ""
                
                filename = safe_filename(preferred_title) + ext
            else:
                # Use suggested filename from download
                suggested_name = download.suggested_filename or "download"
                filename = safe_filename(suggested_name)
            
            target = self._get_unique_filename(filename, target_dir)
            
            # Check if download should be skipped
            if target is None:
                print(f"  ⊘ skip (file exists): {filename}")
                return None
            
            # Save the download
            download.save_as(target)
            
            return filename
        except Exception as e:
            print(f"  ⚠ ClickDownloader failed: {url} ({e})")
            return None


class AutoDownloader(Downloader):
    """
    Tries RequestDownloader first, falls back to ClickDownloader if that fails.
    """
    
    def __init__(self, config: Optional['BaseConfig'] = None):
        super().__init__(config)
        self.request_downloader = RequestDownloader(config)
        self.click_downloader = ClickDownloader(config)
    
    def download(self, page: Page, url: str, target_dir: Path, preferred_title: str | None = None) -> Optional[str]:
        """Try request first, then click."""
        # Try request downloader first
        result = self.request_downloader.download(page, url, target_dir, preferred_title=preferred_title)
        if result:
            return result
        
        # Fallback to click downloader
        print(f"  ↻ Fallback to ClickDownloader for: {url}")
        return self.click_downloader.download(page, url, target_dir, preferred_title=preferred_title)


def create_downloader(strategy: str, config: Optional['BaseConfig'] = None) -> Downloader:
    """
    Create a downloader based on strategy string.
    
    Args:
        strategy: "request", "click", or "auto"
        config: Optional BaseConfig instance (for file replacement policy)
    
    Returns:
        Downloader instance
    """
    if strategy == "request":
        return RequestDownloader(config)
    elif strategy == "click":
        return ClickDownloader(config)
    elif strategy == "auto":
        return AutoDownloader(config)
    else:
        raise ValueError(f"Unknown downloader strategy: {strategy}")

