import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl



def full_url(base: str, path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return urljoin(base, path_or_url)

def _normalize_umlauts(text: str) -> str:
    """
    Convert German umlauts and special characters to ASCII equivalents.
    Ü -> Ue, ü -> ue, Ä -> Ae, ä -> ae, Ö -> Oe, ö -> oe, ß -> ss
    """
    # German umlauts mapping
    umlaut_map = {
        'Ä': 'Ae', 'ä': 'ae',
        'Ö': 'Oe', 'ö': 'oe',
        'Ü': 'Ue', 'ü': 'ue',
        'ß': 'ss',
        'ẞ': 'SS',  # Capital ß (rare but exists)
    }
    
    result = []
    for char in text:
        if char in umlaut_map:
            result.append(umlaut_map[char])
        else:
            result.append(char)
    
    return ''.join(result)

def safe_filename(text: str, max_len: int = 90) -> str:
    """
    Create a filesystem-safe filename from text.
    Preserves German umlauts by converting them to ASCII equivalents (Ü->Ue, etc.).
    Removes or replaces other problematic characters.
    """
    if not text:
        return "page"
    
    text = text.strip()
    
    # First, normalize umlauts to ASCII equivalents
    text = _normalize_umlauts(text)
    
    # Normalize unicode (e.g., é -> e, ñ -> n)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Replace problematic filesystem characters with underscore
    # Keep: letters, numbers, dots, hyphens, underscores, spaces
    # Replace: / \ : * ? " < > | and other special chars
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    
    # Replace multiple spaces/underscores with single underscore
    text = re.sub(r'[\s_]+', '_', text)
    
    # Remove leading/trailing underscores and dots
    text = text.strip('_.')
    
    # Truncate to max length
    if len(text) > max_len:
        text = text[:max_len].rstrip('_.')
    
    # Ensure we have something left
    if not text:
        return "page"
    
    return text

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
