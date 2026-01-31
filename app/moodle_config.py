"""
Example configuration for Moodle scraper.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from components.base import BaseConfig


@dataclass(frozen=True)
class MoodleConfig(BaseConfig):
    """
    Configuration for Moodle learning platform scraper.
    Extends BaseConfig with Moodle-specific settings.
    """
    # Base URLs / Navigation
    base: str = "https://elearning.ovgu.de"  # Adjust to your Moodle instance
    start_path: str = "/course/view.php?id=XXXXX"  # Replace XXXXX with your course ID
    login_path: str = "/login/index.php"
    
    # Login form selectors (adjust if your Moodle uses different selectors)
    sel_user: str = 'input[name="username"]'
    sel_pass: str = 'input[name="password"]'
    sel_submit: str = 'button[type="submit"]'
    
    # Security: Restrict downloads to trusted hosts only
    allowed_resource_hosts: tuple[str, ...] = ("elearning.ovgu.de",)
    
    # Resource download policy
    include_mode_raw: bool = False
    include_mode_dl: bool = True
    include_archive_zip: bool = True
    include_archive_tgz: bool = False
    include_images: bool = False
    include_pdfs: bool = True                 # Enable PDF downloads for Moodle
    include_url_txt: bool = False
    
    # Runtime / Browser settings
    profile_dir: str = ".pw_profile_moodle"   # Separate profile for Moodle
    out_dir: Path = Path("data/moodle")       # Output directory
    pdf_format: str = "A4"
    print_background: bool = True
    headless: bool = True
    
    # Downloader strategy: "request", "click", or "auto"
    # "auto" is recommended for Moodle as some resources require click-based downloads
    downloader_strategy: str = "auto"
    
    # Moodle-specific: Which module types to scrape
    # None = use default ("/mod/resource/view.php", "/mod/folder/view.php")
    resource_module_patterns: Optional[tuple[str, ...]] = None


def main() -> None:
    """Main entry point for Moodle scraper."""
    from components.base import create_scraper
    
    # Optionally specify which Moodle module types to scrape
    # Default: ("/mod/resource/view.php", "/mod/folder/view.php")
    # You can add more like "/mod/url/view.php", "/mod/page/view.php", etc.
    cfg = MoodleConfig(
        resource_module_patterns=(
            "/mod/resource/view.php",
            "/mod/folder/view.php",
            # "/mod/url/view.php",  # Uncomment if you want to scrape URL resources
        )
    )
    
    scraper = create_scraper(cfg)
    scraper.run()


if __name__ == "__main__":
    main()

