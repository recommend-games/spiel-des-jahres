import csv
import dataclasses
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Rating:
    bgg_id: int
    bgg_user_name: str
    bgg_user_rating: float
    updated_at: datetime
    scraped_at: datetime


def reviews_csv_to_ratings(
    file_path: str | Path,
    *,
    updated_at: datetime | None = None,
) -> Iterable[Rating]:
    file_path = Path(file_path).resolve()
    LOGGER.info("Reading reviews from <%s>", file_path)

    now = datetime.now(timezone.utc)
    updated_at = updated_at or now

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            bgg_id = int(row.pop("bgg_id"))
            name = row.pop("name", None)
            LOGGER.debug("Processing reviews for <%s> (BGG ID %d)", name, bgg_id)

            for reviewer, rating in row.items():
                if rating:
                    yield Rating(
                        bgg_id=bgg_id,
                        bgg_user_name=reviewer,
                        bgg_user_rating=float(rating),
                        updated_at=updated_at,
                        scraped_at=now,
                    )
