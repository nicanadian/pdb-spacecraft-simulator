# Spacecraft Simulator Makefile
# Aerie integration, testing, and build targets

.PHONY: help install install-dev aerie-setup aerie-up aerie-down aerie-status aerie-health \
        plan schedule export test test-cov test-ete test-ete-smoke test-e2e \
        viewer viewer-build mcp-server lint format clean \
        dev e2e modelgen modelgen-extract modelgen-build modelgen-check modelgen-serve \
        modelgen-viewer-build modelgen-e2e golden-demo schema-snapshot schema-check

# Detect Python 3.10+ (prefer homebrew python3.11 if system python is 3.9)
PYTHON ?= $(shell python3 -c "import sys; print('python3' if sys.version_info >= (3,10) else '')" 2>/dev/null || echo "")
ifeq ($(PYTHON),)
PYTHON := $(shell which python3.11 2>/dev/null || which python3.12 2>/dev/null || echo python3)
endif

# Default target
help:
	@echo "Spacecraft Simulator - Available Targets"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install         Install package in production mode"
	@echo "  install-dev     Install package in development mode with all extras"
	@echo ""
	@echo "Aerie Integration:"
	@echo "  aerie-setup     Clone Aerie repository (one-time setup)"
	@echo "  aerie-up        Start Aerie services via Docker Compose"
	@echo "  aerie-down      Stop Aerie services"
	@echo "  aerie-status    Check health of Aerie services"
	@echo "  aerie-health    Alias for aerie-status"
	@echo ""
	@echo "Plan Operations:"
	@echo "  plan            Create plan from scenario (SCENARIO=path/to/scenario.yaml)"
	@echo "  schedule        Run scheduler on current plan"
	@echo "  export          Export plan from Aerie"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run unit tests (excluding ETE)"
	@echo "  test-cov        Run unit tests with coverage"
	@echo "  test-ete        Run ETE validation tests"
	@echo "  test-ete-smoke  Run ETE smoke tests only (<60s)"
	@echo "  test-e2e        Run full end-to-end validation workflow"
	@echo ""
	@echo "Viewer & MCP:"
	@echo "  viewer          Start viewer dev server (localhost:3002)"
	@echo "  viewer-build    Build viewer for production"
	@echo "  mcp-server      Start MCP HTTP server (localhost:8765)"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint            Run linters (ruff)"
	@echo "  format          Format code (black)"
	@echo "  clean           Remove build artifacts and caches"
	@echo ""
	@echo "Quick Start:"
	@echo "  dev             One-command bootstrap (install + build + extract)"
	@echo "  e2e             Full E2E: extract + build + viewer build + serve + Playwright tests"
	@echo ""
	@echo "Modelgen:"
	@echo "  modelgen            Full pipeline: extract + build + viewer build"
	@echo "  modelgen-extract    Extract architecture IR from source"
	@echo "  modelgen-build      Apply overrides and produce model.json"
	@echo "  modelgen-check      Validate overrides for staleness"
	@echo "  modelgen-serve      Serve architecture viewer (port 8090)"
	@echo "  modelgen-viewer-build  Build the modelui SolidJS viewer"
	@echo "  modelgen-e2e        Run modelgen Playwright tests"
	@echo ""
	@echo "Demos & CI:"
	@echo "  golden-demo     Run golden demo scenario (seed data + verify)"
	@echo "  schema-snapshot Generate IR JSON schema snapshot for drift detection"
	@echo "  schema-check    Check IR schema for drift against snapshot"

# ============================================================================
# Setup & Installation
# ============================================================================

install:
	pip install .

install-dev:
	pip install -e ".[dev,validation,aerie,medium]"

# ============================================================================
# Aerie Integration
# ============================================================================

AERIE_VERSION ?= v2.17.0
AERIE_DIR := .aerie-upstream
AERIE_COMPOSE := $(AERIE_DIR)/deployment/docker-compose.yml

