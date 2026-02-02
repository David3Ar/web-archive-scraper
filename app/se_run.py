"""
Configuration for SE (Software Engineering) course on Roeselite platform.
"""
import sys
from pathlib import Path

# Add project root to path so 'app' module can be imported
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dataclasses import dataclass

from app.base_config.roeselite_config import RoeseliteConfig


@dataclass(frozen=True)
class SEConfig(RoeseliteConfig):
    """
    Configuration for SE (Software Engineering) course scraper.
    Extends RoeseliteConfig with SE-specific settings.
    """
    
    base: str = "https://se.cs.ovgu.de"

    profile_dir: str = ".pw_profile_se"      # persistent browser profile (cookies, session)
    out_dir: Path = Path("data/se-itpm")      # root output directory

    allowed_resource_hosts: tuple[str, ...] = ("se.cs.ovgu.de",)


def main() -> None:
    """Main entry point for SE scraper."""
    from app.components.base import create_scraper
    
    cfg = SEConfig()
    scraper = create_scraper(cfg)
    scraper.run()


if __name__ == "__main__":
    main()