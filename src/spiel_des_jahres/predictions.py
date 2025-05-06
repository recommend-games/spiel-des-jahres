from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date
from itertools import islice
from typing import TYPE_CHECKING

import polars as pl
import requests

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from typing import Any

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://recommend.games"


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
) -> Iterable[dict[str, Any]]:
    """Call to a Recommend.Games instance."""

    results = _recommend_games(
        base_url=base_url,
        timeout=timeout,
        request_params=request_params,
    )

    return islice(results, max_results) if max_results else results


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
            rec_rank=pl.col("rec_rating").rank(method="max").over("kennerspiel")
            / pl.len().over("kennerspiel"),
        )
    )