aerie-setup:
	@echo "Setting up Aerie $(AERIE_VERSION)..."
	@if [ ! -d "$(AERIE_DIR)" ]; then \
		git clone --depth 1 --branch $(AERIE_VERSION) \
			https://github.com/NASA-AMMOS/aerie.git $(AERIE_DIR); \
	else \
		echo "Aerie directory already exists. Use 'make aerie-clean' to reset."; \
	fi
	@if [ -f "aerie/.env.template" ] && [ ! -f "aerie/.env" ]; then \
		cp aerie/.env.template aerie/.env; \
		echo "Created aerie/.env from template. Edit as needed."; \
	fi
	@echo "Aerie setup complete."

aerie-up: aerie-env-check
	@echo "Starting Aerie services..."
	cd $(AERIE_DIR)/deployment && docker compose up -d
	@echo "Waiting for services to become healthy..."
	@python scripts/aerie_health_check.py --wait --timeout 120
	@echo "Aerie is ready at http://localhost:8080"

aerie-down:
	@echo "Stopping Aerie services..."
	cd $(AERIE_DIR)/deployment && docker compose down
	@echo "Aerie services stopped."

aerie-status:
	@python scripts/aerie_health_check.py

aerie-clean:
	@echo "Removing Aerie directory..."
	rm -rf $(AERIE_DIR)
	@echo "Aerie cleaned."

aerie-env-check:
	@if [ ! -d "$(AERIE_DIR)" ]; then \
		echo "Error: Aerie not set up. Run 'make aerie-setup' first."; \
		exit 1; \
	fi

# ============================================================================
# Plan Operations
# ============================================================================

SCENARIO ?= examples/scenarios/leo_ops.yaml
PLAN_NAME ?= $(shell basename $(SCENARIO) .yaml)

plan: aerie-status
	@echo "Creating plan from scenario: $(SCENARIO)"
	python scripts/create_plan.py --scenario $(SCENARIO) --name $(PLAN_NAME)

schedule: aerie-status
	@echo "Running scheduler..."
	python scripts/run_scheduler.py --plan $(PLAN_NAME)

export: aerie-status
	@echo "Exporting plan..."
	python scripts/export_plan.py --plan $(PLAN_NAME) --output exports/$(PLAN_NAME)

# ============================================================================
# Simulation
# ============================================================================

FIDELITY ?= LOW
PLAN_FILE ?= exports/$(PLAN_NAME)/plan.json

sim:
	simrun run --plan $(PLAN_FILE) --fidelity $(FIDELITY)

sim-low:
	$(MAKE) sim FIDELITY=LOW

sim-medium:
	$(MAKE) sim FIDELITY=MEDIUM

# ============================================================================
# Testing
# ============================================================================

test:
	pytest tests/ --ignore=tests/ete -v

test-cov:
	pytest tests/ --ignore=tests/ete --cov=sim --cov-report=term-missing

test-ete:
	pytest tests/ete/ -v

test-ete-smoke:
	pytest tests/ete/ -m "ete_smoke" -v

test-ete-full:
	pytest tests/ete/ -v --tb=short

test-e2e: aerie-status
	@echo "Running end-to-end validation..."
	@echo "Step 1: Creating plan from scenario..."
	python scripts/create_plan.py --scenario validation/scenarios/ssr_baseline.yaml
	@echo "Step 2: Running scheduler..."
	python scripts/run_scheduler.py --plan ssr_baseline
	@echo "Step 3: Exporting plan..."
	python scripts/export_plan.py --plan ssr_baseline --output exports/ssr_baseline
	@echo "Step 4: Running LOW fidelity simulation..."
	simrun run --plan exports/ssr_baseline/plan.json --fidelity LOW --output runs/e2e_low
	@echo "Step 5: Running MEDIUM fidelity simulation..."
	simrun run --plan exports/ssr_baseline/plan.json --fidelity MEDIUM --output runs/e2e_medium
	@echo "Step 6: Running cross-fidelity validation..."
	python -m validation.cross_fidelity.comparator runs/e2e_low runs/e2e_medium
	@echo "Step 7: Generating visualization..."
	simrun viz --run runs/e2e_medium
	@echo "End-to-end validation complete."

