# CubeTrainer

A cstimer-style timer plus a jperm-style OLL/PLL algorithm trainer.

## Run

    uv run cubetrainer

## Checks

    uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest

## Git hooks

A pre-commit hook in `.githooks/` runs ruff and ty. Enable it once per clone:

    git config core.hooksPath .githooks
