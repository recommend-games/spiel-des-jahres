from __future__ import annotations

import logging
from itertools import islice
from typing import TYPE_CHECKING

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
    **params: Any,
) -> Generator[dict[str, Any]]:
    url = f"{base_url}/api/games/recommend/"
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
    **params: Any,
) -> Iterable[dict[str, Any]]:
    """Call to a Recommend.Games instance."""

    results = _recommend_games(
        base_url=base_url,
        timeout=timeout,
        **params,
    )
    return islice(results, max_results) if max_results else results
