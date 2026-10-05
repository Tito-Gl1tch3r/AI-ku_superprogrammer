# Reproducible pipeline for AI-ku_superprogrammer

PY ?= python3
BUDGET ?= 480
BATCH ?= 1
WORKERS ?= 3

.PHONY: help smoke test pilot write understand finalize stats report full

help:
	@echo "make smoke      - generate+verify samples for every family"
	@echo "make test       - run the pipeline test suite (pytest)"
	@echo "make write      - one write-stage batch (BUDGET seconds)"
	@echo "make understand - one understand-stage batch"
	@echo "make finalize   - dedup + splits + shards"
	@echo "make stats      - aggregate statistics"
	@echo "make report     - regenerate QUALITY_REPORT.md"
	@echo "make full       - same as pilot but with configs/full.json targets"

smoke:
	$(PY) -m generators.smoke --samples 3

test:
	$(PY) -m pytest tests/ -x -q

write:
	$(PY) scripts/build_dataset.py --config configs/pilot.json --stage write \
		--time-budget $(BUDGET) --batch $(BATCH) --workers $(WORKERS)

understand:
	$(PY) scripts/build_dataset.py --config configs/pilot.json --stage understand \
		--time-budget $(BUDGET) --batch $(BATCH) --workers $(WORKERS)

finalize:
	$(PY) scripts/finalize.py

stats:
	$(PY) scripts/make_stats.py

report:
	$(PY) scripts/make_quality_report.py

full:
	$(PY) scripts/build_dataset.py --config configs/full.json --stage write \
		--time-budget $(BUDGET) --batch $(BATCH) --workers $(WORKERS)
	$(PY) scripts/build_dataset.py --config configs/full.json --stage understand \
		--time-budget $(BUDGET) --batch $(BATCH) --workers $(WORKERS)
