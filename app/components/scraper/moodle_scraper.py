"""
Moodle platform scraper.
"""
import re
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from app.components.base import BaseScraper
from app.base_config.base_config import BaseConfig
from app.components.utils import full_url, safe_filename


@dataclass
class ResourceLink:
    """Represents a Moodle resource link with its section and title."""
    url: str
    section: str
    title: str | None = None


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
    
    def _is_sso_login_page(self, page: Page) -> bool:
        """Check if current page is an SSO login page (SAML2, etc.)."""
        url = page.url.lower()
        # Check for common SSO patterns
        sso_indicators = [
            "saml2",
            "sso",
            "idp",
            "shibboleth",
            "oauth",
            "saml",
            "idp-serv.uni-magdeburg.de",
        ]
        return any(indicator in url for indicator in sso_indicators)
    
    def handle_information_release(self, page: Page) -> bool:
        """
        Handle optional Information Release / Consent dialog after SSO login.
        
        This dialog may appear after successful SSO login with:
        - Title: "Information Release"
        - Text: "You are about to access the service: elearning.ovgu.de"
        - Accept button: button[name="_eventId_proceed"]
        - Reject button: button[name="_eventId_AttributeReleaseRejected"]
        
        Args:
            page: Playwright page object
            
        Returns:
            True if consent dialog was found and accepted, False otherwise
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        
        try:
            # Quick check with short timeout to avoid blocking normal flow
            # Check if we're on an IdP domain (not yet at elearning.ovgu.de)
            current_url = page.url
            if "elearning.ovgu.de" in current_url.lower():
                # Already at target domain, no consent dialog expected
                return False
            
            # Wait a bit for page to load (but not too long)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=2000)
            except PlaywrightTimeoutError:
                pass  # Continue anyway
            
            # Check for Information Release page indicators
            # Option 1: Check page title
            page_title = page.title().lower()
            is_info_release = "information release" in page_title
            
            # Option 2: Check for the Accept button (more reliable)
            accept_button = page.locator('button[name="_eventId_proceed"]')
            button_visible = False
            try:
                button_visible = accept_button.is_visible(timeout=1500)
            except (PlaywrightTimeoutError, Exception):
                pass
            
            if not is_info_release and not button_visible:
                # Not an information release page
                return False
            
            print("Detected Information Release / Consent dialog")
            
            # Click Accept button
            try:
                accept_button.click(timeout=2000)
                print("Clicked Accept on Information Release dialog")
            except Exception as e:
                print(f"⚠ WARNING: Could not click Accept button: {e}")
                return False
            
            # Wait for navigation back to elearning.ovgu.de
            # Use a pattern that matches any path on elearning.ovgu.de
            try:
                # Wait for URL to contain elearning.ovgu.de
                page.wait_for_url(
                    lambda url: "elearning.ovgu.de" in url.lower(),
                    timeout=10000,
                    wait_until="networkidle"
                )
                print("Successfully navigated back to elearning.ovgu.de after consent")
            except PlaywrightTimeoutError:
                # Fallback: just wait for network idle and check URL
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                    final_url = page.url
                    if "elearning.ovgu.de" in final_url.lower():
                        print("Successfully navigated back to elearning.ovgu.de after consent")
                    else:
                        print(f"⚠ WARNING: After consent, URL is: {final_url} (expected elearning.ovgu.de)")
                except Exception as e:
                    print(f"⚠ WARNING: Error waiting for navigation after consent: {e}")
            
            return True
            
        except Exception as e:
            # Defensive: never fail the entire flow if consent handling fails
            print(f"⚠ WARNING: Error handling Information Release dialog: {e}")
            return False
    
    def _is_logged_in(self, page: Page) -> bool:
        """
        Check if user is logged in by looking for positive indicators.
        
        Returns:
            True if logged in, False otherwise
        """
        try:
            # Wait for page to be ready
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except:
            pass
        
        # Positive indicators that we're logged in:
        # 1. User menu or user dropdown (common in Moodle)
        logged_in_indicators = [
            '[data-toggle="dropdown"][aria-label*="user"]',  # User dropdown
            '[data-toggle="dropdown"][aria-label*="User"]',
            '.usermenu',  # Moodle user menu
            '#usermenu',
            '[id*="usermenu"]',
            '[class*="usermenu"]',
            'a[href*="user/profile"]',  # Profile link
            'a[href*="logout"]',  # Logout link (only visible when logged in)
            'a[title*="Logout"]',
            'a[title*="Abmelden"]',
            '.user-info',  # User info section
            '[class*="user-info"]',
        ]
        
        for selector in logged_in_indicators:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    return True
            except:
                continue
        
        # Also check if we're on a course page (requires login)
        # Course pages typically have course content elements
        course_indicators = [
            '[id*="region-main"]',  # Main content region
            '.course-content',  # Course content
            '[class*="course-content"]',
            '[data-region="main-content"]',
        ]
        
        for selector in course_indicators:
            try:
                element = page.query_selector(selector)
                if element:
                    # If we're on a course page and not redirected to login, we're probably logged in
                    if not self._is_login_page(page) and not self._is_sso_login_page(page):
                        return True
            except:
                continue
        
        return False
    
    def ensure_logged_in(self, page: Page) -> None:
        """Ensure user is logged in to Moodle."""
        current_url = page.url
        print(f"Checking login status. Current URL: {current_url}")
        
        # First, check if we're clearly on a login page (by URL)
        if self._is_login_page(page):
            print("Detected standard Moodle login page (by URL), attempting login...")
            self._login(page)
            # Handle Information Release dialog after login
            self.handle_information_release(page)
            return
        
        if self._is_sso_login_page(page):
            print("Detected SSO login page (by URL), attempting login...")
            self._login(page)
            # Handle Information Release dialog after SSO login
            self.handle_information_release(page)
            return
        
        # Wait for page to load
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass
        
        final_url = page.url
        print(f"After wait, URL: {final_url}")
        
        # Check if we're logged in by looking for positive indicators
        if self._is_logged_in(page):
            print("✓ Already logged in (detected logged-in indicators)")
            return
        
        # Check if we got redirected to login page
        if self._is_login_page(page):
            print("Redirected to standard Moodle login page, attempting login...")
            self._login(page)
            self.handle_information_release(page)
            return
        
        if self._is_sso_login_page(page):
            print("Redirected to SSO login page, attempting login...")
            self._login(page)
            self.handle_information_release(page)
            return
        
        # If we're on a course page but couldn't detect login status clearly,
        # check if we can access course content (which requires login)
        if "/course/view.php" in final_url:
            try:
                # Try to find course content - if we can see it, we're logged in
                course_content = page.query_selector('[id*="region-main"], .course-content, [data-region="main-content"]')
                if course_content:
                    print("✓ Already logged in (can access course content)")
                    return
            except:
                pass
        
        # If we're not sure, but we're not on a login page, assume we're logged in
        # (Moodle typically redirects to login if not authenticated)
        if not self._is_login_page(page) and not self._is_sso_login_page(page):
            print("✓ Assuming already logged in (not on login page)")
            return
        
        # Last resort: if we're still not sure, try to navigate to login page
        # But only if we're actually on a login page
        print("⚠ Could not determine login status, but not on login page - assuming logged in")
    
    def _extract_section_name(self, page: Page, link_element) -> str:
        """
        Extract the section name for a given link element.
        
        Uses multiple fallback strategies to find the section container:
        1. Look for closest section container (li[id^='section-'], section, [data-sectionid])
        2. Extract section title from .sectionname, h3.sectionname, or [data-for='section_title']
        3. Fallback to "Unsorted" if nothing found
        
        Args:
            page: Playwright page object
            link_element: JavaScript handle to the link element
            
        Returns:
            Section name (filesystem-safe)
        """
        try:
            # Strategy 1: Find closest section container using JavaScript
            section_name = page.evaluate("""
                (link) => {
                    // Find closest section container
                    let container = link.closest('li[id^="section-"]') ||
                                   link.closest('section') ||
                                   link.closest('[data-sectionid]') ||
                                   link.closest('.section') ||
                                   link.closest('[class*="section"]');
                    
                    if (!container) {
                        // Try traversing up the DOM tree
                        let parent = link.parentElement;
                        let depth = 0;
                        while (parent && depth < 10) {
                            if (parent.id && parent.id.startsWith('section-')) {
                                container = parent;
                                break;
                            }
                            if (parent.classList && (
                                parent.classList.contains('section') ||
                                Array.from(parent.classList).some(c => c.includes('section'))
                            )) {
                                container = parent;
                                break;
                            }
                            if (parent.getAttribute && parent.getAttribute('data-sectionid')) {
                                container = parent;
                                break;
                            }
                            parent = parent.parentElement;
                            depth++;
                        }
                    }
                    
                    if (!container) return null;
                    
                    // Extract section title with multiple fallback selectors
                    let titleEl = container.querySelector('.sectionname') ||
                                container.querySelector('h3.sectionname') ||
                                container.querySelector('[data-for="section_title"]') ||
                                container.querySelector('h3') ||
                                container.querySelector('.section-title') ||
                                container.querySelector('[class*="sectionname"]');
                    
                    if (titleEl) {
                        let text = titleEl.innerText || titleEl.textContent;
                        if (text) return text.trim();
                    }
                    
                    // Fallback: try to extract from container's own text
                    let containerText = container.innerText || container.textContent;
                    if (containerText) {
                        // Try to find first line or heading
                        let lines = containerText.split('\\n').map(l => l.trim()).filter(l => l);
                        if (lines.length > 0) {
                            return lines[0];
                        }
                    }
                    
                    return null;
                }
            """, link_element)
            
            if section_name and section_name.strip():
                return safe_filename(section_name.strip())
        except Exception as e:
            print(f"  ⚠ Warning: Could not extract section name: {e}")
        
        return "Unsorted"
    
    def collect_item_pages(self, page: Page) -> list[str]:
        """
        Collect Moodle resource page URLs from the course overview.
        Looks for links matching resource_module_patterns.
        
        Note: This method is kept for backward compatibility.
        Use collect_resource_links() for section-based organization.
        """
        resource_links = self.collect_resource_links(page)
        return [rl.url for rl in resource_links]
    
    def collect_resource_links(self, page: Page) -> list[ResourceLink]:
        """
        Collect Moodle resource links with section and title information.
        
        For each link matching resource_module_patterns:
        - Extracts the URL
        - Determines the section name from the DOM structure
        - Extracts the link text as title
        
        Returns:
            List of ResourceLink objects with url, section, and title
        """
        # Wait for page to be fully loaded
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass  # Continue anyway
        
        # Get all links with their elements
        link_data = page.eval_on_selector_all(
            "a[href]",
            """
            els => els.map(e => ({
                href: e.getAttribute('href'),
                text: (e.innerText || e.textContent || '').trim(),
                element: e
            })).filter(item => item.href)
            """
        )
        
        resource_links = []
        base_url = self.cfg.base
        seen_urls = set()
        
        for link_info in link_data:
            href = link_info.get('href')
            if not href:
                continue
                
            url = full_url(base_url, href)
            
            # Check if URL matches any resource module pattern
            matches_pattern = False
            for pattern in self.resource_module_patterns:
                if pattern in url:
                    matches_pattern = True
                    break
            
            if not matches_pattern:
                continue
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Extract section name
            # We need to get the actual element handle to traverse DOM
            try:
                # Find the link element again to get its handle
                link_selector = f'a[href="{href}"]'
                # Use a more specific approach: evaluate on all matching links
                section_name = page.evaluate("""
                    (href) => {
                        let links = Array.from(document.querySelectorAll('a[href]'));
                        let link = links.find(l => l.getAttribute('href') === href);
                        if (!link) return null;
                        
                        // Find closest section container
                        let container = link.closest('li[id^="section-"]') ||
                                       link.closest('section') ||
                                       link.closest('[data-sectionid]') ||
                                       link.closest('.section') ||
                                       link.closest('[class*="section"]');
                        
                        if (!container) {
                            // Try traversing up the DOM tree
                            let parent = link.parentElement;
                            let depth = 0;
                            while (parent && depth < 10) {
                                if (parent.id && parent.id.startsWith('section-')) {
                                    container = parent;
                                    break;
                                }
                                if (parent.classList && (
                                    parent.classList.contains('section') ||
                                    Array.from(parent.classList).some(c => c.includes('section'))
                                )) {
                                    container = parent;
                                    break;
                                }
                                if (parent.getAttribute && parent.getAttribute('data-sectionid')) {
                                    container = parent;
                                    break;
                                }
                                parent = parent.parentElement;
                                depth++;
                            }
                        }
                        
                        if (!container) return null;
                        
                        // Extract section title with multiple fallback selectors
                        let titleEl = container.querySelector('.sectionname') ||
                                    container.querySelector('h3.sectionname') ||
                                    container.querySelector('[data-for="section_title"]') ||
                                    container.querySelector('h3') ||
                                    container.querySelector('.section-title') ||
                                    container.querySelector('[class*="sectionname"]');
                        
                        if (titleEl) {
                            let text = titleEl.innerText || titleEl.textContent;
                            if (text) return text.trim();
                        }
                        
                        // Fallback: try to extract from container's own text
                        let containerText = container.innerText || container.textContent;
                        if (containerText) {
                            let lines = containerText.split('\\n').map(l => l.trim()).filter(l => l);
                            if (lines.length > 0) {
                                return lines[0];
                            }
                        }
                        
                        return null;
                    }
                """, href)
                
                if not section_name or not section_name.strip():
                    section_name = "Unsorted"
                else:
                    section_name = safe_filename(section_name.strip())
            except Exception as e:
                print(f"  ⚠ Warning: Could not extract section for {url}: {e}")
                section_name = "Unsorted"
            
            # Extract link text as title
            title = link_info.get('text') or None
            if title:
                title = title.strip()
                if not title:
                    title = None
            
            resource_links.append(ResourceLink(
                url=url,
                section=section_name,
                title=title
            ))
        
        return resource_links
    
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
    
    def create_section_folder(self, section_name: str) -> Path:
        """
        Create a folder for a Moodle section.
        
        Args:
            section_name: Name of the section (already filesystem-safe)
            
        Returns:
            Path to the section folder
        """
        section_folder = self.cfg.out_dir / section_name
        section_folder.mkdir(parents=True, exist_ok=True)
        return section_folder
    
    def run(self, downloader=None) -> None:
        """
        Main execution method with section-based folder organization.
        
        Overrides BaseScraper.run() to use section-based folder structure.
        Downloads are organized by Moodle section/topic, not by URL path.
        """
        from app.components.downloader import create_downloader
        from playwright.sync_api import sync_playwright
        
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
            
            # Collect resource links with section information
            resource_links = self.collect_resource_links(page)
            print(f"Found: {len(resource_links)} resources")
            
            # Group by section for better output
            sections = {}
            for rl in resource_links:
                if rl.section not in sections:
                    sections[rl.section] = []
                sections[rl.section].append(rl)
            
            print(f"  In {len(sections)} Sections: {', '.join(sections.keys())}")
            
            for i, resource_link in enumerate(resource_links, 1):
                url = resource_link.url
                section = resource_link.section
                title = resource_link.title
                
                print(f"[{i}/{len(resource_links)}] Section: {section} | {title or url}")
                
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                except PlaywrightTimeoutError:
                    print(f"  ⚠ Timeout loading page, continuing...")
                    continue
                except Exception as e:
                    print(f"  ⚠ Error loading page: {e}")
                    continue
                
                # Create section folder
                section_folder = self.create_section_folder(section)
                
                # Save PDF if configured (optional, can be disabled)
                # For now, we'll skip PDF saving and focus on attachments
                # If you want PDFs, uncomment:
                # self.save_pdf(page, section_folder)
                
                # Save attachments in section folder
                n = self._save_attachments(page, section_folder, downloader, title)
                if n:
                    print(f"  ✓ {n} file(s) saved to: {section_folder}")
            
            ctx.close()
    
    def _save_attachments(self, page: Page, section_folder: Path, downloader, preferred_title: str | None = None) -> int:
        """
        Save attachments for the current page in section folder.
        
        Args:
            page: Current Playwright page
            section_folder: Section folder to save attachments in
            downloader: Downloader instance to use
            preferred_title: Preferred filename (from link text)
            
        Returns:
            Number of successfully saved files
        """
        # Save directly in section folder (no "attachments" subfolder)
        # This matches the user's requirement: files go directly into section folders
        
        links = self.collect_attachments(page)
        if not links:
            return 0
        
        saved = 0
        
        for url in links:
            try:
                # Use preferred_title if available, otherwise let downloader determine filename
                filename = downloader.download(page, url, section_folder, preferred_title=preferred_title)
                if filename:
                    saved += 1
            except Exception as e:
                print(f"  ⚠ failed: {url} ({e})")
        
        return saved

