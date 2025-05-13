from __future__ import annotations

import importlib.resources
import logging
from copy import deepcopy
from datetime import date
from itertools import chain, islice
from pathlib import Path
from typing import TYPE_CHECKING

import funcy
import joblib
import polars as pl
import requests
from board_game_recommender.abc import BaseGamesRecommender
from board_game_recommender.light import LightGamesRecommender
from sklearn.base import BaseEstimator

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping
    from typing import Any

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://recommend.games"

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = importlib.resources.files() / "data"
SCRAPED_DIR = PROJECT_DIR.parent / "board-game-data" / "scraped"

GAME_FEATURES = (
    "bgg_id",
    "name",
    "year",
    "num_votes",
    "avg_rating",
    "bayes_rating",
    "complexity",
)


def _recommend_games(
    *,
    base_url: str,
    timeout: float = 60,
    request_params: dict[str, Any] | None = None,
) -> Generator[dict[str, Any]]:
    url = f"{base_url}/api/games/recommend/"
    params = deepcopy(request_params or {})
    params.setdefault("page", 1)

    while True:
        LOGGER.debug("Requesting page %d", params["page"])

        try:
            response = requests.get(
                url=url,
                params=params,
                timeout=timeout,
            )
        except Exception:
            LOGGER.exception(
                "Unable to retrieve recommendations with params: %r",
                params,
            )
            return

        if not response.ok:
            LOGGER.error("Request unsuccessful: %s", response.text)
            return

        try:
            result = response.json()
        except Exception:
            LOGGER.exception("Invalid response: %s", response.text)
            return

        if not isinstance(result, dict):
            LOGGER.error("Invalid response: %s", result)
            return

        if not result.get("results"):
            return

        yield from result["results"]

        if not result.get("next"):
            return

        params["page"] += 1


def recommend_games(
    *,
    base_url: str = BASE_URL,
    max_results: int | None = 25,
    timeout: float = 60,
    request_params: dict[str, Any] | None = None,
    progress_bar: bool = False,
) -> Generator[dict[str, Any]]:
    """Call to a Recommend.Games instance."""

    results: Iterable[dict[str, Any]] = _recommend_games(
        base_url=base_url,
        timeout=timeout,
        request_params=request_params,
    )

    results = islice(results, max_results) if max_results else results

    if progress_bar:
        from tqdm import tqdm

        results = tqdm(
            results,
            desc="Fetching recommendations",
            unit=" game(s)",
            total=max_results,
        )

    yield from results


def _add_rel_columns(candidates: pl.LazyFrame, col_suffix: str = "") -> pl.LazyFrame:
    return candidates.with_columns(
        (
            pl.col(f"rec_rating{col_suffix}").rank(method="max").over("kennerspiel")
            / pl.len().over("kennerspiel")
        ).alias(f"rec_rel_rank{col_suffix}"),
        (
            (
                pl.col(f"rec_rating{col_suffix}")
                - pl.col(f"rec_rating{col_suffix}").min().over("kennerspiel")
            )
            / (
                pl.col(f"rec_rating{col_suffix}").max().over("kennerspiel")
                - pl.col(f"rec_rating{col_suffix}").min().over("kennerspiel")
            )
        ).alias(f"rec_min_max{col_suffix}"),
        (
            (
                pl.col(f"rec_rating{col_suffix}")
                - pl.col(f"rec_rating{col_suffix}").mean().over("kennerspiel")
            )
            / pl.col(f"rec_rating{col_suffix}").std().over("kennerspiel")
        ).alias(f"rec_standard{col_suffix}"),
    )


def fetch_candidates_for_single_user(
    *,
    user_name: str = "s_d_j",
    year: int | None = None,
    bgg_ids_include: Iterable[int] | None = None,
    bgg_ids_exclude: Iterable[int] | None = None,
    kennerspiel_cutoff_score: float = 0.5,
    max_results: int | None = 25,
    base_url: str = BASE_URL,
    timeout: float = 60,
    request_params: dict[str, Any] | None = None,
    progress_bar: bool = False,
) -> pl.LazyFrame:
    user_name = user_name.lower()
    year = year or date.today().year
    params = deepcopy(request_params or {})

    params["user"] = user_name
    params["year__gte"] = year - 1
    params["year__lte"] = year

    params.setdefault("exclude_clusters", False)
    params.setdefault("exclude_known", False)
    params.setdefault("exclude_owned", False)

    if bgg_ids_include is not None:
        params["include"] = ",".join(map(str, bgg_ids_include))
    if bgg_ids_exclude is not None:
        params["exclude"] = ",".join(map(str, bgg_ids_exclude))

    candidates = recommend_games(
        base_url=base_url,
        max_results=max_results,
        timeout=timeout,
        request_params=params,
        progress_bar=progress_bar,
    )

    data = (
        pl.LazyFrame(candidates)
        .select(
            *GAME_FEATURES,
            "rec_rating",
            "kennerspiel_score",
        )
        .with_columns(
            kennerspiel=pl.col("kennerspiel_score") > kennerspiel_cutoff_score,
        )
    )

    return _add_rel_columns(data)


