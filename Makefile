# Forge — common development commands
# Windows: use `make` from Git Bash / WSL, or run equivalent commands from README

.PHONY: setup install test test-llm demo demo-security demo-itil demo-mixed lint clean help

PYTHON ?= .venv/Scripts/python
PIP ?= .venv/Scripts/pip

help:
	@echo "Forge Makefile targets:"
	@echo "  make setup          Create venv and install dependencies"
	@echo "  make test           Run pytest (fast suite, no LLM)"
	@echo "  make test-llm       Run LLM acceptance tests (requires API key)"
	@echo "  make demo           Run general demo"
	@echo "  make demo-security  Run security scenario"
	@echo "  make demo-itil      Run ITIL scenario"
	@echo "  make demo-mixed     Run mixed security+ITIL scenario"
	@echo "  make lint           Run ruff"
	@echo "  make clean          Remove caches"

setup:
	python -m venv .venv
	$(PIP) install -e ".[dev]" -i https://pypi.org/simple

install: setup

test:
	$(PYTHON) -m pytest tests/ -q -k "not test_run_forge_cli_helper" -m "not llm"

test-llm:
	$(PYTHON) -m pytest tests/test_llm_reference_coverage.py -m llm -v --tb=short

demo:
	$(PYTHON) main.py --type general

demo-security:
	$(PYTHON) main.py --type security --no-feedback --report

demo-itil:
	$(PYTHON) main.py --type itil --no-feedback --report

demo-mixed:
	$(PYTHON) main.py --type mixed --no-feedback --report

lint:
	$(PYTHON) -m ruff check forge tests

clean:
	rm -rf .pytest_cache **/__pycache__ .ruff_cache
