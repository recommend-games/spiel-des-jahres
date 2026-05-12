# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Additional Commands

| Task | Command |
| :--- | :--- |
| Single test | `uv run pytest tests/test_foo.py::test_bar` |
| Train kennerspiel model | `uv run python -m spiel_des_jahres.kennerspiel <dest.joblib>` |

## LLM Pipeline

Uses the OpenAI `responses.parse()` API with a Pydantic response format — not the chat completions endpoint.
