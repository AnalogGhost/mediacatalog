from pathlib import Path

import requests


def fetch_poster_cached(url, imdb_id=None, cache_dir=None):
    if not url or url == "N/A":
        return None, None, None

    cache_root = None
    if cache_dir and imdb_id:
        cache_root = Path(cache_dir) / "posters"
        for ext, content_type in (
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("png", "image/png"),
            ("webp", "image/webp"),
        ):
            candidate = cache_root / f"{imdb_id}.{ext}"
            if candidate.exists():
                return candidate.read_bytes(), content_type, ext

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"
    else:
        ext = "jpg"
    data = response.content

    if cache_root:
        cache_root.mkdir(parents=True, exist_ok=True)
        (cache_root / f"{imdb_id}.{ext}").write_bytes(data)

    if not content_type:
        content_type = f"image/{ext}"
    return data, content_type, ext
