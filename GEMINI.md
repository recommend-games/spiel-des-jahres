# GEMINI.md

Gemini CLI context for this repository. General project instructions are in `AGENTS.md`.

@AGENTS.md

## Agent Mandates

To maintain project integrity across all environments and agents:

- **CRITICAL: NEVER undo, revert, or overwrite manual changes made by the user.** Always perform a targeted `read_file` or check the current file state before applying an edit. If an agent's proposed change contradicts existing manual adjustments, the agent must defer to the user's manual state.
- **Path Conventions:** Respect the established path conventions in this repository (e.g., using `../board-game-data/` rather than `../../`).
- **Local Destructive Actions:** NEVER perform destructive actions that lead to irreversible data loss (e.g., `git reset --hard`, `rm -rf` on project directories, or complete file overwrites of established files) without explicit user confirmation. Prioritize surgical edits and always verify current file state to preserve uncommitted manual work.
- **Git Operational Logic:**
    - **Narrow Directives:** A directive to "commit" applies ONLY to the current state. It is NOT a license for autonomous commits in future turns.
    - **Safe Resets:** When asked to "undo" or "revert" a commit, always use methods that preserve changes in the working tree (e.g., `git reset HEAD~1`). NEVER use `--hard` resets.
- **Honest Error Tracking:** Never misattribute technical data loss (e.g., files deleted during a reset or failed edit) to user intent or feedback. Agents must take full responsibility for technical regressions.
- **Git Safety:** NEVER use force-push (`--force` or `--force-with-lease`) unless explicitly and specifically directed by the user for a particular command. Always perform a thorough `git status` and `git diff` before committing to ensure no unintended changes or reversions are included.
- **Validation:** Always run `uv run pre-commit` after any modification to ensure structural and stylistic compliance.
