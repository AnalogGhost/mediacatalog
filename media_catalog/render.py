from io import BytesIO
import datetime
import re

import requests
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from media_catalog.poster import fetch_poster_cached


def _wrap_lines(text, width, font_name, font_size):
    words = text.split()
    line = []
    lines = []
    for word in words:
        test_line = " ".join(line + [word])
        if stringWidth(test_line, font_name, font_size) <= width:
            line.append(word)
        else:
            if line:
                lines.append(" ".join(line))
            line = [word]
    if line:
        lines.append(" ".join(line))
    return lines


def _draw_wrapped_text(c, text, x, y, width, line_height, font_name, font_size):
    c.setFont(font_name, font_size)
    lines = _wrap_lines(text, width, font_name, font_size)
    for idx, line_text in enumerate(lines):
        c.drawString(x, y - idx * line_height, line_text)
    return y - len(lines) * line_height


def _draw_wrapped_text_dynamic(c, text, x, y, line_height, font_name, font_size, width_for_y):
    c.setFont(font_name, font_size)
    words = text.split()
    current_y = y
    while words:
        width = width_for_y(current_y)
        line = []
        while words:
            test_line = " ".join(line + [words[0]])
            if stringWidth(test_line, font_name, font_size) <= width:
                line.append(words.pop(0))
            else:
                break
        if not line:
            line.append(words.pop(0))
        c.drawString(x, current_y, " ".join(line))
        current_y -= line_height
    return current_y


def _draw_wrapped_names(c, text, x, y, line_height, font_name, font_size, width_for_y):
    c.setFont(font_name, font_size)
    raw_names = [name.strip() for name in text.split(",") if name.strip()]
    names = []
    for idx, name in enumerate(raw_names):
        suffix = "," if idx < len(raw_names) - 1 else ""
        names.append(f"{name}{suffix}")
    current_y = y
    line = []
    while names:
        width = width_for_y(current_y)
        line.clear()
        while names:
            test_line = " ".join(line + [names[0]])
            if stringWidth(test_line, font_name, font_size) <= width:
                line.append(names.pop(0))
            else:
                break
        if not line:
            line.append(names.pop(0))
        c.drawString(x, current_y, " ".join(line))
        current_y -= line_height
    return current_y


def _format_us_date(value):
    if not value or value == "N/A":
        return value
    try:
        parsed = datetime.datetime.strptime(value, "%d %b %Y")
    except ValueError:
        return value
    formatted = parsed.strftime("%b %d, %Y")
    return formatted.replace(" 0", " ")


def _canonical_genre(value):
    if not value:
        return value
    key = value.strip().lower().replace("-", "").replace(" ", "")
    if key in {"scifi", "sciencefiction"}:
        return "Science Fiction"
    return value.strip()




def _draw_key_value(c, label, value, x, y, width, line_height, font_name, font_size):
    if not value or value == "N/A":
        return y
    text = f"{label}: {value}"
    return _draw_wrapped_text(c, text, x, y, width, line_height, font_name, font_size)


def _fetch_poster(url, imdb_id=None, cache_dir=None):
    data, _, _ = fetch_poster_cached(url, imdb_id=imdb_id, cache_dir=cache_dir)
    if not data:
        return None
    return BytesIO(data)


def _parse_percent(value):
    if not value or value == "N/A":
        return None
    cleaned = value.replace("%", "").strip()
    if cleaned.isdigit():
        return int(cleaned)
    return None


def _genre_tab_color(index):
    palette = [
        (0.14, 0.43, 0.78),
        (0.15, 0.62, 0.38),
        (0.95, 0.54, 0.15),
        (0.85, 0.33, 0.31),
        (0.55, 0.35, 0.64),
        (0.20, 0.60, 0.70),
        (0.80, 0.65, 0.15),
        (0.30, 0.30, 0.30),
    ]
    if index is None:
        return palette[0]
    return palette[index % len(palette)]


def _fit_tab_font_size(label, max_width, font_name, base_size):
    if not label:
        return base_size
    width = stringWidth(label, font_name, base_size)
    if width <= max_width:
        return base_size
    scale = max_width / width
    return max(4.5, base_size * scale)


