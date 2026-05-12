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

## Generating Annual Predictions

The full prediction lifecycle involves gathering review data, exporting jury preferences to the recommendation engine, retraining the model, and finally generating rankings.

### Project Structure

This project assumes a sibling directory structure for its dependencies:
* `board-game-data/`: Master datasets.
* `board-game-scraper/`: Scraper feeds and local `.jl` items.
* `board-game-merger/`: Data merging tools.
* `recommend-games-server/`: Recommender training and deployment.
* `spiel-des-jahres/`: This repository.

### Required External Datasets

* **[BGG Games Dataset](https://gitlab.com/recommend.games/board-game-data):** `../board-game-data/scraped/bgg_GameItem.csv` (Used for matching BGG IDs and game features).

### 1. Scrape & Update Master Reviews

Collect new reviews from the `spiel-des-jahres.de` Kritikenrundschau and update the master dataset.

```sh
# 1a. Run the spider (requires LLM_API_KEY)
mkdir -p results
uv run --extra scraper scrapy runspider src/spiel_des_jahres/review_spider.py

# 1b. Update master kritikenrundschau.csv
uv run python -m spiel_des_jahres.update_reviews \
    $(ls -t results/reviews-*.jl | head -n 1) \
    --bgg-games ../board-game-data/scraped/bgg_GameItem.csv
```

### 2. Prepare the Annual Data Directory

Set up the data and artefacts directories:

```sh
YEAR=$(date +%Y)
mkdir -p "src/spiel_des_jahres/data/${YEAR}"
mkdir -p artefacts
```

* **`reviews.csv`**: The candidate pool for the target year. Typically manually filtered from `kritikenrundschau.csv` to include only eligible games for the current cycle.
* **`exclude.csv`**: BGG IDs of games to disqualify (e.g., previous winners or ineligible reprints). One BGG ID per line under a `bgg_id` header.

### 3. Export Scraper Items (.jl)

Convert local reviews and historical awards into "scraper items" (User and Rating objects) and store them in the [board-game-scraper](https://gitlab.com/recommend.games/board-game-scraper) feed directories.

```sh
# Define metadata and feed paths
TIMESTAMP=$(date -u +%Y-%m-%dT%H-%M-%S)
FEED_DIR="../board-game-scraper/feeds/bgg"

# 3a. Export Jury Member profiles
uv run python -m spiel_des_jahres.ratings --item-type user \
    --year "${YEAR}" \
    --reviews-file "src/spiel_des_jahres/data/${YEAR}/reviews.csv" \
    --reviewer-prefix "s_d_j_" \
    > "${FEED_DIR}/UserItem/${TIMESTAMP}-sdj.jl"

# 3b. Export Jury Member ratings
uv run python -m spiel_des_jahres.ratings --item-type rating \
    --year "${YEAR}" \
    --reviews-file "src/spiel_des_jahres/data/${YEAR}/reviews.csv" \
    --reviewer-prefix "s_d_j_" \
    > "${FEED_DIR}/RatingItem/${TIMESTAMP}-sdj.jl"

# 3c. Export the Jury (as a whole) historical award ratings
uv run python -m spiel_des_jahres.ratings --item-type rating \
    --awards-file src/spiel_des_jahres/data/sdj.csv \
    --awards-user "s_d_j" \
    >> "${FEED_DIR}/RatingItem/${TIMESTAMP}-sdj.jl"
uv run python -m spiel_des_jahres.ratings --item-type rating \
    --awards-file src/spiel_des_jahres/data/kindersdj.csv \
    --awards-user "s_d_j" \
    >> "${FEED_DIR}/RatingItem/${TIMESTAMP}-sdj.jl"
uv run python -m spiel_des_jahres.ratings --item-type rating \
    --awards-file src/spiel_des_jahres/data/ksdj.csv \
    --awards-user "s_d_j" \
    >> "${FEED_DIR}/RatingItem/${TIMESTAMP}-sdj.jl"
```

### 4. Retrain the Recommender Model
The exported items in the feed directories must be merged with broader BGG scrapes to update the master dataset and the recommendation engine.

1. **Merge**: Update the master dataset in `../board-game-data/` by running the following command from the `../board-game-merger/` directory:
    ```sh
    cd ../board-game-merger/
    poetry run python -m board_game_merger all \
        --progress-bar \
        --verbose \
        --clean-results \
        --overwrite
    ```

2. **Process, Train & Sync**: Run the prediction lifecycle tasks from the `../recommend-games-server/` directory. This updates CSVs, retrains the model, snapshots rankings, and pushes changes to the master repository:
    ```sh
    cd ../recommend-games-server/
    pipenv run pynt gitprepare makecsvs referencecsvs link updatecount gitupdate
    pipenv run pynt "trainbgg[out_path_light=$(pwd)/../spiel-des-jahres/artefacts/recommender_light.npz]"
    ```
    * `gitprepare`: Ensures the data repository is clean and up-to-date.
    * `makecsvs` / `referencecsvs`: Updates CSV versions of the master data and foreign references.
    * `link`: Updates game linkages (`links.json`).
    * `updatecount`: Updates the line and file counts in `COUNT.md`.
    * `gitupdate`: Commits and pushes the updated data to the master repository.
    * `trainbgg`: Retrains the recommender model and exports the light artefact.

### 5. Train the Kennerspiel Model

Train the local classifier that identifies "Kennerspiel" candidates.

```sh
uv run python -m spiel_des_jahres.kennerspiel artefacts/kennerspiel.joblib
```

### 6. Generate Final Rankings

With the data prepared and the models updated, generate the final rankings.

```sh
uv run python -m spiel_des_jahres.predictions \
    --year "${YEAR}" \
    --recommender-model artefacts/recommender_light.npz \
    --kennerspiel-model artefacts/kennerspiel.joblib \
    --output predictions.csv
```

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
