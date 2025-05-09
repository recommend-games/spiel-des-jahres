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
import jupyter_black
import numpy as np
import polars as pl
from pathlib import Path
from spiel_des_jahres.kennerspiel import load_games, train_model

jupyter_black.load()

pl.Config.set_tbl_rows(100)
pl.Config.set_fmt_str_lengths(100)

# %%
games = load_games().collect()
games.shape

# %%
games.sample(10)

# %%
games.describe()

# %%
model = train_model(games.to_pandas())
model

# %%
np.mean(model.predict(games.to_pandas()) == games["kennerspiel"].to_numpy())