def include_exclude_jury_members(
    year: int,
) -> tuple[pl.Series, pl.Series, list[str]]:
    with importlib.resources.as_file(
        DATA_DIR / str(year) / "exclude.csv",
    ) as exclude_path:
        LOGGER.info("Reading exclude from <%s>", exclude_path)
        exclude_explicit = (
            pl.scan_csv(exclude_path).select("bgg_id").collect()["bgg_id"]
        )

    with importlib.resources.as_file(
        DATA_DIR / str(year - 1) / "reviews.csv",
    ) as prev_reviews_path:
        if prev_reviews_path.exists():
            LOGGER.info("Reading previous reviews from <%s>", prev_reviews_path)
            prev_reviews = (
                pl.scan_csv(prev_reviews_path).select("bgg_id").collect()["bgg_id"]
            )
        else:
            prev_reviews = pl.Series(name="bgg_id", values=[], dtype=pl.Int64)

    with (
        importlib.resources.as_file(DATA_DIR / "sdj.csv") as sdj_path,
        importlib.resources.as_file(DATA_DIR / "ksdj.csv") as ksdj_path,
        importlib.resources.as_file(DATA_DIR / "kindersdj.csv") as kindersdj_path,
    ):
        LOGGER.info(
            "Fetching previous awards from <%s>, <%s> and <%s>",
            sdj_path,
            ksdj_path,
            kindersdj_path,
        )
        prev_awards = (
            pl.scan_csv([sdj_path, ksdj_path, kindersdj_path])
            .sort("jahrgang", descending=True)
            .filter(pl.col("jahrgang") < year)
            .select("bgg_id")
            .collect()["bgg_id"]
        )

    exclude = pl.concat(
        [exclude_explicit, prev_reviews, prev_awards],
        how="vertical",
    ).unique(maintain_order=True)
    del exclude_explicit, prev_awards, prev_reviews

    with importlib.resources.as_file(
        DATA_DIR / str(year) / "reviews.csv",
    ) as curr_reviews_path:
        LOGGER.info("Reading current reviews from <%s>", curr_reviews_path)
        curr_reviews = pl.read_csv(curr_reviews_path)
    include = curr_reviews.remove(pl.col("bgg_id").is_in(exclude))["bgg_id"]
    jury_members = curr_reviews.select(pl.exclude("bgg_id", "name")).columns
    del curr_reviews

    return include, exclude, jury_members


def fetch_candidates(
    year: int,
    *,
    main_user: str = "s_d_j",
    jury_member_prefix: str = "s_d_j_",
    kennerspiel_cutoff_score: float = 0.5,
    max_results: int | None = 25,
    base_url: str = BASE_URL,
    timeout: float = 60,
    max_exclude_games: int = 250,
    progress_bar: bool = False,
) -> tuple[list[str], pl.LazyFrame]:
    """Fetch all candidates from the recommendation API."""

    include, exclude, jury_members = include_exclude_jury_members(year)

    LOGGER.info("Including %d games", len(include))
    exclude = exclude.head(max_exclude_games)
    LOGGER.info("Excluding %d games", len(exclude))

    LOGGER.info("Fetching candidates for %s", main_user)
    result = fetch_candidates_for_single_user(
        user_name=main_user,
        year=year,
        bgg_ids_include=include,
        bgg_ids_exclude=exclude,
        kennerspiel_cutoff_score=kennerspiel_cutoff_score,
        max_results=max_results,
        base_url=base_url,
        timeout=timeout,
        request_params={"exclude_known": True},
        progress_bar=progress_bar,
    )

    for jury_member in jury_members:
        LOGGER.info("Fetching candidates for %s", jury_member)
        results_jury_member = fetch_candidates_for_single_user(
            user_name=f"{jury_member_prefix}{jury_member}",
            year=year,
            bgg_ids_include=include,
            bgg_ids_exclude=exclude,
            kennerspiel_cutoff_score=kennerspiel_cutoff_score,
            max_results=max_results,
            base_url=base_url,
            timeout=timeout,
            progress_bar=progress_bar,
        ).select("bgg_id", "rec_rating", "rec_rel_rank", "rec_min_max", "rec_standard")

        result = result.join(
            results_jury_member,
            on="bgg_id",
            how="left",
            suffix=f"_{jury_member}",
        )

    return jury_members, result.rename(
        {
            "rec_rating": f"rec_rating_{main_user}",
            "rec_rel_rank": f"rec_rel_rank_{main_user}",
            "rec_min_max": f"rec_min_max_{main_user}",
            "rec_standard": f"rec_standard_{main_user}",
        },
    )


