# Sheet Solution — developer entry points.
# All commands run fully offline once dependencies are installed.

PYTHON ?= python3

.PHONY: check-scaffold check-offline check-determinism test test-cov demo run all

check-scaffold:
	$(PYTHON) scripts/check-scaffold.py

check-offline:
	$(PYTHON) scripts/check-offline.py

check-determinism:
	$(PYTHON) scripts/check-determinism.py --out out/determinism

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q

test-cov:
	PYTHONPATH=src $(PYTHON) -m pytest --cov=src/sheet_solution --cov-report=term-missing -q

# Reused spine demo (inherited engine).
demo:
	PYTHONPATH=src $(PYTHON) -m sheet_solution demo --out out/demo

# Sheet-audit run against the example template + sheet.
run:
	PYTHONPATH=src $(PYTHON) -m sheet_solution run \
		--sheet examples/example-sheet.xlsx --template examples/check-template.example.txt \
		--out out/report

all: check-scaffold check-offline test demo

gui:
	PYTHONPATH=src $(PYTHON) gui/main.py

release:
	bash scripts/make-release.sh