# ============================================================================
# Code Quality
# ============================================================================

lint:
	ruff check sim/ cli/ tests/

format:
	black sim/ cli/ tests/

# ============================================================================
# Viewer & MCP Server
# ============================================================================

viewer:
	@echo "Starting viewer development server..."
	cd viewer && npm run dev

viewer-build:
	@echo "Building viewer for production..."
	cd viewer && npm run build

mcp-server:
	@echo "Starting MCP HTTP server on port 8765..."
	python -m sim_mcp.http_server --port 8765

aerie-health: aerie-status

# ============================================================================
# Quick Start / Bootstrap
# ============================================================================

dev: install-dev modelgen
	@echo ""
	@echo "Development environment ready."
	@echo "  Run 'make test' to run tests"
	@echo "  Run 'make modelgen-serve' to view architecture"
	@echo "  Run 'make e2e' to run full E2E validation"

e2e: modelgen modelgen-e2e
	@echo "Full E2E validation passed."

# ============================================================================
# Modelgen - Architecture Model Generator
# ============================================================================

modelgen: modelgen-extract modelgen-build modelgen-viewer-build
	@echo "Modelgen pipeline complete."
	@echo "  model.json: build/modelgen/model.json"
	@echo "  viewer:     tools/modelui/dist/"
	@echo "  Run 'make modelgen-serve' to view"

modelgen-extract:
	@echo "Extracting architecture from source..."
	$(PYTHON) -m tools.modelgen.cli extract \
		--root . --mappings spec/mappings.yml \
		-o build/modelgen/ir.json

modelgen-build: build/modelgen/ir.json
	@echo "Building model.json with overrides..."
	$(PYTHON) -m tools.modelgen.cli build \
		--ir build/modelgen/ir.json \
		--overrides spec/overrides.yml \
		-o build/modelgen/

modelgen-check: build/modelgen/ir.json
	$(PYTHON) -m tools.modelgen.cli check \
		--ir build/modelgen/ir.json \
		--overrides spec/overrides.yml

modelgen-viewer-build:
	@echo "Building modelui viewer..."
	cd tools/modelui && npm install --silent && npx vite build
	cp build/modelgen/model.json tools/modelui/dist/model.json

modelgen-serve: tools/modelui/dist/model.json
	$(PYTHON) -m tools.modelgen.cli serve \
		--dir tools/modelui/dist --port 8090

modelgen-e2e: tools/modelui/dist/model.json
	@echo "Running modelgen unit + E2E tests..."
	$(PYTHON) -m pytest tests/tools/test_modelgen/ -v

tools/modelui/dist/model.json: build/modelgen/model.json
	@mkdir -p tools/modelui/dist
	cp build/modelgen/model.json tools/modelui/dist/model.json

build/modelgen/ir.json:
	@$(MAKE) modelgen-extract

build/modelgen/model.json: build/modelgen/ir.json
	@$(MAKE) modelgen-build

# ============================================================================
# Golden Demo Scenarios
# ============================================================================

golden-demo:
	@echo "Running golden demo scenario..."
	$(PYTHON) scripts/golden_demo.py
	@echo "Golden demo passed."

# ============================================================================
# Interface Schema Drift Detection
# ============================================================================

SCHEMA_SNAPSHOT := spec/ir_schema_snapshot.json

schema-snapshot: build/modelgen/ir.json
	@echo "Generating IR schema snapshot..."
	$(PYTHON) scripts/schema_snapshot.py --ir build/modelgen/ir.json --output $(SCHEMA_SNAPSHOT)
	@echo "Snapshot written to $(SCHEMA_SNAPSHOT)"

schema-check: build/modelgen/ir.json
	@echo "Checking IR schema for drift..."
	$(PYTHON) scripts/schema_snapshot.py --ir build/modelgen/ir.json --check $(SCHEMA_SNAPSHOT)

# ============================================================================
# Cleanup
# ============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
