"""
Configuration for Theoinf course on Moodle platform.
"""
import sys
from pathlib import Path

# Add project root to path so 'app' module can be imported
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dataclasses import dataclass
from typing import Optional

from app.base_config.moodle_config import MoodleConfig


@dataclass(frozen=True)
class TheoinfConfig(MoodleConfig):
    """
    Configuration for Theoinf course scraper.
    Extends MoodleConfig with Theoinf-specific settings.
    """
    # Base URLs / Navigation (Theoinf-specific)
    start_path: str = "/course/view.php?id=19620"  # Theoinf course ID
    
    # Runtime / Browser settings (Theoinf-specific overrides)
    profile_dir: str = ".pw_profile_theoinf"    # Separate profile for Theoinf
    out_dir: Path = Path("data/theoinf")        # Output directory for Theoinf
    headless: bool = False                      # run browser without UI
    replace_existing_files: bool = False

def main() -> None:
    """Main entry point for Theoinf scraper."""
    from app.components.base import create_scraper
    
    # Optionally specify which Moodle module types to scrape
    # Default: ("/mod/resource/view.php", "/mod/folder/view.php")
    # You can add more like "/mod/url/view.php", "/mod/page/view.php", etc.
    cfg = TheoinfConfig(
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

