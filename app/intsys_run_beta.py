"""
Configuration for IntSys course on Moodle platform.
"""
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add project root to path so 'app' module can be imported
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
    
from app.base_config.moodle_config import MoodleConfig


@dataclass(frozen=True)
class IntSysConfig(MoodleConfig):
    """
    Configuration for IntSys course scraper.
    Extends MoodleConfig with IntSys-specific settings.
    """
    start_path: str = "/course/view.php?id=19667"  # IntSys WS25/26 course ID
    out_dir: Path = Path("data/int-sys")       



def main() -> None:
    from app.components.base import create_scraper
    
    cfg = IntSysConfig()
    scraper = create_scraper(cfg)
    scraper.run()

if __name__ == "__main__":
    main()

