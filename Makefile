# Makefile for integration_framework
.PHONY: install test lint lint-fix typecheck run run-single run-by-tag run-asyncio run-multiprocessing validate report graph clean

install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

test:
	python -m pytest --cov=integration_framework --cov-report=html tests integrations/*/tests/

lint:
	python -m ruff check .

lint-fix:
	python -m ruff check --fix .

typecheck:
	python -m mypy .

run:
	python -m batch --run-all

run-single:
	python -m batch --run-single

run-by-tag:
	python -m batch --run-by-tag

run-asyncio:
	python -m batch --run-all --parallel asyncio

run-multiprocessing:
	python -m batch --run-all --parallel multiprocessing

validate:
	python -m batch --validate

report:
	python -m batch --report $(shell date +%Y-%m)

graph:
	python generate_graph.py > process_graph.dot
	@echo "Generated process_graph.dot. To visualize, install Graphviz and run:"
	@echo "dot -Tpng process_graph.dot -o process_graph.png"

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ *.pyc */*.pyc */*/*.pyc
	rm -rf htmlcov .coverage
	rm -rf .mypy_cache
	rm -rf *.egg-info
	rm -rf output/*.yaml
	rm -f process_graph.dot process_graph.png

