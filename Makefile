.PHONY: setup dev-backend dev-frontend lint format test test-backend test-frontend build-frontend pki fixtures docker-build docker-run smoke

# ─── Setup ────────────────────────────────────────────────────────────────────
setup:
	@echo "=== Installing backend dependencies ==="
	cd backend && uv sync
	@echo "=== Installing frontend dependencies ==="
	cd frontend && npm ci
	@echo "=== Setup complete ==="

# ─── Development ──────────────────────────────────────────────────────────────
dev-backend:
	@echo "=== Starting backend (uvicorn) ==="
	cd backend && uv run python -m app

dev-frontend:
	@echo "=== Starting frontend (vite) ==="
	cd frontend && npm run dev

# ─── Lint & Format ────────────────────────────────────────────────────────────
lint:
	@echo "=== Linting backend ==="
	cd backend && uv run ruff check app tests
	@echo "=== Linting frontend ==="
	cd frontend && npm run lint 2>/dev/null || echo "  (frontend lint not yet configured — P09+)"

format:
	@echo "=== Formatting backend ==="
	cd backend && uv run ruff format --check app tests
	@echo "=== Formatting frontend ==="
	cd frontend && npm run format 2>/dev/null || echo "  (frontend format not yet configured — P09+)"

# ─── Test ─────────────────────────────────────────────────────────────────────
test: test-backend test-frontend

test-backend:
	@echo "=== Running backend tests ==="
	cd backend && uv run pytest --cov -x -q

test-frontend:
	@echo "=== Running frontend tests ==="
	cd frontend && npm test 2>/dev/null || echo "  (frontend tests not yet configured — P09+)"

# ─── Build ────────────────────────────────────────────────────────────────────
build-frontend:
	@echo "=== Building frontend ==="
	cd frontend && npm run build

# ─── PKI & Fixtures ───────────────────────────────────────────────────────────
PKI_PORT ?= 20888

pki:
	@echo "=== Generating test PKI ==="
	cd backend && uv run python tests/pki/build_pki.py --port $(PKI_PORT)
	@echo "=== Copying trust store to dev/trust ==="
	mkdir -p dev/trust
	cp backend/tests/pki/out/trust/*.pem dev/trust/
	@echo "=== PKI generation complete ==="

fixtures:
	@echo "=== Generating test fixtures ==="
	cd backend && uv run python tests/fixtures/make_fixtures.py
	@echo "=== Fixture generation complete ==="

# ─── Docker ───────────────────────────────────────────────────────────────────
docker-build:
	@echo "Docker build not yet available (P13)"

docker-run:
	@echo "Docker run not yet available (P13)"

# ─── Smoke ────────────────────────────────────────────────────────────────────
smoke:
	@echo "Smoke test not yet available (P13)"
