# Gemini CLI Context: Spiel des Jahres

This project provides tools and logic for predicting the winners of the **Spiel des Jahres** (and Kennerspiel/Kinderspiel) board game awards. It combines historical award data, scraped reviews from the official "Kritikenrundschau", and data from a recommendation engine.

## Project Overview

- **Purpose:** Automate the collection of board game reviews and generate data-driven predictions for the Spiel des Jahres awards.
- **Main Technologies:**
    - **Python** (managed by `uv`)
    - **Polars:** Primary library for high-performance data manipulation.
    - **Scrapy:** Used for crawling review articles from `spiel-des-jahres.de`.
    - **OpenAI:** Integrated into the scraping pipeline to extract structured data from raw review text.
    - **Scikit-learn:** Used for prediction models.
    - **Board-Game-Recommender:** Integration with a recommendation engine to weight predictions by jury preference.

## Core Architecture

- `src/spiel_des_jahres/review_spider.py`: A `SitemapSpider` that crawls the Kritikenrundschau section.
- `src/spiel_des_jahres/llm_pipeline.py`: A Scrapy pipeline using LLMs to parse raw article text into structured game/reviewer/rating JSON.
- `src/spiel_des_jahres/update_reviews.py`: CLI utility to update `kritikenrundschau.csv`. It matches games with BGG IDs using exact (case-insensitive) and fuzzy matching.
- `src/spiel_des_jahres/predictions.py`: Logic to fetch candidates, calculate jury-specific metrics, and generate final prediction scores (`sdj_score`).
- `src/spiel_des_jahres/data/`: Contains canonical CSV files for awards (`sdj.csv`, `ksdj.csv`, etc.) and historical reviews.

## Development Conventions

### Coding Standards
- **Polars Usage:** Strictly prefer **LazyFrame** API (`.lazy()`, `pl.scan_csv()`) for data transformations to ensure efficiency.
- **Type Safety:** Use explicit type hints. `mypy` is used for static type checking.
- **Linting:** `ruff` is the primary linter and formatter.
- **Boolean Arguments:** When calling Polars functions with boolean flags, use keyword arguments (e.g., `.fill_null(value=False)`, `.lit(value=True)`) to satisfy `ruff`'s `FBT` rules.

### Quality Control
- **Pre-commit:** Always run `uv run pre-commit` before committing.
- **Tests:** Use `pytest` for verification. New features or bug fixes should include a reproduction script or test case.

## Key Commands

| Task | Command |
| :--- | :--- |
| **Setup** | `uv sync --all-extras` |
| **Testing** | `uv run pytest` |
| **Quality Checks** | `uv run pre-commit` |
| **Run Crawler** | `uv run scrapy crawl spiel_des_jahres` |
| **Update Reviews** | `uv run python -m spiel_des_jahres.update_reviews <path_to_jl>` |
| **Generate Docs** | `uv run mkdocs serve` |

## Data Matching Logic
When updating reviews, the system matches games against a BGG database. To prevent errors:
- **Exact matching** is only performed for names that are unique in the BGG database.
- **Fuzzy matching** (via `thefuzz`) requires a threshold of 90 and is also restricted to unique BGG titles.
- **Ambiguity:** If a name matches multiple BGG IDs, a warning is logged, and the ID must be assigned manually.

## Agent Mandates

To maintain project integrity across all environments and agents:

- **CRITICAL: NEVER undo, revert, or overwrite manual changes made by the user.** Always perform a targeted `read_file` or check the current file state before applying an edit. If an agent's proposed change contradicts existing manual adjustments, the agent must defer to the user's manual state.
- **Path Conventions:** Respect the established path conventions in this repository (e.g., using `../board-game-data/` rather than `../../`).
- **Local Destructive Actions:** NEVER perform destructive actions that lead to irreversible data loss (e.g., `git reset --hard`, `rm -rf` on project directories, or complete file overwrites of established files) without explicit user confirmation. Prioritize surgical edits and always verify current file state to preserve uncommitted manual work.
- **Git Safety:** NEVER use force-push (`--force` or `--force-with-lease`) unless explicitly and specifically directed by the user for a particular command. Always perform a thorough `git status` and `git diff` before committing to ensure no unintended changes or reversions are included.

- **Validation:** Always run `uv run pre-commit` after any modification to ensure structural and stylistic compliance.
