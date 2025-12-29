import re
from pathlib import Path

IMDB_ID_RE = re.compile(r"(tt\d{7,9})")


def parse_imdb_id(value):
    if not value:
        return None
    match = IMDB_ID_RE.search(value)
    if match:
        return match.group(1)
    return None


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def slugify_title(value):
    if not value:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.lower()
