# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
import logging
import sys

import jupyter_black
import polars as pl

from spiel_des_jahres.predictions import fetch_all_candidates

jupyter_black.load()

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)

pl.Config.set_tbl_rows(100)
pl.Config.set_fmt_str_lengths(100)

# %%
candidates = fetch_all_candidates(
    year=2025,
    max_results=None,
    progress_bar=True,
).collect()
candidates.shape

# %%
weights = {
    "rec_score_s_d_j": 14.0,
    "rec_score_udo_bartsch": 1.0,
    "rec_score_johanna_france": 1.0,
    "rec_score_tobias_franke": 1.0,
    "rec_score_manuel_fritsch": 1.0,
    "rec_score_martina_fuchs": 1.0,
    "rec_score_karsten_grosser": 1.0,
    "rec_score_maren_hoffmann": 1.0,
    "rec_score_stephan_kessler": 1.0,
    "rec_score_tim_koch": 1.0,
    "rec_score_michaela_poignee": 1.0,
    "rec_score_christoph_schlewinski": 1.0,
    "rec_score_harald_schrapers": 1.0,
    "rec_score_nico_wagner": 1.0,
    "rec_score_julia_zerlik": 1.0,
}
sum_weights = sum(weights.values())
len(weights), sum_weights

# %%
candidates = candidates.with_columns(
    score=sum(pl.col(col) * weight for col, weight in weights.items()) / sum_weights,
)
candidates.shape

# %%
candidates.sort("score", descending=True).head(100)

# %%
candidates.sort("kennerspiel", "score", descending=[False, True]).write_csv(
    "candidates.csv",
    float_precision=5,
)
