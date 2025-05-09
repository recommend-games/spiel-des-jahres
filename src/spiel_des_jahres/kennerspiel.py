from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

import funcy
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegressionCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

if TYPE_CHECKING:
    from collections.abc import Iterable


def _parse_list(value: str | Iterable[str], prefix: str | None = None) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    values = funcy.distinct(value)
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
            ("todense", FunctionTransformer(csr_matrix.todense)),
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
    )


def train_model(
    data: pd.DataFrame,
    *,
    target_col: str = "ksdj",
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
