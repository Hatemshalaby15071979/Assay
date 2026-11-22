# Assay — developer entry points.
# All commands run fully offline once dependencies are installed.

PYTHON ?= python3

.PHONY: check-scaffold check-offline check-docs check-determinism test test-cov demo run all scale security analyze compatibility policy

check-scaffold:
	$(PYTHON) scripts/check-scaffold.py

check-offline:
	$(PYTHON) scripts/check-offline.py

check-docs:
	$(PYTHON) scripts/check-doc-consistency.py

check-determinism:
	PYTHONPATH=src $(PYTHON) scripts/check-determinism.py --out out/determinism

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

# Ops tasks: policy validation, analyze, compatibility.
policy:
	PYTHONPATH=src $(PYTHON) -m sheet_solution parse-policy --policy examples/policy.example.yaml

analyze:
	PYTHONPATH=src $(PYTHON) -m sheet_solution analyze --sheet examples/example-sheet.xlsx --out out/analyze

compatibility:
	PYTHONPATH=src $(PYTHON) -m sheet_solution compatibility \
		--sheet-a examples/compare-baseline.xlsx --sheet-b examples/compare-new.xlsx \
		--out out/compat

all: check-scaffold check-offline check-docs test demo

# Bounded scale smoke for the compare path (not a capacity claim).
scale:
	PYTHONPATH=src $(PYTHON) scripts/scale-stress.py --rows 10000

# Fail-closed secret scan over every reachable commit.
security:
	$(PYTHON) tooling/security/scan_history_secrets.py

gui:
	bash gui.sh

release:
	bash scripts/make-release.sh