def load_candidates(
    year: int,
    *,
    games_path: Path | str = SCRAPED_DIR / "bgg_GameItem.csv",
    kennerspiel_model: BaseEstimator | Path | str,
    recommender_model: BaseGamesRecommender[int, str] | Path | str,
    main_user: str = "s_d_j",
    jury_member_prefix: str = "s_d_j_",
    kennerspiel_cutoff_score: float = 0.5,
) -> tuple[list[str], pl.LazyFrame]:
    kennerspiel_model = (
        kennerspiel_model
        if isinstance(kennerspiel_model, BaseEstimator)
        else joblib.load(kennerspiel_model)
    )
    assert isinstance(kennerspiel_model, BaseEstimator), (
        "kennerspiel_model must be an sklearn estimator"
    )

    recommender_model = (
        recommender_model
        if isinstance(recommender_model, BaseGamesRecommender)
        else LightGamesRecommender.from_npz(recommender_model)
    )
    assert isinstance(recommender_model, BaseGamesRecommender), (
        "recommender_model must be a board_game_recommender.BaseGamesRecommender"
    )

    include, exclude, jury_members = include_exclude_jury_members(year)

    features = funcy.distinct(chain(GAME_FEATURES, kennerspiel_model.feature_names_in_))

    games_path = Path(games_path).resolve()
    LOGGER.info("Reading games from <%s>", games_path)
    games = (
        pl.scan_csv(games_path, infer_schema_length=None)
        .filter(pl.col("bgg_id").is_in(recommender_model.known_games))
        .filter(
            pl.col("year").is_between(year - 1, year) | pl.col("bgg_id").is_in(include),
        )
        .remove(pl.col("bgg_id").is_in(exclude))
        .select(*features)
        .collect()
    )

    kennerspiel_scores = kennerspiel_model.predict_proba(games.to_pandas())[:, 1]

    games_with_kennerspiel = (
        games.lazy()
        .with_columns(
            kennerspiel_score=kennerspiel_scores,
        )
        .with_columns(
            kennerspiel=pl.col("kennerspiel_score") > kennerspiel_cutoff_score,
        )
    )

    jury_members_users = [
        f"{jury_member_prefix}{jury_member}" for jury_member in jury_members
    ]
    jury_members_cols = [f"rec_rating_{jury_member}" for jury_member in jury_members]
    users = [main_user, *jury_members_users]
    cols = [f"rec_rating_{main_user}", *jury_members_cols]

    rec_ratings = recommender_model.recommend_as_numpy(
        users=users,
        games=games["bgg_id"],
    )

    rec_ratings_df = pl.LazyFrame(rec_ratings, schema=cols)
    result = pl.concat([games_with_kennerspiel, rec_ratings_df], how="horizontal")

    for jury_member in [main_user, *jury_members]:
        result = _add_rel_columns(result, col_suffix=f"_{jury_member}")

    return jury_members, result


def sdj_predictions(
    year: int,
    *,
    fetch_from_api: bool = False,
    main_user: str = "s_d_j",
    main_user_weights: Mapping[str, float] | None = None,
    jury_member_prefix: str = "s_d_j_",
    jury_member_weights: Mapping[str, float] | None = None,
    kennerspiel_cutoff_score: float = 0.5,
    games_path: Path | str = SCRAPED_DIR / "bgg_GameItem.csv",
    kennerspiel_model: BaseEstimator | Path | str | None = None,
    recommender_model: BaseGamesRecommender[int, str] | Path | str | None = None,
    max_results: int | None = 25,
    base_url: str = BASE_URL,
    timeout: float = 60,
    max_exclude_games: int = 250,
    progress_bar: bool = False,
) -> pl.LazyFrame:
    """Predict the Spiel des Jahres winner."""

    if fetch_from_api:
        jury_members, candidates = fetch_candidates(
            year=year,
            main_user=main_user,
            jury_member_prefix=jury_member_prefix,
            kennerspiel_cutoff_score=kennerspiel_cutoff_score,
            max_results=max_results,
            base_url=base_url,
            timeout=timeout,
            max_exclude_games=max_exclude_games,
            progress_bar=progress_bar,
        )

    else:
        assert kennerspiel_model is not None, "kennerspiel_model must be provided"
        assert recommender_model is not None, "recommender_model must be provided"

        jury_members, candidates = load_candidates(
            year=year,
            games_path=games_path,
            kennerspiel_model=kennerspiel_model,
            recommender_model=recommender_model,
            main_user=main_user,
            jury_member_prefix=jury_member_prefix,
            kennerspiel_cutoff_score=kennerspiel_cutoff_score,
        )

    main_user_weights = main_user_weights or {}
    jury_member_weights = jury_member_weights or {}

    main_user_weights = {
        f"{col}_{main_user}": weight for col, weight in main_user_weights.items()
    }
    jury_member_weights = {
        f"{col}_{jury_member}": weight
        for col, weight in jury_member_weights.items()
        for jury_member in jury_members
    }
    weights = main_user_weights | jury_member_weights
    total_weight = sum(weights.values())

    if total_weight == 0:
        return candidates.with_columns(
            sdj_score=pl.lit(None),
            sdj_rank=pl.lit(None),
        )

    return (
        candidates.with_columns(
            sdj_score=pl.sum_horizontal(
                pl.col(col) * weight for col, weight in weights.items()
            )
            / total_weight,
        )
        .with_columns(
            sdj_rank=pl.col("sdj_score")
            .rank(method="min", descending=True)
            .over("kennerspiel"),
        )
        .sort("kennerspiel", "sdj_rank")
    )
