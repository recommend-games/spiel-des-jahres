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
candidates
