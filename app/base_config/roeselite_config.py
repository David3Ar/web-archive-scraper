"""
Base configuration for Roeselite platform scraper.
"""
from dataclasses import dataclass
from pathlib import Path

from app.base_config.base_config import BaseConfig


@dataclass(frozen=True)
class RoeseliteConfig(BaseConfig):
    """
    Base configuration for Roeselite assignment platform scraper.
    Extends BaseConfig with Roeselite-specific settings.
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
    allowed_resource_hosts: tuple[str, ...] = ("*.cs.ovgu.de",)
    
    # Runtime / Browser settings
    profile_dir: str = ".pw_profile_roeselite"
    out_dir: Path = Path("data/roeselite-fallback")
    
    
    #########################################################
    # Roeselite-specific settings
    #########################################################
    
    # Page filtering
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

