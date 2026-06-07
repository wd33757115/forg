# Forge — minimal runtime image (CLI + Web)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md main.py ./
COPY forge/ forge/
COPY web/ web/
COPY rule_packs/ rule_packs/

RUN pip install -e ".[dev]" -i https://pypi.org/simple

EXPOSE 8000

# Default: Web API (override for CLI demo)
CMD ["python", "main.py", "--web", "--host", "0.0.0.0", "--port", "8000"]
