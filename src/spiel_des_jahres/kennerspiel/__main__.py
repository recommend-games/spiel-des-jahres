from __future__ import annotations

import sys

import joblib

from spiel_des_jahres.kennerspiel import load_games, train_model

# TODO: add argparse


def _main() -> None:
    dest = sys.argv[1]
    games = load_games().collect()
    model = train_model(games.to_pandas())
    joblib.dump(model, dest)


if __name__ == "__main__":
    _main()
