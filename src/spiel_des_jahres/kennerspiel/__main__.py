from __future__ import annotations

import argparse
import logging
import sys

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
    # TODO: more args
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    LOGGER.info(args)

    LOGGER.info("Loading games from %s", SCRAPED_DIR)
    games = load_games(SCRAPED_DIR / "bgg_GameItem.csv").collect()
    LOGGER.info("Loaded %d games", len(games))

    LOGGER.info("Training model")
    model = train_model(games.to_pandas())

    LOGGER.info("Saving model to <%s>", args.dest)
    joblib.dump(model, args.dest)
    LOGGER.info("Done.")


if __name__ == "__main__":
    _main()
