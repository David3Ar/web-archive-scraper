from dataclasses import dataclass
from pathlib import Path

from components.base import BaseConfig


@dataclass(frozen=True)
class SEConfig(BaseConfig):
    """
    Configuration for SE (Software Engineering) platform scraper.
    Extends BaseConfig with SE-specific settings.
    """
    # Base URLs / Navigation
    base: str = "https://se.cs.ovgu.de"
    start_path: str = "/assignments"
    login_path: str = "/users/login"
    
    # Login form selectors
    sel_user: str = 'input[type="text"]'
    sel_pass: str = 'input[type="password"]'
    sel_submit: str = 'input[type="submit"]'
    
    # Security: Restrict downloads to trusted hosts only
    allowed_resource_hosts: tuple[str, ...] = ("se.cs.ovgu.de",)
    
    # Resource download policy
    include_mode_raw: bool = False            # save raw/text views (?mode=raw)
    include_mode_dl: bool = True              # save download links (?mode=dl)
    include_archive_zip: bool = True          # allow .zip archives
    include_archive_tgz: bool = False         # allow .tgz / .tar.gz / .gz archives
    include_images: bool = False              # allow image files (png, jpg, jpeg)
    include_pdfs: bool = False                # allow PDF files
    include_url_txt: bool = False             # write a url.txt file per page
    
    # Runtime / Browser settings
    profile_dir: str = ".pw_profile_se"      # persistent browser profile (cookies, session)
    out_dir: Path = Path("data/se2526")      # root output directory
    pdf_format: str = "A4"                    # PDF page size
    print_background: bool = True             # include background graphics in PDFs
    headless: bool = True                     # run browser without UI
    
    # Downloader strategy: "request", "click", or "auto"
    downloader_strategy: str = "auto"
    
    # Page filtering (SE-specific)
    include_submissions: bool = False         # also process secondary/detail pages (optional)
    
    @property
    def allow_path_regex(self) -> str:
        """Get regex pattern for filtering assignment URLs."""
        if self.include_submissions:
            # process both primary and secondary pages
            return r"^/(assignment|submission)/view/"
        else:
            # process primary pages only
            return r"^/assignment/view/"


def main() -> None:
    """Main entry point for SE scraper."""
    from components.base import create_scraper
    
    cfg = SEConfig()
    scraper = create_scraper(cfg)
    scraper.run()


if __name__ == "__main__":
    main()