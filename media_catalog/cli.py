import argparse
import csv
import json
import os
import re
from pathlib import Path
from importlib import resources

from dotenv import load_dotenv

from media_catalog.epub import build_epub
from media_catalog.merge import merge_pdfs
from media_catalog.omdb import fetch_movie, fetch_series_episodes_count, search_omdb
from media_catalog.render import render_movie_page, render_separator_page
from media_catalog.util import ensure_dir, parse_imdb_id, slugify_title


def read_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), (reader.fieldnames or [])


def write_rows(csv_path, rows, fieldnames):
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_afi_list(filename):
    try:
        afi_path = resources.files("media_catalog").joinpath("data", filename)
    except FileNotFoundError:
        return []
    if not afi_path.exists():
        return []
    with afi_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def afi_lookup_map(entries):
    by_title_year = {}
    by_imdb = {}
    for entry in entries:
        imdb_id = (entry.get("imdb_id") or "").strip()
        if imdb_id:
            by_imdb[imdb_id] = entry
        key = (entry["title"].strip().lower(), entry["year"])
        by_title_year[key] = entry
    return by_title_year, by_imdb


def list_lookup_map(entries):
    by_title_year = {}
    by_imdb = {}
    for entry in entries:
        imdb_id = (entry.get("imdb_id") or "").strip()
        if imdb_id:
            by_imdb[imdb_id] = entry
        title = (entry.get("title") or "").strip().lower()
        year = entry.get("year") or ""
        if title:
            by_title_year[(title, year)] = entry
    return by_title_year, by_imdb


def movie_year_key(value):
    if not value:
        return ""
    match = re.search(r"\d{4}", value)
    return match.group(0) if match else ""


def movie_year_int(value):
    year = movie_year_key(value)
    if not year:
        return 9999
    return int(year)


def resolve_imdb_id(row, column):
    value = row.get(column, "").strip()
    return parse_imdb_id(value)


def title_sort_key(title):
    if not title:
        return ""
    lowered = title.strip().lower()
    for article in ("the ", "a ", "an "):
        if lowered.startswith(article):
            return lowered[len(article) :]
    return lowered


def primary_genre(movie):
    genre = (movie.get("Genre") or "").strip()
    if not genre or genre == "N/A":
        return "Uncategorized"
    return genre.split(",")[0].strip()


def genre_override(row):
    value = (row.get("genre_override") or "").strip()
    return value or None


def series_override(row):
    value = (row.get("series") or "").strip()
    return value or None


def sort_title_for(movie):
    return movie.get("Title", "")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate A5 movie catalog pages from a CSV of IMDb links/IDs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate catalog PDFs/EPUB from a CSV")
    gen.add_argument("--input", required=True, help="Path to input CSV")
    gen.add_argument(
        "--imdb-column",
        default="imdb",
        help="CSV column containing IMDb link or ID (default: imdb)",
    )
    gen.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write PDFs (default: output)",
    )
    gen.add_argument(
        "--pages-dir",
        default="pages",
        help="Subdirectory for per-movie PDFs (default: pages)",
    )
    gen.add_argument(
        "--combined",
        default="catalog.pdf",
        help="Combined PDF filename (default: catalog.pdf)",
    )
    gen.add_argument(
        "--epub",
        action="store_true",
        help="Generate an EPUB alongside the PDF output",
    )
    gen.add_argument(
        "--epub-name",
        default="catalog.epub",
        help="EPUB filename (default: catalog.epub)",
    )
    gen.add_argument(
        "--left-margin-mm",
        type=float,
        default=25.0,
        help="Left margin in mm for hole punch clearance (default: 25)",
    )
    gen.add_argument(
        "--no-poster",
        action="store_true",
        help="Skip downloading posters",
    )
    gen.add_argument(
        "--cache-dir",
        default=".cache/omdb",
        help="Directory to cache OMDb responses (default: .cache/omdb)",
    )
    gen.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache reads and writes",
    )
    gen.add_argument(
        "--overrides-dir",
        default=".overrides",
        help="Directory of manual override JSON files named <imdb_id>.json (default: .overrides)",
    )

    srch = subparsers.add_parser("search", help="Search OMDb by title")
    srch.add_argument("query", help="Title to search for")
    srch.add_argument("--year", help="Optional year to narrow results")

    return parser


def load_override(overrides_dir, imdb_id):
    path = Path(overrides_dir) / f"{imdb_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("imdbID", imdb_id)
    return data


def cmd_search(args, api_key):
    results = search_omdb(args.query, api_key, year=args.year)
    if not results:
        print(f"No results found on OMDb for '{args.query}'")
        return
    print(f"{'IMDb ID':<12} {'Year':<6} {'Type':<8} Title")
    print("-" * 60)
    for r in results:
        print(f"{r.get('imdbID', ''):<12} {r.get('Year', ''):<6} {r.get('Type', ''):<8} {r.get('Title', '')}")


