"""
Base classes for scrapers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from playwright.sync_api import Page
from typing import Optional

from components.utils import full_url, safe_filename


@dataclass(frozen=True)
class BaseConfig:
    """Base configuration for all scrapers."""
    # Base URL of the target website
    base: str
    
    # Entry page that lists all items to be processed
    start_path: str
    
    # Login page URL (used for interactive login)
    login_path: str
    
    # Login form selectors
    sel_user: str = 'input[type="text"]'
    sel_pass: str = 'input[type="password"]'
    sel_submit: str = 'input[type="submit"]'
    
    # Security: Restrict downloads to trusted hosts only
    allowed_resource_hosts: tuple[str, ...] = ()
    
    # Resource download policy
    include_mode_raw: bool = False
    include_mode_dl: bool = True
    include_archive_zip: bool = True
    include_archive_tgz: bool = False
    include_images: bool = False
    include_pdfs: bool = False
    include_url_txt: bool = False
    
    # Runtime / Browser settings
    profile_dir: str = ".pw_profile"
    out_dir: Path = Path("data")
    pdf_format: str = "A4"
    print_background: bool = True
    headless: bool = True
    
    # Downloader strategy: "request", "click", or "auto" (try request first, fallback to click)
    downloader_strategy: str = "auto"


class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.
    
    Subclasses must implement:
    - ensure_logged_in(page): Ensure user is logged in
    - collect_item_pages(page): Collect URLs of pages to process
    - collect_attachments(page): Collect attachment URLs from current page
    """
    
    def __init__(self, cfg: BaseConfig):
        self.cfg = cfg
    
    @abstractmethod
    def ensure_logged_in(self, page: Page) -> None:
        """
        Ensure the user is logged in. If not, perform login.
        This method should handle navigation to login page if needed.
        """
        pass
    
    @abstractmethod
    def collect_item_pages(self, page: Page) -> list[str]:
        """
        Collect URLs of all pages that should be processed (e.g., assignments, resources).
        This is called on the start page.
        Returns: List of full URLs to visit.
        """
        pass
    
    @abstractmethod
    def collect_attachments(self, page: Page) -> list[str]:
        """
        Collect attachment/resource URLs from the current page.
        This is called for each item page.
        Returns: List of full URLs to download.
        """
        pass
    
    def _is_login_page(self, page: Page) -> bool:
        """Check if current page is a login page."""
        return self.cfg.login_path in page.url
    
    def _login(self, page: Page) -> None:
        """Perform interactive login."""
        from getpass import getpass
        
        user = input("Username: ").strip()
        pw = getpass("Password: ")
        
        page.goto(full_url(self.cfg.base, self.cfg.login_path))
        page.fill(self.cfg.sel_user, user)
        page.fill(self.cfg.sel_pass, pw)
        page.click(self.cfg.sel_submit)
        page.wait_for_load_state("networkidle")
    
    def create_page_folder(self, idx: int, url: str, page: Page) -> Path:
        """
        Create a folder for the current page.
        Returns: Path to the created folder.
        """
        title = page.title() or url
        folder = self.cfg.out_dir / f"{idx:03d}_{safe_filename(title)}"
        folder.mkdir(parents=True, exist_ok=True)
        
        if self.cfg.include_url_txt:
            (folder / "url.txt").write_text(url + "\n", encoding="utf-8")
        
        return folder
    
    def save_pdf(self, page: Page, folder: Path) -> None:
        """Save the current page as PDF."""
        page.pdf(
            path=str(folder / "task.pdf"),
            format=self.cfg.pdf_format,
            print_background=self.cfg.print_background,
        )
    
    def run(self, downloader: Optional['Downloader'] = None) -> None:
        """
        Main execution method.
        
        Args:
            downloader: Optional Downloader instance. If None, will be created based on cfg.downloader_strategy.
        """
        from components.downloader import create_downloader
        
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        start_url = full_url(self.cfg.base, self.cfg.start_path)
        
        if downloader is None:
            downloader = create_downloader(self.cfg.downloader_strategy)
        
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=self.cfg.profile_dir,
                headless=self.cfg.headless,
            )
            page = ctx.new_page()
            
            page.goto(start_url)
            self.ensure_logged_in(page)
            page.goto(start_url, wait_until="networkidle")
            
            links = self.collect_item_pages(page)
            print(f"Gefunden: {len(links)} Seiten")
            
            for i, url in enumerate(links, 1):
                print(f"[{i}/{len(links)}] {url}")
                page.goto(url, wait_until="networkidle")
                
                folder = self.create_page_folder(i, url, page)
                
                self.save_pdf(page, folder)
                
                n = self._save_attachments(page, folder, downloader)
                if n:
                    print(f"  ✓ attachments saved: {n}")
            
            ctx.close()
    
    def _save_attachments(self, page: Page, page_folder: Path, downloader: 'Downloader') -> int:
        """
        Save attachments for the current page.
        
        Args:
            page: Current Playwright page
            page_folder: Folder to save attachments in
            downloader: Downloader instance to use
        
        Returns:
            Number of successfully saved files
        """
        att_dir = page_folder / "attachments"
        att_dir.mkdir(parents=True, exist_ok=True)
        
        links = self.collect_attachments(page)
        if not links:
            return 0
        
        saved = 0
        
        for url in links:
            try:
                filename = downloader.download(page, url, att_dir)
                if filename:
                    saved += 1
            except Exception as e:
                print(f"  ⚠ failed: {url} ({e})")
        
        return saved


# Forward reference for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from components.downloader import Downloader

# Import here to avoid circular dependency
from playwright.sync_api import sync_playwright


def create_scraper(cfg: BaseConfig) -> BaseScraper:
    """
    Factory function to create the appropriate scraper based on config type.
    
    Args:
        cfg: Configuration instance
    
    Returns:
        Appropriate scraper instance
    
    Raises:
        ValueError: If config type is not recognized
    """
    # Import here to avoid circular dependencies
    from components.se_scraper import RoessliteScraper
    from components.moodle_scraper import MoodleScraper
    
    # Check config type and create appropriate scraper
    cfg_type = type(cfg).__name__
    
    if cfg_type == "SEConfig":
        # SEConfig (Roesslite platform)
        return RoessliteScraper(cfg, cfg.allow_path_regex)
    elif cfg_type == "MoodleConfig":
        # MoodleConfig
        # Use resource_module_patterns from config, or default
        resource_patterns = cfg.resource_module_patterns
        if resource_patterns is None:
            resource_patterns = ("/mod/resource/view.php", "/mod/folder/view.php")
        return MoodleScraper(cfg, resource_module_patterns=resource_patterns)
    else:
        raise ValueError(f"Unknown config type: {cfg_type}. Supported: SEConfig, MoodleConfig")

