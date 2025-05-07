from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
import requests

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from typing import Any

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://recommend.games"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


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
        LOGGER.info("Requesting page %d", params["page"])

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
            unit="game",
            total=max_results,
        )

    yield from results


def fetch_candidates(
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

    params.setdefault("num_votes__gte", 1)
    params.setdefault("kennerspiel_score__gte", 0.0)
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

    return (
        pl.LazyFrame(candidates)
        .select(
            "bgg_id",
            "name",
            "year",
            "bgg_rank",
            "num_votes",
            "avg_rating",
            "bayes_rating",
            "rec_rating",
            "complexity",
            "kennerspiel_score",
        )
        .with_columns(
            kennerspiel=pl.col("kennerspiel_score") > kennerspiel_cutoff_score,
        )
        .with_columns(
            rec_rel_rank=pl.col("rec_rating").rank(method="max").over("kennerspiel")
            / pl.len().over("kennerspiel"),
        )
    )


def fetch_all_candidates(
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
) -> pl.LazyFrame:
    """Fetch all candidates from the recommendation API."""

    reviews = pl.read_csv(DATA_DIR / str(year) / "reviews.csv")
    include = reviews["bgg_id"]
    jury_members = reviews.select(pl.exclude("bgg_id", "name")).columns
    del reviews

    exclude = (
        pl.scan_csv(DATA_DIR / str(year) / "exclude.csv")
        .select("bgg_id")
        .collect()["bgg_id"]
    )
    prev_awards = (
        pl.scan_csv(
            [DATA_DIR / "sdj.csv", DATA_DIR / "ksdj.csv", DATA_DIR / "kindersdj.csv"],
        )
        .sort("jahrgang", descending=True)
        .filter(pl.col("jahrgang") < year)
        .select("bgg_id")
        .collect()["bgg_id"]
    )
    exclude = (
        pl.concat([exclude, prev_awards], how="vertical")
        .unique(maintain_order=True)
        .head(max_exclude_games)
    )
    del prev_awards

    LOGGER.info("Fetching candidates for %s", main_user)
    result = fetch_candidates(
        user_name=main_user,
        year=year,
        bgg_ids_include=include,
        bgg_ids_exclude=exclude,
        kennerspiel_cutoff_score=kennerspiel_cutoff_score,
        max_results=max_results,
        base_url=base_url,
        timeout=timeout,
        progress_bar=progress_bar,
    )

    for jury_member in jury_members:
        LOGGER.info("Fetching candidates for %s", jury_member)
        results_jury_member = fetch_candidates(
            user_name=f"{jury_member_prefix}{jury_member}",
            year=year,
            bgg_ids_include=include,
            bgg_ids_exclude=exclude,
            kennerspiel_cutoff_score=kennerspiel_cutoff_score,
            max_results=max_results,
            base_url=base_url,
            timeout=timeout,
            progress_bar=progress_bar,
        ).select("bgg_id", "rec_rating", "rec_rel_rank")

        result = result.join(
            results_jury_member,
            on="bgg_id",
            how="left",
            suffix=f"_{jury_member}",
        )

    return result.rename(
        {
            "rec_rating": f"rec_rating_{main_user}",
            "rec_rel_rank": f"rec_rel_rank_{main_user}",
        },
    )
