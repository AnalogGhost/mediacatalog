# MediaCatalog (A5 Binder Pages)

Generate printable A5 pages for a movie catalog from a CSV containing IMDb links/IDs. The tool fetches metadata via the OMDb API, renders one page per movie, and also produces a combined PDF for printing.

License: GPL-3.0-or-later

## Features

- One movie per page (A5 PDF) plus optional reflowable EPUB.
- Genre sections with right-edge colored tabs for quick visual scanning.
- Series-aware sorting and per-page series labels.
- Optional list badges (AFI, IMDb Top 250, BFI Sight & Sound, Palme d'Or).
- Poster caching to speed up repeated runs.

## Quick Start

1. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set your OMDb API key:

```bash
export OMDB_API_KEY="your_key_here"
```

Alternatively, add it to a `.env` file in the repo root:

```bash
OMDB_API_KEY=your_key_here
```

3. Prepare a CSV (example):

```csv
imdb,genre_override,series
https://www.imdb.com/title/tt0111161/,Drama,
https://www.imdb.com/title/tt0068646/,Crime,
```

4. Generate PDFs:

```bash
python -m media_catalog --input movies.csv
```

Output:
- Per-movie pages in `output/pages/`
- Combined PDF at `output/catalog.pdf`
- Optional EPUB at `output/catalog.epub` when `--epub` is used.

## Options

- `--imdb-column`: column name for IMDb links/IDs (default: `imdb`)
- `--output-dir`: output directory (default: `output`)
- `--pages-dir`: subdirectory for per-movie PDFs (default: `pages`)
- `--combined`: combined PDF filename (default: `catalog.pdf`)
- `--epub`: generate an EPUB alongside the PDFs
- `--epub-name`: EPUB filename (default: `catalog.epub`)
- `--left-margin-mm`: left margin in mm for hole punch clearance (default: `25`)
- `--no-poster`: skip poster downloads
- `--cache-dir`: directory to cache OMDb responses (default: `.cache/omdb`)
- `--no-cache`: disable cache reads and writes

Note: For TV series, the tool may make additional OMDb calls to count total episodes by season. These responses are also cached.
Poster images are cached under `<cache-dir>/posters` to avoid repeated downloads.

CSV supports an optional `genre_override` column to control grouping order.
Add an optional `series` column to group series entries, which are sorted by release year.
The `title` column is updated on each run with the OMDb title for easier editing.
Plots are fetched in full and truncated to a length threshold; short plots are only used when the full plot is a placeholder.
PDF pages include a right-edge color tab per genre, evenly spaced down the edge.

## Public Repo Tips

- Use `movies.example.csv` as a template; keep your personal `movies.csv` private.
- Generated output is excluded via `.gitignore`.

## Sample Output

Generate sample PDFs and EPUB from the example CSV:

```bash
python -m media_catalog --input movies.example.csv --epub
```

Sample files (generated from `movies.example.csv`):
- `samples/catalog.pdf`
- `samples/catalog.epub`

## Publishing

### PyPI

1. Build:

```bash
python -m build
```

2. Upload:

```bash
python -m twine upload dist/*
```

Automated release: push a tag like `v0.1.1` and GitHub Actions will build and publish.

Install after publishing:

```bash
pip install mediacatalog
```

### Homebrew

1. Create a GitHub release (tag like `v0.1.0`).
2. Update `packaging/homebrew/mediacatalog.rb` with the tarball URL and SHA256.
3. Publish the formula in a tap repo (e.g., `homebrew-media-catalog`).

Install after publishing:

```bash
brew tap YOUR_GITHUB_USER/tap
brew install mediacatalog
```

## Contributing

Issues and PRs are welcome. If you add new features, please update the README and include a short example in `movies.example.csv`.

The tool marks movies that appear in the AFI Top 100 lists (1998 and 2007), stored in `media_catalog/data/afi_top_100_1998.csv` and `media_catalog/data/afi_top_100_2007.csv`. It also supports optional lists for `media_catalog/data/imdb_top_250.csv`, `media_catalog/data/imdb_top_250_tv.csv`, `media_catalog/data/cannes_palme_dor.csv`, and `media_catalog/data/bfi_sight_sound.csv`. List files use `title,year,rank,imdb_id` columns; populate `imdb_id` to match by IMDb ID, otherwise it falls back to title + year matching.

## Notes

- A5 size is used with a wider left margin to allow for hole punching. Adjust `--left-margin-mm` after a test print.
- OMDb data is subject to their terms. Use your own API key.
