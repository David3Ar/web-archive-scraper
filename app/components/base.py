"""
Base classes for scrapers.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from playwright.sync_api import Page
from typing import Optional

from app.components.utils import full_url, safe_filename
from app.base_config.base_config import BaseConfig


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
        """Perform interactive login with retry on failure."""
        from getpass import getpass
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        
        max_attempts = 5
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            if attempt == 1:
                print("Login required. Please enter credentials:")
            else:
                print(f"\n⚠ Login failed. Attempt {attempt}/{max_attempts}")
                print("Please enter credentials again:")
            
            user = input("Username: ").strip()
            if not user:
                print("✗ Username cannot be empty. Please try again.")
                attempt -= 1  # Don't count empty username as attempt
                continue
            
            pw = getpass("Password: ")
            if not pw:
                print("✗ Password cannot be empty. Please try again.")
                attempt -= 1  # Don't count empty password as attempt
                continue
            
            # Check if we're already on a login page (including SSO)
            current_url = page.url
            is_on_login_page = self._is_login_page(page)
            
            # For MoodleScraper, also check SSO pages
            if hasattr(self, '_is_sso_login_page'):
                is_on_login_page = is_on_login_page or self._is_sso_login_page(page)
            
            if not is_on_login_page:
                login_url = full_url(self.cfg.base, self.cfg.login_path)
                if attempt == 1:
                    print(f"Navigating to login page: {login_url}")
                try:
                    page.goto(login_url, wait_until="networkidle", timeout=30000)
                except PlaywrightTimeoutError as e:
                    print(f"✗ ERROR: Timeout loading login page: {e}")
                    if attempt < max_attempts:
                        continue
                    raise
                except Exception as e:
                    print(f"✗ ERROR: Error loading login page: {e}")
                    if attempt < max_attempts:
                        continue
                    raise
            else:
                if attempt == 1:
                    print(f"Already on login page: {current_url}")
                # Wait for page to be ready
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass  # Continue even if timeout
            
            # Check if login form elements exist
            # Try standard selectors first, then fallback to common alternatives (for SSO pages)
            user_field = None
            pass_field = None
            submit_button = None
            
            # Try primary selector
            user_field = page.query_selector(self.cfg.sel_user)
            
            # If not found, try common alternatives (especially for SSO pages)
            if not user_field:
                alternative_user_selectors = [
                    'input[type="text"]',
                    'input[id*="user"]',
                    'input[name*="user"]',
                    'input[id*="login"]',
                    'input[name*="login"]',
                    '#username',
                    '#user',
                    '#login',
                ]
                for selector in alternative_user_selectors:
                    user_field = page.query_selector(selector)
                    if user_field:
                        if attempt == 1:
                            print(f"  Found username field with alternative selector: {selector}")
                        break
            
            if not user_field:
                print(f"✗ ERROR: Username field not found with selector: {self.cfg.sel_user}")
                print(f"  Current page URL: {page.url}")
                print(f"  Page title: {page.title()}")
                # Try to get page content for debugging
                try:
                    body_text = page.query_selector("body").inner_text()[:500]
                    print(f"  Page content preview: {body_text}...")
                except:
                    pass
                if attempt < max_attempts:
                    continue
                raise ValueError(f"Username field not found: {self.cfg.sel_user}")
            
            # Try primary selector for password
            pass_field = page.query_selector(self.cfg.sel_pass)
            
            # If not found, try common alternatives
            if not pass_field:
                alternative_pass_selectors = [
                    'input[type="password"]',
                    'input[id*="pass"]',
                    'input[name*="pass"]',
                    '#password',
                    '#pass',
                ]
                for selector in alternative_pass_selectors:
                    pass_field = page.query_selector(selector)
                    if pass_field:
                        if attempt == 1:
                            print(f"  Found password field with alternative selector: {selector}")
                        break
            
            if not pass_field:
                print(f"✗ ERROR: Password field not found with selector: {self.cfg.sel_pass}")
                if attempt < max_attempts:
                    continue
                raise ValueError(f"Password field not found: {self.cfg.sel_pass}")
            
            # Try primary selector for submit
            submit_button = page.query_selector(self.cfg.sel_submit)
            
            # If not found, try common alternatives
            if not submit_button:
                alternative_submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Login")',
                    'button:has-text("Anmelden")',
                    'button:has-text("Sign in")',
                    'input[value*="Login"]',
                    'input[value*="Anmelden"]',
                ]
                for selector in alternative_submit_selectors:
                    try:
                        submit_button = page.query_selector(selector)
                        if submit_button:
                            if attempt == 1:
                                print(f"  Found submit button with alternative selector: {selector}")
                            break
                    except:
                        continue
            
            if not submit_button:
                print(f"✗ ERROR: Submit button not found with selector: {self.cfg.sel_submit}")
                if attempt < max_attempts:
                    continue
                raise ValueError(f"Submit button not found: {self.cfg.sel_submit}")
            
            # Clear fields before filling (in case of retry)
            try:
                if user_field:
                    user_field.fill("")
                    user_field.fill(user)
                else:
                    page.fill(self.cfg.sel_user, user)
            except Exception as e:
                print(f"✗ ERROR: Error filling username: {e}")
                if attempt < max_attempts:
                    continue
                raise
            
            try:
                if pass_field:
                    pass_field.fill("")
                    pass_field.fill(pw)
                else:
                    page.fill(self.cfg.sel_pass, pw)
            except Exception as e:
                print(f"✗ ERROR: Error filling password: {e}")
                if attempt < max_attempts:
                    continue
                raise
            
            # Submit form
            try:
                if submit_button:
                    submit_button.click()
                else:
                    page.click(self.cfg.sel_submit)
            except Exception as e:
                print(f"✗ ERROR: Error clicking submit: {e}")
                if attempt < max_attempts:
                    continue
                raise
            
            # Wait for navigation
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                print(f"⚠ WARNING: Timeout waiting for page load (may still be loading)")
            except Exception as e:
                print(f"⚠ WARNING: Error waiting for page load: {e}")
            
            # Verify login success
            final_url = page.url
            
            # Check if still on login page (login failed)
            is_still_on_login = self._is_login_page(page)
            if hasattr(self, '_is_sso_login_page'):
                is_still_on_login = is_still_on_login or self._is_sso_login_page(page)
            
            if is_still_on_login:
                # Try to extract error message from page
                error_message = None
                try:
                    error_selectors = [
                        '.alert-danger',
                        '.alert-error',
                        '.error',
                        '[role="alert"]',
                        '.loginerrors',
                        '#loginerrormessage',
                    ]
                    for selector in error_selectors:
                        error_elem = page.query_selector(selector)
                        if error_elem:
                            error_text = error_elem.inner_text().strip()
                            if error_text:
                                error_message = error_text
                                break
                    
                    # Also check for common error text patterns
                    if not error_message:
                        page_text = page.inner_text("body").lower()
                        if "invalid" in page_text or "incorrect" in page_text or "wrong" in page_text:
                            error_message = "Invalid credentials"
                except Exception as e:
                    pass  # Ignore errors when extracting error message
                
                if error_message:
                    print(f"✗ {error_message}")
                else:
                    print(f"✗ Login failed - still on login page")
                    print(f"  Final URL: {final_url}")
                
                # Continue loop to retry
                if attempt < max_attempts:
                    continue
                else:
                    print(f"\n✗ ERROR: Login failed after {max_attempts} attempts")
                    raise ValueError("Login failed: Still on login page after submission")
            
            # Check for common error indicators in URL or page
            if "error" in final_url.lower():
                page_title = page.title()
                print(f"⚠ WARNING: URL suggests possible login issue")
                print(f"  Final URL: {final_url}")
                print(f"  Page title: {page_title}")
            
            # If we reach here, login was successful
            print("✓ Login successful")
            return
        
        # Should not reach here, but just in case
        raise ValueError(f"Login failed after {max_attempts} attempts")
    
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
        from app.components.downloader import create_downloader
        
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        start_url = full_url(self.cfg.base, self.cfg.start_path)
        
        if downloader is None:
            downloader = create_downloader(self.cfg.downloader_strategy, self.cfg)
        
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
            print(f"Found: {len(links)} pages")
            
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
    from app.components.downloader import Downloader

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
    from app.components.scraper.roeselite_scraper import RoeseliteScraper
    from app.components.scraper.moodle_scraper import MoodleScraper
    
    # Check config type by checking MRO (Method Resolution Order) to handle inheritance
    cfg_type = type(cfg)
    cfg_type_name = cfg_type.__name__
    
    # Get all base class names from MRO to check inheritance
    mro_names = [cls.__name__ for cls in cfg_type.__mro__]
    
    # Check if it's a RoeseliteConfig or subclass (inheritance handles SEConfig, etc.)
    if "RoeseliteConfig" in mro_names:
        # Verify it has the required property
        if hasattr(cfg, 'allow_path_regex'):
            return RoeseliteScraper(cfg, cfg.allow_path_regex)
    
    # Check if it's a MoodleConfig or subclass (inheritance handles TheoinfConfig, etc.)
    if "MoodleConfig" in mro_names:
        # Use resource_module_patterns from config, or default
        resource_patterns = getattr(cfg, 'resource_module_patterns', None)
        if resource_patterns is None:
            resource_patterns = ("/mod/resource/view.php", "/mod/folder/view.php")
        return MoodleScraper(cfg, resource_module_patterns=resource_patterns)
    
    raise ValueError(f"Unknown config type: {cfg_type_name}. Supported: RoeseliteConfig or MoodleConfig (and their subclasses)")

