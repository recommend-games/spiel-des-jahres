from __future__ import annotations

import argparse
import csv
import dataclasses
import itertools
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from spiel_des_jahres.data import AwardRatings, Rating, User
from spiel_des_jahres.utils import json_datetime

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    import polars as pl

LOGGER = logging.getLogger(__name__)


def _parse_reviews_jl(
    file_path: str | Path,
) -> Iterable[dict[str, Any]]:
    file_path = Path(file_path).resolve()
    LOGGER.info("Reading reviews from <%s>", file_path)

    with file_path.open("r", newline="") as file:
        for article in map(json.loads, file):
            article_data = {
                "url": article.get("url"),
                "date_published": article.get("date_published"),
            }
            article_reviews = article.get("reviews")

            if not isinstance(article_reviews, list):
                LOGGER.warning("No reviews found in article: %s", article_data)
                continue

            for review in article_reviews:
                yield {**article_data, **review}


def reviews_jl_to_polars(
    file_path: str | Path,
) -> pl.DataFrame:
    import polars as pl

    reviews = pl.LazyFrame(_parse_reviews_jl(file_path)).select(
        pl.lit(None).alias("bgg_id"),
        pl.col("game_title").alias("name"),
        "url",
        "date_published",
        "reviewer_id",
        "rating",
    )

    reviewers = (
        reviews.select("reviewer_id")
        .unique()
        .sort("reviewer_id")
        .collect()["reviewer_id"]
    )

    return (
        reviews.collect()
        .pivot(on="reviewer_id", values="rating")
        .select(pl.exclude(reviewers), *reviewers)
        .sort("date_published", "name")
    )


def reviews_csv_to_users(
    file_path: str | Path,
    *,
    updated_at: datetime | None = None,
    reviewer_prefix: str = "",
    cols_to_exclude: Iterable[str] = ("bgg_id", "name", "url", "date_published"),
) -> Iterable[User]:
    file_path = Path(file_path).resolve()
    LOGGER.info("Reading users from <%s>", file_path)

    cols_to_exclude = frozenset(cols_to_exclude)

    now = datetime.now(timezone.utc)
    updated_at = updated_at or now

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or ()
        reviewer_names = [col for col in fieldnames if col not in cols_to_exclude]
        for reviewer_name in reviewer_names:
            if "_" in reviewer_name:
                first_name, last_name = reviewer_name.split("_", 1)
            else:
                first_name = reviewer_name
                last_name = None

            yield User(
                bgg_user_name=f"{reviewer_prefix}{reviewer_name}",
                first_name=first_name.capitalize() if first_name else None,
                last_name=last_name.capitalize() if last_name else None,
                updated_at=updated_at,
                scraped_at=now,
            )


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
            _ = row.pop("url", None)

            try:
                date_published = datetime.fromisoformat(row.pop("date_published", None))
            except Exception:
                date_published = None

            LOGGER.debug("Processing reviews for <%s> (BGG ID %d)", name, bgg_id)

            for reviewer, rating in row.items():
                if rating:
                    yield Rating(
                        bgg_id=bgg_id,
                        bgg_user_name=f"{reviewer_prefix}{reviewer}",
                        bgg_user_rating=float(rating),
                        updated_at=date_published or updated_at,
                        scraped_at=now,
                    )


def awards_csv_to_ratings(
    file_path: str | Path,
    *,
    bgg_user_name: str,
    award_ratings: AwardRatings,
) -> Iterable[Rating]:
    file_path = Path(file_path).resolve()
    LOGGER.info("Reading awards from <%s>", file_path)

    now = datetime.now(timezone.utc)

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            bgg_id = int(row["bgg_id"])
            year = int(row["jahrgang"])
            winner = bool(int(row["winner"]))
            nominated = bool(int(row["nominated"]))
            recommended = bool(int(row["recommended"]))
            sonderpreis = bool(row["sonderpreis"])
            rating = max(
                winner * award_ratings.winner_rating,
                nominated * award_ratings.nominated_rating,
                recommended * award_ratings.recommended_rating,
                sonderpreis * award_ratings.sonderpreis_rating,
            )
            yield Rating(
                bgg_id=bgg_id,
                bgg_user_name=bgg_user_name,
                bgg_user_rating=rating,
                updated_at=datetime(year, 1, 1, tzinfo=timezone.utc),
                scraped_at=now,
            )


def arg_parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--item-type",
        "-t",
        type=str,
        choices=("user", "rating"),
        default="rating",
        help="Type of items to process",
    )
    parser.add_argument(
        "--reviews-file",
        "-r",
        type=str,
        help="Path to the reviews CSV file",
    )
    parser.add_argument(
        "--reviewer-prefix",
        "-p",
        type=str,
        help="Prefix for BGG usernames",
    )
    parser.add_argument(
        "--year",
        "-y",
        type=int,
        help="Year of the reviews",
    )
    parser.add_argument(
        "--awards-file",
        "-a",
        type=str,
        help="Path to the awards CSV file",
    )
    parser.add_argument(
        "--awards-user",
        "-u",
        type=str,
        help="BGG username for awards",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity",
    )
    return parser.parse_args()


def main() -> None:
    args = arg_parse()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
    )

    reviews_users = (
        reviews_csv_to_users(
            file_path=args.reviews_file,
            reviewer_prefix=args.reviewer_prefix or "",
            updated_at=datetime(args.year, 1, 1, tzinfo=timezone.utc)
            if args.year
            else None,
        )
        if args.item_type == "user" and args.reviews_file
        else ()
    )

    reviews_ratings = (
        reviews_csv_to_ratings(
            file_path=args.reviews_file,
            reviewer_prefix=args.reviewer_prefix or "",
            updated_at=datetime(args.year, 1, 1, tzinfo=timezone.utc)
            if args.year
            else None,
        )
        if args.item_type == "rating" and args.reviews_file
        else ()
    )

    awards_ratings = (
        awards_csv_to_ratings(
            file_path=args.awards_file,
            bgg_user_name=args.awards_user,
            award_ratings=AwardRatings(),
        )
        if args.item_type == "rating" and args.awards_file and args.awards_user
        else ()
    )

    for obj in itertools.chain(reviews_users, reviews_ratings, awards_ratings):
        assert isinstance(obj, User | Rating), f"Invalid item type: {type(obj)}"
        obj_dict = dataclasses.asdict(obj)
        obj_str = json.dumps(obj_dict, default=json_datetime)
        print(obj_str)


if __name__ == "__main__":
    main()
