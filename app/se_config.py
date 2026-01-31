from dataclasses import dataclass
from pathlib import Path

from components.scraper import Scraper


@dataclass(frozen=True)
class SEConfig:
    # --------------------------------------------------
    # Base URLs / Navigationa
    # --------------------------------------------------

    # Base URL of the target website
    base: str = "https://se.cs.ovgu.de"

    # Entry page that lists all items to be processed
    start_path: str = "/assignments"

    # Login page URL (used for interactive login)
    login_path: str = "/users/login"

    # --------------------------------------------------
    # Login form selectors
    # Update these if the login page structure changes
    # --------------------------------------------------

    sel_user: str = 'input[type="text"]'
    sel_pass: str = 'input[type="password"]'
    sel_submit: str = 'input[type="submit"]'

    # --------------------------------------------------
    # Security
    # Restrict downloads to trusted hosts only
    # --------------------------------------------------

    allowed_resource_hosts = ("se.cs.ovgu.de",)

    # --------------------------------------------------
    # Ressource download policy
    # Controls which linked resources are saved
    # --------------------------------------------------

    include_mode_raw: bool = False            # save raw/text views (?mode=raw)
    include_mode_dl: bool = True              # save download links (?mode=dl)
    include_archive_zip: bool = True          # allow .zip archives
    include_archive_tgz: bool = False         # allow .tgz / .tar.gz / .gz archives
    include_images: bool = False              # allow image files (png, jpg, jpeg)
    include_pdfs: bool = False                 # allow PDF files
    include_url_txt: bool = False             # write a url.txt file per page
    include_submissions: bool = False         # also process secondary/detail pages (optional)

    # --------------------------------------------------
    # Runtime / Browser settings
    # --------------------------------------------------

    profile_dir: str = ".pw_profile_se"        # persistent browser profile (cookies, session)
    out_dir: Path = Path("data/se2526")               # root output directory

    pdf_format: str = "A4"                     # PDF page size
    print_background: bool = True              # include background graphics in PDFs
    headless: bool = True                      # run browser without UI

    # --------------------------------------------------
    # Page filtering
    # Controls which page URLs are collected from the start page
    # --------------------------------------------------

    if include_submissions:
        # process both primary and secondary pages
        allow_path_regex = r"^/(assignment|submission)/view/"
    else:
        # process primary pages only
        allow_path_regex = r"^/assignment/view/"


def main() -> None:
    cfg = SEConfig()
    Scraper(cfg).run()


if __name__ == "__main__":
    main()