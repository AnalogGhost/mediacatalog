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


class _KoboSpanCounter:
    """Assigns Kobo's `koboSpan` paragraph ids, as kepub.epub content does.

    Kobo firmware keys its per-book reading stats, resume position, and
    in-book highlighting off `<span class="koboSpan" id="kobo.N.1">`
    wrappers around each block of text. Without them the device still
    renders the EPUB fine, it just can't drive those Kobo-only features.
    """

    def __init__(self):
        self._n = 0

    def wrap(self, fragment):
        if not fragment:
            return fragment
        self._n += 1
        return f'<span class="koboSpan" id="kobo.{self._n}.1">{fragment}</span>'


def _wrap_html(body, kepub=False):
    if kepub:
        # Kobo's own renderer expects content nested in book-columns/book-inner
        # to lay out full-justification and columns the way its own kepub
        # converter produces.
        body = f'<div id="book-columns"><div id="book-inner">{body}</div></div>'
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


def _movie_html(movie, poster_ref, kepub=False):
    span = _KoboSpanCounter()

    def wrap(fragment):
        return span.wrap(fragment) if kepub else fragment

    title = html.escape(movie.get("Title", "Untitled"))
    title_html = wrap(title)

    subtitle = html.escape(_movie_subtitle(movie))
    subtitle_html = wrap(subtitle)

    series_name = movie.get("SeriesName", "")
    series_html = (
        f'<p class="series"><strong>Series:</strong> {wrap(html.escape(series_name))}</p>'
        if series_name
        else ""
    )

    poster_html = (
        f'<div class="poster"><img src="{poster_ref}" alt="{title}" /></div>'
        if poster_ref
        else ""
    )

    details = _movie_details(movie)
    details_html = ""
    if details and kepub:
        # Plain lines rather than a table so they wrap around the floated poster.
        lines = "".join(
            f'<p class="detail"><strong>{html.escape(label)}:</strong> '
            f"{wrap(html.escape(value))}</p>"
            for label, value in details
        )
        details_html = f'<div class="details">{lines}</div>'
    elif details:
        rows = "".join(
            f"<tr><th>{html.escape(label)}</th><td>{wrap(html.escape(value))}</td></tr>"
            for label, value in details
        )
        details_html = f'<table class="details">{rows}</table>'

    badges = _list_badges(movie)
    badges_html = (
        '<p class="badges">' + wrap(" • ".join(html.escape(b) for b in badges)) + "</p>"
        if badges
        else ""
    )

    plot = movie.get("Plot", "")
    plot_html = f'<p class="plot">{wrap(html.escape(plot))}</p>' if plot and plot != "N/A" else ""

    imdb_id = movie.get("imdbID", "")
    imdb_link = (
        f'<p class="imdb"><a href="https://www.imdb.com/title/{imdb_id}/">IMDb</a></p>'
        if imdb_id
        else ""
    )

    body = f"""
    <h1>{title_html}</h1>
    <p class="subtitle">{subtitle_html}</p>
    {series_html}
    {poster_html}
    {details_html}
    {badges_html}
    {plot_html}
    {imdb_link}
    """
    return _wrap_html(body, kepub=kepub)


def _toc_page_html(entries):
    parts = []
    prev_level = 0
    for level, title, href in entries:
        if level > prev_level:
            parts.append("<ul>" * (level - prev_level))
        elif level < prev_level:
            parts.append("</li>" + "</ul></li>" * (prev_level - level))
        else:
            parts.append("</li>")
        parts.append(
            f'<li class="toc-level-{level}"><a href="{href}">{html.escape(title)}</a>'
        )
        prev_level = level
    if prev_level:
        parts.append("</li>" + "</ul></li>" * (prev_level - 1) + "</ul>")
    body = f'<h1 class="section">Table of Contents</h1><nav class="toc">{"".join(parts)}</nav>'
    return body