def _draw_tomato_icon(c, x, y, size_mm, is_fresh):
    size = size_mm * mm
    if is_fresh:
        c.setFillColorRGB(0.82, 0.13, 0.13)
        c.circle(x + size / 2, y + size / 2, size / 2, fill=1, stroke=0)
        c.setFillColorRGB(0.1, 0.5, 0.2)
        c.circle(x + size / 2 + size / 6, y + size / 2 + size / 6, size / 6, fill=1, stroke=0)
    else:
        c.setFillColorRGB(0.1, 0.6, 0.2)
        points = [
            (x + size * 0.5, y + size * 1.0),
            (x + size * 0.62, y + size * 0.72),
            (x + size * 0.95, y + size * 0.7),
            (x + size * 0.7, y + size * 0.5),
            (x + size * 0.85, y + size * 0.2),
            (x + size * 0.5, y + size * 0.38),
            (x + size * 0.15, y + size * 0.2),
            (x + size * 0.3, y + size * 0.5),
            (x + size * 0.05, y + size * 0.7),
            (x + size * 0.38, y + size * 0.72),
        ]
        path = c.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for px, py in points[1:]:
            path.lineTo(px, py)
        path.close()
        c.drawPath(path, fill=1, stroke=0)


def _extract_awards_summary(awards_text, is_series):
    if not awards_text or awards_text == "N/A":
        return ""
    if is_series:
        label = "Emmy"
        label_pattern = r"(?:Primetime\s+|Daytime\s+)?Emmy"
    else:
        label = "Oscar"
        label_pattern = r"Oscar"
    wins_match = re.search(rf"Won\s+(\d+)\s+{label_pattern}s?", awards_text)
    noms_match = re.search(rf"Nominated\s+for\s+(\d+)\s+{label_pattern}s?", awards_text)
    wins = int(wins_match.group(1)) if wins_match else 0
    noms = int(noms_match.group(1)) if noms_match else 0
    if wins or noms:
        awards_label = "Emmy Awards" if is_series else "Academy Awards"
        single_label = "Emmy Award" if is_series else "Academy Award"
        if wins and noms:
            win_label = single_label if wins == 1 else awards_label
            nom_label = single_label if noms == 1 else awards_label
            return f"Winner of {wins} {win_label}, nominated for {noms} {nom_label}"
        if wins:
            label = single_label if wins == 1 else awards_label
            return f"Winner of {wins} {label}"
        label = single_label if noms == 1 else awards_label
        return f"Nominated for {noms} {label}"
    return ""

