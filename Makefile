.PHONY: install dev test lint format clean

install:
	pip install -e ".[dev]"

dev:
	pip install -e ".[dev,llm]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache

release:
	git tag -a v$(shell python -c "import importlib.metadata; print(importlib.metadata.version('pcb-forge'))") -m "Release v$(shell python -c "import importlib.metadata; print(importlib.metadata.version('pcb-forge'))")"
	git push --tags
