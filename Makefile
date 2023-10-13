PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help setup setup-rl test lint format format-check clean

help:
	@$(PYTHON) -c 'print("Targets: setup setup-rl test lint format format-check clean")'

setup:
	./scripts/bootstrap.sh

setup-rl:
	./scripts/bootstrap.sh --rl

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check regression rl scripts tests

format:
	$(PYTHON) -m ruff format regression rl scripts tests

format-check:
	$(PYTHON) -m ruff format --check regression rl scripts tests

clean:
	$(PYTHON) -c 'import shutil; from pathlib import Path; [shutil.rmtree(p) for p in Path(".").rglob("__pycache__")]; shutil.rmtree(".pytest_cache", ignore_errors=True); shutil.rmtree(".ruff_cache", ignore_errors=True)'
