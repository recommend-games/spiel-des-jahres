# Spiel des Jahres

[![PyPI](https://img.shields.io/pypi/v/spiel-des-jahres?style=flat-square)](https://pypi.python.org/pypi/spiel-des-jahres/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/spiel-des-jahres?style=flat-square)](https://pypi.python.org/pypi/spiel-des-jahres/)
[![PyPI - License](https://img.shields.io/pypi/l/spiel-des-jahres?style=flat-square)](https://pypi.python.org/pypi/spiel-des-jahres/)
[![Coookiecutter - Wolt](https://img.shields.io/badge/cookiecutter-Wolt-00c2e8?style=flat-square&logo=cookiecutter&logoColor=D4AA00&link=https://github.com/woltapp/wolt-python-package-cookiecutter)](https://github.com/woltapp/wolt-python-package-cookiecutter)


---

**Documentation**: [https://recommend-games.github.io/spiel-des-jahres](https://recommend-games.github.io/spiel-des-jahres)

**Source Code**: [https://github.com/recommend-games/spiel-des-jahres](https://github.com/recommend-games/spiel-des-jahres)

**PyPI**: [https://pypi.org/project/spiel-des-jahres/](https://pypi.org/project/spiel-des-jahres/)

---

Spiel des Jahres predictions

## Generating Annual Predictions

Generating the annual predictions for the Spiel and Kennerspiel des Jahres involves gathering review data, updating local datasets, training models, and finally running the prediction notebook.

**Required External Datasets:**
Before starting, ensure you have the following external datasets available (paths are configurable but default to these locations relative to the project root):
*   **BGG Games Dataset:** `../board-game-data/scraped/bgg_GameItem.csv` (Used for matching BGG IDs during review updates and providing game features for predictions).
*   **Recommender Model:** `../recommend-games-server/data/recommender_light.npz` (Used in the final notebook to calculate jury-specific recommendation metrics).

**1. Scrape New Reviews (Kritikenrundschau)**
Automate the collection of new reviews from the official `spiel-des-jahres.de` Kritikenrundschau.
*   **Preparation**: Set your OpenAI API key and the LLM model to use for parsing unstructured review text.
    ```sh
    export LLM_API_KEY="your-api-key-here"
    export LLM_MODEL="gpt-4o"
    ```
*   **Run the Spider**: Crawl the site and extract review data into a JSON Lines file.
    ```sh
    uv run --extra scraper scrapy runspider src/spiel_des_jahres/review_spider.py
    ```

**2. Update Master Review Data**
Merge the newly scraped reviews from the spider's `.jl` output into the canonical dataset (`src/spiel_des_jahres/data/kritikenrundschau.csv`). The script automatically matches game names to BGG IDs using exact and fuzzy matching against the external **BGG Games Dataset**.
```sh
uv run python -m spiel_des_jahres.update_reviews $(ls -t results/reviews-*.jl | head -n 1)
```

**3. Prepare the Annual Data Directory**
The predictions rely on a specific data directory for the target year (e.g., `src/spiel_des_jahres/data/2026/`).
*   **`reviews.csv`**: This file acts as the primary input for the current year's candidate pool and jury preferences. It is derived manually or programmatically from the master `kritikenrundschau.csv` updated in Step 2. It contains all candidates (`bgg_id`, `name`) and columns for each active jury member's ratings.
*   **`exclude.csv`**: Contains any `bgg_id`s of games that should be explicitly disqualified or excluded from consideration for the current year.

**4. Train the Kennerspiel Model**
The predictions require a machine learning model that predicts whether a game belongs in the "Kennerspiel" category based on BGG complexity, votes, and categories.
```sh
uv run python -m spiel_des_jahres.kennerspiel ./kennerspiel.joblib
```
*(Alternative: You can run the `notebooks/Kennerspiel.py` notebook to retrain the model and inspect its accuracy).*

**5. Generate the Final Predictions**
With the data prepared and the Kennerspiel model trained, generate the final predictions.
*   Open the Jupyter Notebook `notebooks/SdJ predictions.py`.
*   Update the `year` parameter in the `sdj_predictions` function call to the target year.
*   Ensure that the paths to your external data sources (`games_path`, `kennerspiel_model`, `recommender_model`) are correct.
*   Run the notebook end-to-end. This script joins the candidate pool from `reviews.csv` with the `kennerspiel_model` probabilities and `recommender_model` metrics to compute the final `sdj_score` and `sdj_rank`.

## Installation

```sh
pip install spiel-des-jahres
```

## Development

* Clone this repository
* Requirements:
  * [uv](https://docs.astral.sh/uv/)
  * Python 3.10+
* Create a virtual environment and install the dependencies

```sh
uv sync --all-extras
```

### Testing

```sh
uv run pytest
```

### Documentation

The documentation is automatically generated from the content of the [docs directory](https://github.com/recommend-games/spiel-des-jahres/tree/master/docs) and from the docstrings
 of the public signatures of the source code. The documentation is updated and published as a [Github Pages page](https://pages.github.com/) automatically as part each release.

### Releasing

Trigger the [Draft release workflow](https://github.com/recommend-games/spiel-des-jahres/actions/workflows/draft_release.yml)
(press _Run workflow_). This will update the changelog & version and create a GitHub release which is in _Draft_ state.

Find the draft release from the
[GitHub releases](https://github.com/recommend-games/spiel-des-jahres/releases) and publish it. When
 a release is published, it'll trigger [release](https://github.com/recommend-games/spiel-des-jahres/blob/master/.github/workflows/release.yml) workflow which creates PyPI
 release and deploys updated documentation.

### Pre-commit

Pre-commit hooks run all the auto-formatting (`ruff format`), linters (e.g. `ruff` and `mypy`), and other quality
 checks to make sure the changeset is in good shape before a commit/push happens.

You can install the hooks with (runs for each commit):

```sh
pre-commit install
```

Or if you want them to run only for each push:

```sh
pre-commit install -t pre-push
```

Or if you want e.g. want to run all checks manually for all files:

```sh
pre-commit run --all-files
```

---

This project was generated using the [wolt-python-package-cookiecutter](https://github.com/woltapp/wolt-python-package-cookiecutter) template.
