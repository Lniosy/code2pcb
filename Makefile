     1|.PHONY: install dev test lint format clean
     2|
     3|install:
     4|	pip install -e ".[dev]"
     5|
     6|dev:
     7|	pip install -e ".[dev,llm]"
     8|
     9|test:
    10|	pytest tests/ -v
    11|
    12|lint:
    13|	ruff check src/ tests/
    14|
    15|format:
    16|	ruff format src/ tests/
    17|
    18|typecheck:
    19|	mypy src/
    20|
    21|clean:
    22|	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    23|	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache
    24|
    25|release:
    26|	git tag -a v$(shell python -c "import importlib.metadata; print(importlib.metadata.version('code2pcb'))") -m "Release v$(shell python -c "import importlib.metadata; print(importlib.metadata.version('code2pcb'))")"
    27|	git push --tags
    28|