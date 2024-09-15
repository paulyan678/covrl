PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help setup setup-rl test test-rl lint typecheck format format-check regress-smoke dry-run-vcs dry-run-questa audit clean

help:
	@$(PYTHON) -c 'print("Targets: setup setup-rl test test-rl lint typecheck format format-check regress-smoke dry-run-vcs dry-run-questa audit clean")'

setup:
	./scripts/bootstrap.sh

setup-rl:
	./scripts/bootstrap.sh --rl

test:
	$(PYTHON) -m unittest discover -s tests -v

test-rl:
	RUN_RL_TRAINING_SMOKE=1 $(PYTHON) -m pytest -q -p no:cacheprovider

lint:
	$(PYTHON) -m ruff check regression rl scripts tests

typecheck:
	$(PYTHON) -m mypy regression rl scripts tests

format:
	$(PYTHON) -m ruff format regression rl scripts tests

format-check:
	$(PYTHON) -m ruff format --check regression rl scripts tests

regress-smoke:
	$(PYTHON) scripts/regress.py suite smoke --simulator mock

dry-run-vcs:
	$(PYTHON) scripts/regress.py suite smoke --simulator vcs --dry-run

dry-run-questa:
	$(PYTHON) scripts/regress.py suite smoke --simulator questa --dry-run

audit:
	$(PYTHON) scripts/audit_repo.py

clean:
	$(PYTHON) scripts/regress.py clean
	$(PYTHON) -c 'import shutil; from pathlib import Path; [shutil.rmtree(p) for p in Path(".").rglob("__pycache__")]; [shutil.rmtree(p, ignore_errors=True) for p in (".pytest_cache", ".ruff_cache", ".mypy_cache")]'
