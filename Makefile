# Forge — common development commands
# Windows: use `make` from Git Bash / WSL, or run equivalent commands from README

.PHONY: setup install test demo demo-security demo-itil lint clean help

PYTHON ?= .venv/Scripts/python
PIP ?= .venv/Scripts/pip

help:
	@echo "Forge Makefile targets:"
	@echo "  make setup          Create venv and install dependencies"
	@echo "  make test           Run pytest (fast suite)"
	@echo "  make demo           Run general demo"
	@echo "  make demo-security  Run security scenario"
	@echo "  make demo-itil      Run ITIL scenario"
	@echo "  make lint           Run ruff"
	@echo "  make clean          Remove caches"

setup:
	python -m venv .venv
	$(PIP) install -e ".[dev]" -i https://pypi.org/simple

install: setup

test:
	$(PYTHON) -m pytest tests/ -q --ignore=tests/test_full_pipeline.py -k "not test_run_forge_cli_helper"

demo:
	$(PYTHON) main.py --type general

demo-security:
	$(PYTHON) main.py --type security --no-feedback

demo-itil:
	$(PYTHON) main.py --type itil --no-feedback

lint:
	$(PYTHON) -m ruff check forge tests

clean:
	rm -rf .pytest_cache **/__pycache__ .ruff_cache
