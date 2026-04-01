set shell := ["zsh", "-cu"]

default:
  @just --list

sync:
  uv sync

test:
  uv run pytest -q

arch:
  PYTHONPATH=src uv run lint-imports

check:
  just test
  just arch

eval *args:
  uv run python run_eval.py {{args}}
