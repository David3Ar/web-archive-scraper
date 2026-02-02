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
    start_path: str = "/course/view.php?id=19620"  # Theoinf I WS25/26 course ID
    out_dir: Path = Path("data/theo-inf")       



def main() -> None:
    """Main entry point for Theoinf scraper."""
    from app.components.base import create_scraper

    cfg = TheoinfConfig() 
    scraper = create_scraper(cfg)
    scraper.run()


if __name__ == "__main__":
    main()

