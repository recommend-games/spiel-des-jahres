# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

| Task | Command |
| :--- | :--- |
| Setup | `uv sync --all-extras` |
| Tests | `uv run pytest` |
| Single test | `uv run pytest tests/test_foo.py::test_bar` |
| Lint + format | `uv run pre-commit run --all-files` |
| Type check | `uv run mypy .` |
| Run spider | `uv run --extra scraper scrapy runspider src/spiel_des_jahres/review_spider.py` |
| Update reviews CSV | `uv run python -m spiel_des_jahres.update_reviews $(ls -t results/reviews-*.jl \| head -n 1)` |
| Train kennerspiel model | `uv run python -m spiel_des_jahres.kennerspiel <dest.joblib>` |
| Serve docs | `uv run mkdocs serve` |

100% test coverage is enforced (`fail_under = 100` in `pyproject.toml`).

## Architecture

The project predicts Spiel des Jahres award winners by combining scraped jury reviews with recommendation-engine data.

**Pipeline stages:**

1. **Scrape** (`review_spider.py`): A Scrapy `SitemapSpider` crawls `spiel-des-jahres.de/kritikenrundschau-*`, extracts raw article text and metadata, then passes items through the LLM pipeline.

2. **Extract** (`llm_pipeline.py`): A Scrapy item pipeline calls an OpenAI-compatible API (configured via env vars `LLM_API_KEY`, `LLM_MODEL`, etc.) to parse raw text into structured `Review` Pydantic objects (game title, reviewer, 1–10 rating, sentiment). Output is written to `results/reviews-*.jl` (JSON Lines).

3. **Update** (`update_reviews.py`): Merges `.jl` output into `src/spiel_des_jahres/data/kritikenrundschau.csv`. Matches game names to BGG IDs via exact (case-insensitive) then fuzzy matching (`thefuzz`, threshold 90). Ambiguous names are logged as warnings and require manual assignment.

4. **Classify** (`kennerspiel/`): An sklearn `LogisticRegressionCV` pipeline classifies games as Spiel or Kennerspiel. Trained on historical SdJ/KSdJ award data from `sdj.csv`/`ksdj.csv` plus game features from the sibling `board-game-data` repo. The trained model is saved as `kennerspiel.joblib`.

5. **Predict** (`predictions.py`): `sdj_predictions()` is the main entry point. Two modes:
   - `fetch_from_api=True`: fetches recommendations live from the Recommend.Games API for the main jury account (`s_d_j`) and each jury member (`s_d_j_<member>`).
   - `fetch_from_api=False`: requires a `kennerspiel_model` (joblib) and `recommender_model` (`.npz`) path; runs locally against `board-game-data/scraped/bgg_GameItem.csv`.

   Outputs a Polars LazyFrame with `sdj_score` and `sdj_rank` columns grouped by `kennerspiel`.

**Data files** (`src/spiel_des_jahres/data/`):
- `sdj.csv`, `ksdj.csv`, `kindersdj.csv` — historical award winners/nominees
- `kritikenrundschau.csv` — all scraped jury reviews (updated by `update_reviews.py`)
- `<year>/reviews.csv` — games reviewed by the jury in a given year, with per-jury-member ratings
- `<year>/exclude.csv` — games explicitly excluded from that year's predictions

**External dependencies** (sibling directories assumed at `../../`):
- `board-game-data/scraped/bgg_GameItem.csv` — BGG game database for feature extraction and ID matching
- `recommend-games-server/data/recommender_light.npz` — pre-trained recommender model (used in local prediction mode)

**Notebooks** (`notebooks/`): Managed with `jupytext` (`.py` percent format synced with `.ipynb`). The main predictions notebook calls `sdj_predictions()` directly.

## Coding Conventions

- **Polars**: Always prefer the **LazyFrame API** (`.lazy()`, `pl.scan_csv()`). Only `.collect()` at the end of a pipeline.
- **Boolean args**: Use keyword arguments for Polars boolean flags: `.fill_null(value=False)`, `.lit(value=True)` — required by ruff's `FBT` rules.
- **Ruff**: All rules enabled except `ANN`, `D`, `TD`, `FIX`, and a few others (see `pyproject.toml`). Notebooks are excluded from ruff.
- **mypy**: Strict mode. Add `[[tool.mypy.overrides]]` for third-party stubs rather than loosening global config.
- **LLM pipeline**: Uses the OpenAI `responses.parse()` API with a Pydantic response format — not the chat completions endpoint.
