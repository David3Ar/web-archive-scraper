"""
Base configuration for Moodle scraper.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.base_config.base_config import BaseConfig


@dataclass(frozen=True)
class MoodleConfig(BaseConfig):
    """
    Base configuration for Moodle learning platform scraper.
    Extends BaseConfig with Moodle-specific settings.
    """
    # Base URLs / Navigation
    base: str = "https://elearning.ovgu.de"  # Adjust to your Moodle instance
    start_path: str = "/course/view.php?id=XXXXX"  # Replace XXXXX with your course ID
    login_path: str = "/login/index.php"
    
    # Login form selectors (adjust if your Moodle uses different selectors)
    sel_user: str = 'input[type="text"]'
    sel_pass: str = 'input[type="password"]'
    sel_submit: str = 'button[type="submit"]'
    
    # Security: Restrict downloads to trusted hosts only
    allowed_resource_hosts: tuple[str, ...] = ("elearning.ovgu.de",)
    
    profile_dir: str = ".pw_profile_moodle"
    out_dir: Path = Path("data/moodle-fallback")
    
    headless: bool = False # Moodle currently needs headless

    
    #########################################################
    # Moodle-specific settings
    #########################################################
    
    # Which module types to scrape ?
    resource_module_patterns: Optional[tuple[str, ...]] = None # use default: ("/mod/resource/view.php", "/mod/folder/view.php")
        # "/mod/url/view.php",  # if you want to scrape URL resources
        # "/mod/page/view.php"  # if you want to scrape Page resources
