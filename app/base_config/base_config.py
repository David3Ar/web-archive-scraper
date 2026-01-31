"""
Base configuration for all scrapers.
"""
from dataclasses import dataclass
from pathlib import Path


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
    
    # File replacement policy: If True, existing files will be replaced. If False, downloads will be skipped if file exists.
    replace_existing_files: bool = False