def render_movie_page(
    movie,
    output_path,
    left_margin_mm=25.0,
    include_poster=True,
    poster_cache_dir=None,
    tab_index=None,
    tab_count=None,
    tab_label=None,
):
    width, height = A5
    left_margin = left_margin_mm * mm
    right_margin = 12 * mm
    top_margin = 12 * mm
    bottom_margin = 12 * mm

    c = canvas.Canvas(str(output_path), pagesize=A5)

    title = movie.get("Title", "Untitled")
    year = movie.get("Year", "")
    rated = movie.get("Rated", "")
    runtime = movie.get("Runtime", "")
    genre = movie.get("Genre", "")
    genre_override = movie.get("GenreOverride", "")
    primary_genre = ""
    if genre and genre != "N/A":
        primary_genre = genre.split(",")[0].strip()
    released = _format_us_date(movie.get("Released", ""))
    director = movie.get("Director", "")
    writer = movie.get("Writer", "")
    actors = movie.get("Actors", "")
    language = movie.get("Language", "")
    country = movie.get("Country", "")
    awards = movie.get("Awards", "")
    media_type = movie.get("Type", "")
    metascore = movie.get("Metascore", "")
    plot = movie.get("Plot", "")
    imdb_rating = movie.get("imdbRating", "")
    ratings = movie.get("Ratings", [])
    imdb_id = movie.get("imdbID", "")
    afi_1998 = movie.get("AFI1998Rank", "")
    afi_2007 = movie.get("AFI2007Rank", "")
    imdb_top_250 = movie.get("IMDbTop250Rank", "")
    imdb_top_250_tv = movie.get("IMDbTop250TVRank", "")
    palme_dor_year = movie.get("CannesPalmeDorYear", "")
    bfi_rank = movie.get("BFISightAndSoundRank", "")
    series_name = movie.get("SeriesName", "")
    total_seasons = movie.get("totalSeasons", "")
    total_episodes = movie.get("totalEpisodes", "")

    if tab_index is not None and tab_count:
        tab_width = 9 * mm
        usable_height = height - top_margin - bottom_margin
        slot_height = usable_height / tab_count
        tab_height = max(8 * mm, slot_height - 2 * mm)
        y_center = height - top_margin - slot_height * (tab_index + 0.5)
        tab_y = y_center - tab_height / 2
        tab_x = width - tab_width
        r, g, b = _genre_tab_color(tab_index)
        c.setFillColorRGB(r, g, b)
        c.setStrokeColorRGB(r, g, b)
        c.rect(tab_x, tab_y, tab_width, tab_height, fill=1, stroke=0)
        if tab_label:
            c.saveState()
            c.setFillColorRGB(1, 1, 1)
            base_size = 6.2
            font_size = _fit_tab_font_size(
                tab_label, tab_height - 2 * mm, "Helvetica-Bold", base_size
            )
            c.setFont("Helvetica-Bold", font_size)
            label = tab_label
            c.translate(tab_x + tab_width / 2, tab_y + tab_height / 2)
            c.rotate(90)
            c.drawCentredString(0, -2, label)
            c.restoreState()
        c.setFillColorRGB(0, 0, 0)

    rotten = ""
    for rating in ratings:
        source = rating.get("Source", "")
        value = rating.get("Value", "")
        if source == "Rotten Tomatoes":
            rotten = value

    title_font = "Helvetica-Bold"
    body_font = "Helvetica"

    content_width = width - left_margin - right_margin
    y = height - top_margin

    poster_width = 45 * mm
    poster_height = 60 * mm
    poster_x = left_margin + content_width - poster_width
    poster_y = y - poster_height - 4 * mm

    if include_poster:
        poster_stream = None
        try:
            poster_stream = _fetch_poster(
                movie.get("Poster"),
                imdb_id=movie.get("imdbID"),
                cache_dir=poster_cache_dir,
            )
        except requests.RequestException:
            poster_stream = None

        if poster_stream:
            try:
                image = ImageReader(poster_stream)
                c.drawImage(
                    image,
                    poster_x,
                    poster_y,
                    width=poster_width,
                    height=poster_height,
                    preserveAspectRatio=True,
                    anchor="n",
                )
            except Exception:
                pass

    def available_width(current_y):
        if include_poster and poster_y <= current_y <= poster_y + poster_height:
            return content_width - poster_width - 6 * mm
        return content_width

    def draw_wrapped_block(text, current_y):
        def width_for_y(y_pos):
            return available_width(y_pos)
        return _draw_wrapped_text_dynamic(
            c, text, left_margin, current_y, line_height, body_font, body_font_size, width_for_y
        )

    title_font_size = 17
    title_line_height = 6 * mm
    subtitle_font_size = 12
    subtitle_line_height = 5 * mm
    title_main = title
    title_sub = ""
    if ": " in title:
        title_main, title_sub = title.split(": ", 1)
    c.setFont(title_font, title_font_size)
    title_lines = _wrap_lines(title_main, available_width(y), title_font, title_font_size)
    for line in title_lines:
        c.drawString(left_margin, y, line)
        y -= title_line_height
    if title_sub:
        c.setFont(body_font, subtitle_font_size)
        subtitle_lines = _wrap_lines(title_sub, available_width(y), body_font, subtitle_font_size)
        for line in subtitle_lines:
            c.drawString(left_margin, y, line)
            y -= subtitle_line_height

    subtitle_runtime = runtime
    if media_type == "series":
        seasons_text = f"{total_seasons} seasons" if total_seasons else ""
        episodes_text = f"{total_episodes} episodes" if total_episodes else ""
        if seasons_text and episodes_text:
            subtitle_runtime = f"{seasons_text}, {episodes_text}"
        elif seasons_text or episodes_text:
            subtitle_runtime = seasons_text or episodes_text
        else:
            subtitle_runtime = ""
    genre_list = []
    if genre_override:
        genre_list.append(_canonical_genre(genre_override))
    if genre and genre != "N/A":
        for item in [entry.strip() for entry in genre.split(",") if entry.strip()]:
            canonical = _canonical_genre(item)
            normalized = canonical.replace("-", "").replace(" ", "").lower()
            override_normalized = [
                value.replace("-", "").replace(" ", "").lower() for value in genre_list
            ]
            if normalized not in override_normalized:
                genre_list.append(canonical)
    genre_display = ", ".join(genre_list)

    subtitle_bits = [
        bit
        for bit in [year, subtitle_runtime, rated, genre_display]
        if bit and bit != "N/A"
    ]
    subtitle = " • ".join(subtitle_bits)
    c.setFont(body_font, 9.5)
    if subtitle:
        y = _draw_wrapped_text(
            c, subtitle, left_margin, y, available_width(y), 4.8 * mm, body_font, 9.5
        )
        y -= 2 * mm
    else:
        y -= 2 * mm

    if series_name:
        c.setFont(title_font, 9.2)
        label = "Series: "
        label_width = stringWidth(label, title_font, 9.2)
        c.drawString(left_margin, y, label)
        c.setFont(body_font, 9.2)
        y = _draw_wrapped_text(
            c,
            series_name,
            left_margin + label_width,
            y,
            available_width(y) - label_width,
            4.6 * mm,
            body_font,
            9.2,
        )
        y -= 1.5 * mm

    body_font_size = 9
    line_height = 4.6 * mm
    c.setFont(body_font, body_font_size)

    awards_summary = _extract_awards_summary(awards, is_series=media_type == "series")

    series_run = ""
    if media_type == "series":
        seasons_text = f"{total_seasons} seasons" if total_seasons else ""
        episodes_text = f"{total_episodes} episodes" if total_episodes else ""
        if seasons_text and episodes_text:
            series_run = f"{seasons_text}, {episodes_text}"
        elif seasons_text or episodes_text:
            series_run = seasons_text or episodes_text

    def _label_for_names(singular, value):
        if not value or value == "N/A":
            return singular
        normalized = value.replace("&", ",").replace(" and ", ",")
        count = sum(1 for part in normalized.split(",") if part.strip())
        return f"{singular}s" if count > 1 else singular

    grid_items = [
        ("Released", released),
        ("Country", country),
        ("Language", language),
        ("Series", series_run),
        ("IMDb", imdb_rating),
        ("Metacritic", f"{metascore}/100" if metascore and metascore != "N/A" else metascore),
        ("Rotten Tomatoes", rotten),
        (_label_for_names("Director", director), director),
        (_label_for_names("Writer", writer), writer),
    ]
    grid_items = [(label, value) for label, value in grid_items if value and value != "N/A"]

    if grid_items:
        col_gap = 6 * mm
        label_font_size = 8.2
        value_font_size = 8.5
        label_line_height = 4.2 * mm
        value_line_height = 4.4 * mm
        full_width_labels = {"Director", "Writer"}

        rows = []
        pending = None
        for item in grid_items:
            label, _ = item
            if label in full_width_labels:
                if pending:
                    rows.append([pending])
                    pending = None
                rows.append([item])
                continue
            if pending is None:
                pending = item
            else:
                rows.append([pending, item])
                pending = None
        if pending:
            rows.append([pending])

        for row_items in rows:
            width_available = available_width(y)
            col_width = (width_available - col_gap) / 2
            cell_heights = []
            wrapped_values = []

            for label, value in row_items:
                width = width_available if len(row_items) == 1 else col_width
                value_lines = _wrap_lines(value, width, body_font, value_font_size)
                wrapped_values.append(value_lines)
                cell_heights.append(
                    label_line_height + len(value_lines) * value_line_height + 1 * mm
                )

            row_height = max(cell_heights) if cell_heights else label_line_height

            for col, (label, value) in enumerate(row_items):
                x = left_margin if len(row_items) == 1 else left_margin + col * (col_width + col_gap)
                c.setFont(title_font, label_font_size)
                c.drawString(x, y, f"{label}")
                c.setFont(body_font, value_font_size)
                value_lines = wrapped_values[col]
                for line_index, line_text in enumerate(value_lines):
                    line_y = y - label_line_height - line_index * value_line_height
                    if label == "Rotten Tomatoes":
                        percent = _parse_percent(value)
                        if percent is not None:
                            is_fresh = percent >= 60
                            _draw_tomato_icon(c, x, line_y - 1.2 * mm, 3.6, is_fresh)
                            c.setFillColorRGB(0, 0, 0)
                            c.drawString(x + 5 * mm, line_y, f"{percent}%")
                            continue
                    c.drawString(x, line_y, line_text)
            y -= row_height

        y -= 3 * mm

    if awards_summary:
        c.setFont(title_font, body_font_size + 1)
        y = _draw_wrapped_text_dynamic(
            c,
            awards_summary,
            left_margin,
            y,
            line_height,
            title_font,
            body_font_size + 1,
            available_width,
        )
        y -= 2 * mm

    list_parts = []
    if afi_1998:
        list_parts.append(f"AFI 100 (1998) #{afi_1998}")
    if afi_2007:
        list_parts.append(f"AFI 100 (2007) #{afi_2007}")
    if imdb_top_250:
        list_parts.append(f"IMDb Top 250 #{imdb_top_250}")
    if imdb_top_250_tv:
        list_parts.append(f"IMDb Top 250 TV #{imdb_top_250_tv}")
    if bfi_rank:
        list_parts.append(f"BFI Sight & Sound #{bfi_rank}")
    if palme_dor_year:
        list_parts.append(f"Palme d'Or winner ({palme_dor_year})")
    if list_parts:
        c.setFont(title_font, body_font_size + 1)
        y = _draw_wrapped_text_dynamic(
            c,
            " • ".join(list_parts),
            left_margin,
            y,
            line_height,
            title_font,
            body_font_size + 1,
            available_width,
        )
        y -= 2 * mm

    if actors and actors != "N/A":
        c.setFont(title_font, body_font_size)
        c.drawString(left_margin, y, "Cast:")
        label_width = stringWidth("Cast:", title_font, body_font_size)
        c.setFont(body_font, body_font_size)
        cast_width = content_width - poster_width - 6 * mm if include_poster else content_width
        def cast_width_for_y(y_pos):
            return cast_width - label_width - 2 * mm
        y = _draw_wrapped_names(
            c,
            actors,
            left_margin + label_width + 2 * mm,
            y,
            line_height,
            body_font,
            body_font_size,
            cast_width_for_y,
        )
        y -= 2 * mm

    if plot and plot != "N/A":
        if include_poster:
            plot_buffer = 8 * mm
            if y > poster_y - plot_buffer:
                y = poster_y - plot_buffer
        y = draw_wrapped_block(plot, y)

    if imdb_id:
        qr_size = 18 * mm
        qr_code = qr.QrCodeWidget(f"https://www.imdb.com/title/{imdb_id}/")
        bounds = qr_code.getBounds()
        qr_width = bounds[2] - bounds[0]
        qr_height = bounds[3] - bounds[1]
        drawing = Drawing(qr_size, qr_size, transform=[qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0])
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, left_margin, bottom_margin)

    c.showPage()
    c.save()


def render_separator_page(title, output_path, left_margin_mm=25.0):
    width, height = A5
    left_margin = left_margin_mm * mm
    right_margin = 12 * mm
    top_margin = 12 * mm

    c = canvas.Canvas(str(output_path), pagesize=A5)
    c.setFont("Helvetica-Bold", 28)
    text_width = stringWidth(title, "Helvetica-Bold", 28)
    x = left_margin + (width - left_margin - right_margin - text_width) / 2
    y = height - top_margin - 50 * mm
    c.drawString(x, y, title)
    c.setLineWidth(1)
    c.line(left_margin, y - 6 * mm, width - right_margin, y - 6 * mm)
    c.showPage()
    c.save()
