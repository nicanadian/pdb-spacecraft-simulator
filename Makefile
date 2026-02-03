# Spacecraft Simulator Makefile
# Aerie integration, testing, and build targets

.PHONY: help install install-dev aerie-setup aerie-up aerie-down aerie-status aerie-health \
        plan schedule export test test-cov test-ete test-ete-smoke test-e2e \
        viewer viewer-build mcp-server lint format clean

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
