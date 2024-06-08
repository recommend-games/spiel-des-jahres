import argparse
import csv
import dataclasses
import itertools
import json
import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from spiel_des_jahres.data import AwardRatings, Rating
from spiel_des_jahres.utils import json_datetime

LOGGER = logging.getLogger(__name__)


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
    year = args.year or datetime.now(timezone.utc).year

    reviews_ratings = (
        reviews_csv_to_ratings(
            file_path=args.reviews_file,
            reviewer_prefix=args.reviewer_prefix or "",
            updated_at=datetime(year, 1, 1, tzinfo=timezone.utc),
        )
        if args.reviews_file
        else ()
    )

    awards_ratings = (
        awards_csv_to_ratings(
            file_path=args.awards_file,
            bgg_user_name=args.awards_user,
            award_ratings=AwardRatings(),
        )
        if args.awards_file and args.awards_user
        else ()
    )

    for rating_obj in itertools.chain(reviews_ratings, awards_ratings):
        rating_dict = dataclasses.asdict(rating_obj)
        rating_str = json.dumps(rating_dict, default=json_datetime)
        print(rating_str)


if __name__ == "__main__":
    main()
