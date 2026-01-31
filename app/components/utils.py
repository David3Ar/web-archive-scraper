import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl



def full_url(base: str, path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return urljoin(base, path_or_url)

def safe_filename(text: str, max_len: int = 90) -> str:
    text = (text or "").strip()
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", text).strip("_")
    return (text[:max_len] or "page")

def suggest_filename(url: str, target_dir: Path) -> str:
    p = urlparse(url)

    # Basis-Dateiname aus dem Pfad
    base_name = os.path.basename(p.path) or "file"
    base_name = safe_filename(base_name)

    candidate = target_dir / base_name
    if not candidate.exists():
        # Kein Konflikt → sauberer Name
        return base_name

    # Konflikt → relevante Query-Teile anhängen (z.B. mode)
    q = dict(parse_qsl(p.query))
    suffix = ""
    if "mode" in q:
        suffix = f"__mode={q['mode']}"

    stem, ext = os.path.splitext(base_name)
    return f"{stem}{suffix}{ext}"
