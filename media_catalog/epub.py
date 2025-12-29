import html
from pathlib import Path

from ebooklib import epub

from media_catalog.poster import fetch_poster_cached
from media_catalog.util import slugify_title


def _fetch_poster(url, imdb_id=None, cache_dir=None):
    data, content_type, ext = fetch_poster_cached(url, imdb_id=imdb_id, cache_dir=cache_dir)
    if not data:
        return None, None, None
    return data, content_type, ext


def _movie_subtitle(movie):
    year = movie.get("Year", "")
    rated = movie.get("Rated", "")
    runtime = movie.get("Runtime", "")
    genre = movie.get("Genre", "")
    media_type = movie.get("Type", "")
    total_seasons = movie.get("totalSeasons", "")
    total_episodes = movie.get("totalEpisodes", "")
    if media_type == "series":
        seasons_text = f"{total_seasons} seasons" if total_seasons else ""
        episodes_text = f"{total_episodes} episodes" if total_episodes else ""
        if seasons_text and episodes_text:
            runtime = f"{seasons_text}, {episodes_text}"
        elif seasons_text or episodes_text:
            runtime = seasons_text or episodes_text
        else:
            runtime = ""
    bits = [year, runtime, rated, genre]
    bits = [bit for bit in bits if bit and bit != "N/A"]
    return " • ".join(bits)


def _movie_details(movie):
    rotten = ""
    for rating in movie.get("Ratings", []):
        if rating.get("Source") == "Rotten Tomatoes":
            rotten = rating.get("Value", "")
            break
    metascore = movie.get("Metascore", "")
    details = [
        ("Released", movie.get("Released", "")),
        ("Country", movie.get("Country", "")),
        ("Language", movie.get("Language", "")),
        ("IMDb", movie.get("imdbRating", "")),
        ("Metacritic", f"{metascore}/100" if metascore and metascore != "N/A" else metascore),
        ("Rotten Tomatoes", rotten),
        ("Director", movie.get("Director", "")),
        ("Writer", movie.get("Writer", "")),
    ]
    return [(label, value) for label, value in details if value and value != "N/A"]


def _list_badges(movie):
    items = []
    if movie.get("AFI1998Rank"):
        items.append(f"AFI 100 (1998) #{movie['AFI1998Rank']}")
    if movie.get("AFI2007Rank"):
        items.append(f"AFI 100 (2007) #{movie['AFI2007Rank']}")
    if movie.get("IMDbTop250Rank"):
        items.append(f"IMDb Top 250 #{movie['IMDbTop250Rank']}")
    if movie.get("IMDbTop250TVRank"):
        items.append(f"IMDb Top 250 TV #{movie['IMDbTop250TVRank']}")
    if movie.get("BFISightAndSoundRank"):
        items.append(f"BFI Sight & Sound #{movie['BFISightAndSoundRank']}")
    if movie.get("CannesPalmeDorYear"):
        items.append(f"Palme d'Or winner ({movie['CannesPalmeDorYear']})")
    return items


def _wrap_html(body):
    return f"""
<html>
  <head>
    <link rel="stylesheet" type="text/css" href="style/style.css" />
  </head>
  <body>
    {body}
  </body>
</html>
"""