def build_epub(
    sections,
    output_path,
    include_poster=True,
    poster_cache_dir=None,
    book_title="MediaCatalog",
    identifier="media-catalog",
    kepub=False,
):
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(book_title)
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
    .toc ul { list-style: none; padding-left: 1.2em; }
    .toc > ul { padding-left: 0; }
    .toc a { text-decoration: none; }
    .toc-level-1 > a { font-weight: bold; }
    .toc-level-2 > a { font-style: italic; }
    """
    if kepub:
        # Tuned for the Kobo Libra Color (7in Kaleido panel, 1264x1680 @ 300ppi,
        # about 4.2 x 5.6in). Each title should fit on one screen, so the poster
        # floats left with the details wrapping beside it instead of stacking
        # above them. The book-columns/book-inner rules match what Kobo's own
        # kepub converter emits so its pagination behaves like a store book.
        style += """
        body { line-height: 1.3; }
        h1 { font-size: 1.3em; }
        .subtitle, .series { margin: 0.2em 0; }
        div#book-columns { width: 100%; height: 100%; margin: 0; padding: 0; }
        div#book-inner { width: 100%; height: 100%; margin: 0; padding: 0; }
        .poster { float: left; width: 32%; margin: 0.3em 0.7em 0.3em 0; }
        .poster img { width: 100%; max-width: 100%; margin: 0; }
        .details p.detail { margin: 0 0 0.15em 0; font-size: 0.85em; text-align: left; }
        .badges { margin: 0.6em 0 0.4em; font-size: 0.9em; clear: both; }
        p { margin: 0.5em 0; }
        .plot { font-size: 0.95em; margin: 0.5em 0; }
        .imdb { margin: 0.3em 0 0; font-size: 0.9em; }
        """
    style_item = epub.EpubItem(
        uid="style_nav",
        file_name="style/style.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(style_item)

    if kepub:
        book.add_metadata(None, "meta", "", {"name": "kepub-format", "content": "true"})

    spine_items = []
    toc_tree = []
    toc_flat = []

    for section_label, genres in sections:
        section_slug = slugify_title(section_label) or "section"
        section_page = epub.EpubHtml(
            title=section_label,
            file_name=f"{section_slug}.xhtml",
            lang="en",
        )
        section_heading = html.escape(section_label)
        if kepub:
            section_heading = _KoboSpanCounter().wrap(section_heading)
        section_page.content = _wrap_html(
            f'<h1 class="section">{section_heading}</h1>', kepub=kepub
        )
        section_page.add_item(style_item)
        book.add_item(section_page)
        spine_items.append(section_page)
        toc_flat.append((1, section_label, section_page.file_name))

        genre_tree = []
        for genre_label, items in genres:
            genre_slug = slugify_title(f"{section_label}-{genre_label}") or "genre"
            genre_page = epub.EpubHtml(
                title=f"{section_label} - {genre_label}",
                file_name=f"{genre_slug}.xhtml",
                lang="en",
            )
            genre_heading = html.escape(genre_label)
            if kepub:
                genre_heading = _KoboSpanCounter().wrap(genre_heading)
            genre_page.content = _wrap_html(
                f'<h2 class="section">{genre_heading}</h2>', kepub=kepub
            )
            genre_page.add_item(style_item)
            book.add_item(genre_page)
            spine_items.append(genre_page)
            toc_flat.append((2, genre_label, genre_page.file_name))

            movie_chapters = []
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
                chapter.content = _movie_html(movie, poster_ref, kepub=kepub)
                chapter.add_item(style_item)
                book.add_item(chapter)
                spine_items.append(chapter)
                movie_chapters.append(chapter)
                toc_flat.append((3, chapter.title, chapter.file_name))

            genre_tree.append((epub.Section(genre_label), movie_chapters))

        toc_tree.append((epub.Section(section_label), genre_tree))

    toc_page = epub.EpubHtml(
        title="Table of Contents",
        file_name="toc.xhtml",
        lang="en",
    )
    toc_page.content = _wrap_html(_toc_page_html(toc_flat), kepub=kepub)
    toc_page.add_item(style_item)
    book.add_item(toc_page)

    book.toc = toc_tree
    book.spine = ["nav", toc_page] + spine_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book)
