from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib

from spiel_des_jahres.kennerspiel import SCRAPED_DIR, load_games, train_model

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a model to predict a game's Kennerspiel score.",
    )
    parser.add_argument(
        "dest",
        type=str,
        help="Path to save the trained model.",
    )
    parser.add_argument(
        "--games-path",
        "-g",
        type=str,
        default=SCRAPED_DIR / "bgg_GameItem.csv",
        help="Path to the games CSV file.",
    )
    parser.add_argument(
        "--kennerspiel-sonderpreis",
        "-k",
        type=str,
        nargs="+",
        default=(
            "Complex Game",
            "Fantasy Game",
            "Game of the Year Plus",
            "New Worlds Game",
        ),
        help="Sonderpreise that are considered Kennerspiel.",
    )
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    LOGGER.info(args)

    games_path = Path(args.games_path).resolve()
    LOGGER.info("Loading games from %s", games_path)
    games = load_games(
        games_path=games_path,
        kennerspiel_sonderpreis=args.kennerspiel_sonderpreis,
    ).collect()
    LOGGER.info("Loaded %d games", len(games))

    LOGGER.info("Training model")
    model = train_model(games.to_pandas())

    LOGGER.info("Saving model to <%s>", args.dest)
    joblib.dump(model, args.dest)
    LOGGER.info("Done.")


if __name__ == "__main__":
    _main()
