import csv
import dataclasses
import json
import logging
import sys
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
    reviewer_prefix: str = "",
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
                        bgg_user_name=f"{reviewer_prefix}{reviewer}",
                        bgg_user_rating=float(rating),
                        updated_at=updated_at,
                        scraped_at=now,
                    )


def main(file_path: str | Path) -> None:
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    ratings = reviews_csv_to_ratings(
        file_path,
        reviewer_prefix="s_d_j_",
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    for rating in ratings:
        rating_dict = dataclasses.asdict(rating)
        # Handle datetime objects in JSON serialization
        print(
            json.dumps(
                rating_dict,
                default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o),
            ),
        )


if __name__ == "__main__":
    main(sys.argv[1])
