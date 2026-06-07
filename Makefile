# Forge — common development commands
# Windows: use `make` from Git Bash / WSL, or run equivalent commands from README

.PHONY: setup install test test-integration test-llm demo demo-security demo-itil demo-mixed report lint clean docker help

PYTHON ?= .venv/Scripts/python
PIP ?= .venv/Scripts/pip

help:
	@echo "Forge Makefile targets:"
	@echo "  make setup          Create venv and install dependencies"
	@echo "  make test           Run pytest (fast suite, no LLM)"
	@echo "  make test-integration  Full pipeline integration tests"
	@echo "  make test-llm       Run LLM acceptance tests (requires API key)"
	@echo "  make report         Run security demo + save report to reports/"
	@echo "  make docker         Build and start Web via docker-compose"
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

test-integration:
	$(PYTHON) -m pytest tests/test_full_pipeline.py tests/test_v11_pipeline_integration.py tests/test_scenarios_integration.py -q

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

report:
	$(PYTHON) main.py --type security --no-feedback --no-report-prompt --report reports/latest-security.md

docker:
	docker compose up --build

lint:
	$(PYTHON) -m ruff check forge tests

clean:
	rm -rf .pytest_cache **/__pycache__ .ruff_cache
