import json
from pathlib import Path

import requests


def _cache_path(cache_dir, imdb_id, plot):
    return Path(cache_dir) / f"{imdb_id}_{plot}.json"


def _season_cache_path(cache_dir, imdb_id, season):
    return Path(cache_dir) / f"{imdb_id}_season_{season}.json"


def fetch_movie(imdb_id, api_key, cache_dir=None, use_cache=True, plot="full"):
    if cache_dir and use_cache:
        cached = _cache_path(cache_dir, imdb_id, plot)
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))

    url = "https://www.omdbapi.com/"
    params = {"i": imdb_id, "apikey": api_key, "plot": plot}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if data.get("Response") != "True":
        return None

    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        _cache_path(cache_dir, imdb_id, plot).write_text(
            json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8"
        )
    return data


def fetch_series_episodes_count(imdb_id, api_key, total_seasons, cache_dir=None, use_cache=True):
    if not total_seasons or total_seasons == "N/A":
        return ""
    try:
        seasons = int(total_seasons)
    except ValueError:
        return ""

    total_episodes = 0
    for season in range(1, seasons + 1):
        season_data = None
        if cache_dir and use_cache:
            cached = _season_cache_path(cache_dir, imdb_id, season)
            if cached.exists():
                season_data = json.loads(cached.read_text(encoding="utf-8"))

        if not season_data:
            url = "https://www.omdbapi.com/"
            params = {"i": imdb_id, "apikey": api_key, "Season": season}
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            season_data = response.json()
            if cache_dir:
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                _season_cache_path(cache_dir, imdb_id, season).write_text(
                    json.dumps(season_data, ensure_ascii=True, indent=2), encoding="utf-8"
                )

        episodes = season_data.get("Episodes") or []
        total_episodes += len(episodes)

    return str(total_episodes) if total_episodes else ""
