# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python CLI tool for generating A5 movie catalog pages from IMDb links. The core layout:

- `media_catalog/` contains the CLI and PDF generation logic.
- `pyproject.toml` defines the package, dependencies, and `mediacatalog` console entry point.
- `media_catalog/data/` contains the bundled reference lists used by the CLI.
- `README.md` documents usage and options.

## Build, Test, and Development Commands
Typical commands:

- `python -m pip install -e .` to install the package for development.
- `python -m media_catalog --input movies.csv` to generate PDFs.
- `python -m media_catalog --help` to review current CLI options.

## Coding Style & Naming Conventions
Keep code in standard Python style:

- Indentation: 4 spaces.
- Filenames/modules: `snake_case` (e.g., `render.py`).
- Keep functions small and avoid hidden side effects (pass config explicitly).

## Testing Guidelines
Tests are not implemented yet. Before committing a behavior change, run the CLI against a small sample and inspect the generated PDF or EPUB. If tests are added:

- Place tests under `tests/` mirroring `media_catalog/`.
- Name files `test_*.py` and run with `pytest`.

## Commit & Pull Request Guidelines
Use concise, imperative messages, for example:

- `Add OMDb metadata fetch`
- `Refine A5 layout spacing`

Pull requests should include a short summary and how the output was validated (e.g., sample PDF generated).

## Configuration Tips
Set the OMDb API key in `OMDB_API_KEY`. Avoid committing secrets.
