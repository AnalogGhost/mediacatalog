# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python CLI tool for generating A5 movie catalog pages from IMDb links. The core layout:

- `media_catalog/` contains the CLI and PDF generation logic.
- `requirements.txt` lists runtime dependencies.
- `README.md` documents usage and options.

## Build, Test, and Development Commands
There is no build step. Typical commands:

- `pip install -r requirements.txt` to install dependencies.
- `python -m media_catalog --input movies.csv` to generate PDFs.

## Coding Style & Naming Conventions
Keep code in standard Python style:

- Indentation: 4 spaces.
- Filenames/modules: `snake_case` (e.g., `render.py`).
- Keep functions small and avoid hidden side effects (pass config explicitly).

## Testing Guidelines
Tests are not implemented yet. If added:

- Place tests under `tests/` mirroring `media_catalog/`.
- Name files `test_*.py` and run with `pytest`.

## Commit & Pull Request Guidelines
No commit history is available yet. Use concise, imperative messages, for example:

- `Add OMDb metadata fetch`
- `Refine A5 layout spacing`

Pull requests should include a short summary and how the output was validated (e.g., sample PDF generated).

## Configuration Tips
Set the OMDb API key in `OMDB_API_KEY`. Avoid committing secrets.