def main():
    parser = build_parser()
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key:
        raise SystemExit("OMDB_API_KEY is required to fetch movie data.")

    if args.command == "search":
        cmd_search(args, api_key)
        return

    output_root = Path(args.output_dir)
    pages_root = output_root / args.pages_dir
    ensure_dir(pages_root)

    afi_1998 = load_afi_list("afi_top_100_1998.csv")
    afi_2007 = load_afi_list("afi_top_100_2007.csv")
    afi_1998_map, afi_1998_imdb = afi_lookup_map(afi_1998)
    afi_2007_map, afi_2007_imdb = afi_lookup_map(afi_2007)
    imdb_top_250 = load_afi_list("imdb_top_250.csv")
    imdb_top_250_map, imdb_top_250_imdb = list_lookup_map(imdb_top_250)
    palme_dor = load_afi_list("cannes_palme_dor.csv")
    palme_dor_map, palme_dor_imdb = list_lookup_map(palme_dor)
    bfi_sight_sound = load_afi_list("bfi_sight_sound.csv")
    bfi_map, bfi_imdb = list_lookup_map(bfi_sight_sound)
    imdb_top_250_tv = load_afi_list("imdb_top_250_tv.csv")
    imdb_top_250_tv_map, imdb_top_250_tv_imdb = list_lookup_map(imdb_top_250_tv)

    rows, fieldnames = read_rows(args.input)
    for column in ("series", "title"):
        if column not in fieldnames:
            fieldnames.append(column)

    collected = []
    def is_placeholder_plot(value):
        if not value or value == "N/A":
            return True
        lowered = value.strip().lower()
        if "plot is unknown" in lowered:
            return True
        return False

    def truncate_plot(value, max_len):
        if not value or value == "N/A":
            return value
        if len(value) <= max_len:
            return value
        cutoff = value[:max_len]
        for marker in (". ", "! ", "? "):
            idx = cutoff.rfind(marker)
            if idx != -1:
                return cutoff[: idx + 1].strip()
        return cutoff.rstrip() + "..."

    plot_length_threshold = 800
    for row in rows:
        imdb_id = resolve_imdb_id(row, args.imdb_column)
        if not imdb_id:
            print(f"Skipping row without IMDb id in column '{args.imdb_column}': {row}")
            continue
        override = genre_override(row)
        series_name = series_override(row)

        movie = fetch_movie(
            imdb_id,
            api_key,
            cache_dir=args.cache_dir,
            use_cache=not args.no_cache,
        )
        file_override = load_override(args.overrides_dir, imdb_id)
        if file_override:
            title_hint = file_override.get("Title", (movie or {}).get("Title", ""))
            print(f"Applying manual override for {imdb_id}: {title_hint}")
            if movie is None:
                movie = file_override
            else:
                movie.update(file_override)
        if not movie:
            print(f"Skipping IMDb id {imdb_id}: not found in OMDb (title may exist on IMDb but not yet indexed by OMDb)")
            row_title = (row.get("title") or "").strip()
            if row_title:
                suggestions = search_omdb(row_title, api_key)
                if suggestions:
                    print(f"  OMDb search results for '{row_title}':")
                    for s in suggestions[:5]:
                        print(f"    {s.get('imdbID', ''):<12} {s.get('Year', ''):<6} {s.get('Type', ''):<8} {s.get('Title', '')}")
                else:
                    print(f"  No OMDb results found for '{row_title}'")
            continue

        plot = movie.get("Plot", "")
        if is_placeholder_plot(plot):
            short_movie = fetch_movie(
                imdb_id,
                api_key,
                cache_dir=args.cache_dir,
                use_cache=not args.no_cache,
                plot="short",
            )
            short_plot = (short_movie or {}).get("Plot", "")
            short_is_placeholder = is_placeholder_plot(short_plot)
            if not short_is_placeholder:
                movie["Plot"] = short_plot
                plot = short_plot
        if plot and plot != "N/A" and len(plot) > plot_length_threshold:
            movie["Plot"] = truncate_plot(plot, plot_length_threshold)

        if movie.get("Type") == "series" and not movie.get("totalEpisodes"):
            total_seasons = movie.get("totalSeasons")
            total_episodes = fetch_series_episodes_count(
                imdb_id,
                api_key,
                total_seasons,
                cache_dir=args.cache_dir,
                use_cache=not args.no_cache,
            )
            if total_episodes:
                movie["totalEpisodes"] = total_episodes
        imdb_id_value = movie.get("imdbID", "")
        title_key = (movie.get("Title", "").strip().lower(), movie_year_key(movie.get("Year", "")))
        afi_entry_1998 = afi_1998_imdb.get(imdb_id_value) or afi_1998_map.get(title_key)
        afi_entry_2007 = afi_2007_imdb.get(imdb_id_value) or afi_2007_map.get(title_key)
        imdb_top_250_entry = imdb_top_250_imdb.get(imdb_id_value) or imdb_top_250_map.get(title_key)
        palme_dor_entry = palme_dor_imdb.get(imdb_id_value) or palme_dor_map.get(title_key)
        bfi_entry = bfi_imdb.get(imdb_id_value) or bfi_map.get(title_key)
        imdb_top_250_tv_entry = imdb_top_250_tv_imdb.get(imdb_id_value) or imdb_top_250_tv_map.get(title_key)
        if afi_entry_1998:
            movie["AFI1998Rank"] = afi_entry_1998.get("rank")
        if afi_entry_2007:
            movie["AFI2007Rank"] = afi_entry_2007.get("rank")
        if imdb_top_250_entry:
            movie["IMDbTop250Rank"] = imdb_top_250_entry.get("rank")
        if imdb_top_250_tv_entry:
            movie["IMDbTop250TVRank"] = imdb_top_250_tv_entry.get("rank")
        if palme_dor_entry:
            movie["CannesPalmeDorYear"] = palme_dor_entry.get("year")
        if bfi_entry:
            movie["BFISightAndSoundRank"] = bfi_entry.get("rank")
        if override:
            movie["GenreOverride"] = override
        if series_name:
            movie["SeriesName"] = series_name
        row["title"] = movie.get("Title", "")
        collected.append((imdb_id, movie))

    write_rows(args.input, rows, fieldnames)

    collected.sort(
        key=lambda item: (
            1 if item[1].get("Type") == "series" else 0,
            title_sort_key(item[1].get("SeriesName", "")) if item[1].get("SeriesName") else title_sort_key(sort_title_for(item[1])),
            movie_year_int(item[1].get("Year", "")) if item[1].get("SeriesName") else 0,
            title_sort_key(sort_title_for(item[1])),
        )
    )

    generated_pages = []
    movies = [item for item in collected if item[1].get("Type") != "series"]
    series = [item for item in collected if item[1].get("Type") == "series"]

    def render_group(label, items):
        if not items:
            return
        section_path = pages_root / f"{slugify_title(label)}_section.pdf"
        render_separator_page(label, section_path, left_margin_mm=args.left_margin_mm)
        generated_pages.append(section_path)

        by_genre = {}
        for imdb_id, movie in items:
            genre_key = movie.get("GenreOverride") or primary_genre(movie)
            by_genre.setdefault(genre_key, []).append((imdb_id, movie))

        for genre_key in sorted(by_genre.keys(), key=str.lower):
            genre_section = pages_root / f"{slugify_title(label)}_{slugify_title(genre_key)}_section.pdf"
            render_separator_page(genre_key, genre_section, left_margin_mm=args.left_margin_mm)
            generated_pages.append(genre_section)
            genre_items = sorted(
                by_genre[genre_key],
                key=lambda item: (
                    title_sort_key(item[1].get("SeriesName", "")) if item[1].get("SeriesName") else title_sort_key(sort_title_for(item[1])),
                    movie_year_int(item[1].get("Year", "")) if item[1].get("SeriesName") else 0,
                    title_sort_key(sort_title_for(item[1])),
                ),
            )
            for imdb_id, movie in genre_items:
                title_slug = slugify_title(movie.get("Title", ""))
                if title_slug:
                    filename = f"{title_slug}_{imdb_id}.pdf"
                else:
                    filename = f"{imdb_id}.pdf"
                page_path = pages_root / filename
                render_movie_page(
                    movie,
                    page_path,
                    left_margin_mm=args.left_margin_mm,
                    include_poster=not args.no_poster,
                    poster_cache_dir=None if args.no_cache else args.cache_dir,
                )
                generated_pages.append(page_path)

    render_group("Movies", movies)
    render_group("TV Shows", series)

    def build_section(label, items):
        if not items:
            return None
        by_genre = {}
        for imdb_id, movie in items:
            genre_key = movie.get("GenreOverride") or primary_genre(movie)
            by_genre.setdefault(genre_key, []).append((imdb_id, movie))
        genres = []
        for genre_key in sorted(by_genre.keys(), key=str.lower):
            genre_items = sorted(
                by_genre[genre_key],
                key=lambda item: (
                    title_sort_key(item[1].get("SeriesName", ""))
                    if item[1].get("SeriesName")
                    else title_sort_key(sort_title_for(item[1])),
                    movie_year_int(item[1].get("Year", "")) if item[1].get("SeriesName") else 0,
                    title_sort_key(sort_title_for(item[1])),
                ),
            )
            genres.append((genre_key, genre_items))
        return (label, genres)

    sections = []
    movies_section = build_section("Movies", movies)
    if movies_section:
        sections.append(movies_section)
    series_section = build_section("TV Shows", series)
    if series_section:
        sections.append(series_section)

    if generated_pages:
        combined_path = output_root / args.combined
        merge_pdfs(generated_pages, combined_path)
        print(f"Generated {len(generated_pages)} pages and {combined_path}")
    else:
        print("No pages generated.")

    if args.epub:
        if sections:
            epub_path = output_root / args.epub_name
            build_epub(
                sections,
                epub_path,
                include_poster=not args.no_poster,
                poster_cache_dir=None if args.no_cache else args.cache_dir,
            )
            print(f"Generated EPUB at {epub_path}")
        else:
            print("No EPUB generated.")


if __name__ == "__main__":
    main()
