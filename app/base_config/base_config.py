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
    
    # Profile settings
    profile_dir: str = ".pw_base_profile"
    
    # Output settings
    out_dir: Path = Path("data/base-fallback")
    replace_existing_files: bool = False
    
    # PDF settings
    pdf_format: str = "A4"
    print_background: bool = True
    headless: bool = True
    
    # Downloader strategy: "request", "click", or "auto" (try request first, fallback to click)
    downloader_strategy: str = "auto"
    
    # Resource download policy
    include_mode_raw: bool = False            # save raw/text views (?mode=raw)
    include_mode_dl: bool = True              # save download links (?mode=dl)
    include_archive_zip: bool = True          # allow .zip archives
    include_archive_tgz: bool = False         # allow .tgz / .tar.gz / .gz archives
    include_images: bool = False              # allow image files (png, jpg, jpeg)
    include_pdfs: bool = False                # allow PDF files
    include_url_txt: bool = False             # write a url.txt file per page