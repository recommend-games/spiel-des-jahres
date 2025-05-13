from __future__ import annotations

import importlib.resources
from collections.abc import Iterable
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

import funcy
import numpy as np
import pandas as pd
import polars as pl
from scipy.sparse import csr_matrix
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegressionCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

if TYPE_CHECKING:
    from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = importlib.resources.files() / "data"
SCRAPED_DIR = PROJECT_DIR.parent / "board-game-data" / "scraped"

FIRST_KENNERSPIEL_JAHRGANG = 2011


def _arg_to_iter(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return value
    return (value,)


def _parse_list(
    value: str | Iterable[str] | None,
    prefix: str | None = None,
) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    values = funcy.distinct(_arg_to_iter(value))
    return [f"{prefix}{v}" for v in values] if prefix else list(values)


def _list_series(series: pd.Series[str]) -> pd.Series[str]:
    name = series.name
    assert isinstance(name, str)
    return series.apply(_parse_list, prefix=name + ":")


def _list_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe.apply(_list_series)


def _concat_lists(iterable: Iterable[Iterable[str]]) -> list[str]:
    return list(chain.from_iterable(iterable))


def _combine_lists(dataframe: pd.DataFrame) -> pd.Series[list[str]]:
    return dataframe.apply(_concat_lists, axis=1)


def _playable_with(
    dataframe: pd.DataFrame,
    *,
    counts: Iterable[int],
    prefix: str = "",
    more_column: bool = False,
) -> pd.DataFrame:
    min_col, max_col = dataframe.columns
    result = pd.DataFrame(index=dataframe.index)

    count = 0  # just in case counts is empty
    for count in counts:
        playable = (dataframe[min_col] <= count) & (dataframe[max_col] >= count)
        column = f"{prefix}{count:02d}"
        result[column] = playable

    if more_column:
        playable = dataframe[max_col] > count
        column = f"{prefix}{count + 1:02d}+"
        result[column] = playable

    return result


def make_transformer(
    list_columns: Iterable[str] | str,
    player_count_columns: Iterable[str] | str = ("min_players", "max_players"),
    min_df: float = 0.01,
) -> ColumnTransformer:
    """Game transformer."""

    list_pipeline = Pipeline(
        [
            ("list_dataframe", FunctionTransformer(_list_dataframe)),
            ("combine_lists", FunctionTransformer(_combine_lists)),
            (
                "count_vectorizer",
                CountVectorizer(
                    analyzer=set,
                    min_df=min_df,
                    binary=True,
                    dtype=np.bool_,
                ),
            ),
            ("todense", FunctionTransformer(csr_matrix.toarray)),
        ],
    )

    playable_transformer = FunctionTransformer(
        _playable_with,
        kw_args={
            "counts": range(1, 11),
            "prefix": "playable_with_",
            "more_column": True,
        },
    )

    if isinstance(list_columns, str):
        list_columns = [list_columns]

    if isinstance(player_count_columns, str):
        player_count_columns = [player_count_columns]

    return ColumnTransformer(
        [
            ("list_pipeline", list_pipeline, list_columns),
            ("playable_transformer", playable_transformer, player_count_columns),
        ],
        remainder="passthrough",
        force_int_remainder_cols=False,
    )


def train_model(
    data: pd.DataFrame,
    *,
    target_col: str = "kennerspiel",
    numeric_columns: Iterable[str] | str = (
        "min_age",
        "min_time",
        "max_time",
        "cooperative",
        "complexity",
    ),
    list_columns: Iterable[str] | str = (
        "game_type",
        "mechanic",
        "category",
    ),
    player_count_columns: Iterable[str] | str = (
        "min_players",
        "max_players",
    ),
) -> Pipeline:
    numeric_columns = (
        [numeric_columns] if isinstance(numeric_columns, str) else list(numeric_columns)
    )
    list_columns = (
        [list_columns] if isinstance(list_columns, str) else list(list_columns)
    )
    player_count_columns = (
        [player_count_columns]
        if isinstance(player_count_columns, str)
        else list(player_count_columns)
    )
    features = numeric_columns + list_columns + player_count_columns

    transformer = make_transformer(
        list_columns=list_columns,
        player_count_columns=player_count_columns,
        min_df=0.1,
    )

    imputer = SimpleImputer()
    classifier = LogisticRegressionCV(
        class_weight="balanced",
        scoring="f1",
        max_iter=10_000,
    )

    pipeline = Pipeline(
        [
            ("transformer", transformer),
            ("imputer", imputer),
            ("classifier", classifier),
        ],
    )
    pipeline.fit(data[features], data[target_col])
    return pipeline


def load_games(
    games_path: Path = SCRAPED_DIR / "bgg_GameItem.csv",
    kennerspiel_sonderpreis: Iterable[str] | None = (
        "Complex Game",
        "Fantasy Game",
        "Game of the Year Plus",
        "New Worlds Game",
    ),
) -> pl.LazyFrame:
    with (
        importlib.resources.as_file(DATA_DIR / "sdj.csv") as spiel_path,
        importlib.resources.as_file(DATA_DIR / "ksdj.csv") as kennerspiel_path,
    ):
        spiel = (
            pl.scan_csv(spiel_path)
            .with_columns(
                kennerspiel=pl.lit(value=False)
                if kennerspiel_sonderpreis is None
                else pl.col("sonderpreis").is_in(frozenset(kennerspiel_sonderpreis)),
            )
            .filter(
                (pl.col("jahrgang") > FIRST_KENNERSPIEL_JAHRGANG)
                | (
                    (pl.col("jahrgang") == FIRST_KENNERSPIEL_JAHRGANG)
                    & (pl.col("nominated") == 1)
                )
                | pl.col("kennerspiel"),
            )
            .select("bgg_id", pl.col("kennerspiel").fill_null(value=False))
        )
        kennerspiel = pl.scan_csv(kennerspiel_path).select("bgg_id", kennerspiel=True)
        sdj = pl.concat([spiel, kennerspiel]).collect()

    return pl.scan_csv(games_path, infer_schema_length=None).join(
        sdj.lazy(),
        on="bgg_id",
        how="inner",
    )