def _movie_html(movie, poster_ref):
    title = html.escape(movie.get("Title", "Untitled"))
    subtitle = html.escape(_movie_subtitle(movie))
    series_name = movie.get("SeriesName", "")
    series_html = (
        f'<p class="series"><strong>Series:</strong> {html.escape(series_name)}</p>'
        if series_name
        else ""
    )
    plot = movie.get("Plot", "")
    plot_html = f"<p>{html.escape(plot)}</p>" if plot and plot != "N/A" else ""
    imdb_id = movie.get("imdbID", "")
    imdb_link = (
        f'<p class="imdb"><a href="https://www.imdb.com/title/{imdb_id}/">IMDb</a></p>'
        if imdb_id
        else ""
    )
    poster_html = (
        f'<div class="poster"><img src="{poster_ref}" alt="{title}" /></div>'
        if poster_ref
        else ""
    )
    details = _movie_details(movie)
    details_html = ""
    if details:
        rows = "".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
            for label, value in details
        )
        details_html = f'<table class="details">{rows}</table>'
    badges = _list_badges(movie)
    badges_html = (
        '<p class="badges">' + " • ".join(html.escape(b) for b in badges) + "</p>"
        if badges
        else ""
    )
    body = f"""
    <h1>{title}</h1>
    <p class="subtitle">{subtitle}</p>
    {series_html}
    {poster_html}
    {details_html}
    {badges_html}
    {plot_html}
    {imdb_link}
    """
    return _wrap_html(body)


def build_epub(sections, output_path, include_poster=True, poster_cache_dir=None):
    book = epub.EpubBook()
    book.set_identifier("media-catalog")
    book.set_title("MediaCatalog")
    book.set_language("en")

    style = """
    body { font-family: serif; line-height: 1.4; }
    h1 { font-size: 1.6em; margin-bottom: 0.2em; }
    h2 { font-size: 1.2em; margin-top: 1.6em; }
    .subtitle { color: #555; margin-top: 0; }
    .series { color: #444; margin-top: 0; font-style: italic; }
    .poster img { max-width: 60%; height: auto; display: block; margin: 0.8em 0; }
    .details { width: 100%; border-collapse: collapse; margin: 0.6em 0 0.6em; }
    .details th { text-align: left; padding: 0.2em 0.4em 0.2em 0; width: 30%; }
    .details td { padding: 0.2em 0; }
    .badges { font-style: italic; color: #444; }
    .section { text-align: center; }
    """
    style_item = epub.EpubItem(
        uid="style_nav",
        file_name="style/style.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(style_item)

    chapters = []

    for section_label, genres in sections:
        section_slug = slugify_title(section_label) or "section"
        section_page = epub.EpubHtml(
            title=section_label,
            file_name=f"{section_slug}.xhtml",
            lang="en",
        )
        section_page.content = _wrap_html(
            f'<h1 class="section">{html.escape(section_label)}</h1>'
        )
        section_page.add_item(style_item)
        book.add_item(section_page)
        chapters.append(section_page)

        for genre_label, items in genres:
            genre_slug = slugify_title(f"{section_label}-{genre_label}") or "genre"
            genre_page = epub.EpubHtml(
                title=f"{section_label} - {genre_label}",
                file_name=f"{genre_slug}.xhtml",
                lang="en",
            )
            genre_page.content = _wrap_html(
                f'<h2 class="section">{html.escape(genre_label)}</h2>'
            )
            genre_page.add_item(style_item)
            book.add_item(genre_page)
            chapters.append(genre_page)

            for imdb_id, movie in items:
                poster_ref = None
                title_slug = slugify_title(movie.get("Title", "")) or imdb_id
                filename = f"{title_slug}_{imdb_id}.xhtml"
                if include_poster:
                    poster_bytes, media_type, ext = _fetch_poster(
                        movie.get("Poster"),
                        imdb_id=movie.get("imdbID"),
                        cache_dir=poster_cache_dir,
                    )
                    if poster_bytes:
                        poster_name = f"images/{title_slug}_{imdb_id}.{ext}"
                        image_item = epub.EpubItem(
                            uid=poster_name,
                            file_name=poster_name,
                            media_type=media_type,
                            content=poster_bytes,
                        )
                        book.add_item(image_item)
                        poster_ref = poster_name

                chapter = epub.EpubHtml(
                    title=movie.get("Title", "Untitled"),
                    file_name=filename,
                    lang="en",
                )
                chapter.content = _movie_html(movie, poster_ref)
                chapter.add_item(style_item)
                book.add_item(chapter)
                chapters.append(chapter)

    book.toc = chapters
    book.spine = ["nav"] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book)
