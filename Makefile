.PHONY: install lint format test run clean

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

test:
	pytest -q

run:
	seek-scraper search "data engineer" --where "All Sydney NSW" --listed-within 7 --limit 20

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
