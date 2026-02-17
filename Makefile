.PHONY: all install test lint format typecheck build clean bench

all: lint test typecheck

install:
	pip install -e ".[dev,all]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/

build:
	python -m build

bench:
	.venv/bin/python -m benchmarks.bench_memorymesh

clean:
	rm -rf dist/ build/ *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
