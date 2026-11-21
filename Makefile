# One-command checks. CI runs the same targets, so "green locally" means "green in CI".
.PHONY: check lint typecheck arch test e2e

check: lint typecheck arch test e2e

lint:
	uv run ruff check .
	uv run ruff format --check .

# mypy runs per source tree: services/calculation/tests and the root tests/ are both
# packages named `tests`, which mypy would report as duplicate modules in a single run.
typecheck:
	cd services/calculation && uv run mypy src tests
	uv run mypy tests

arch:
	uv run lint-imports

# Each suite is its own `tests` package, so suites run one directory at a time
# (collecting several `tests` packages in one pytest run makes their module names clash).
test:
	uv run pytest services/calculation/tests
	uv run pytest tests/harness

# Full stack in docker compose, then the E2E suite against it. Teardown always runs, and on
# failure the compose logs are printed first; the target exits with pytest's status.
e2e:
	docker compose up -d --build --wait; up=$$?; \
	if [ $$up -eq 0 ]; then uv run pytest tests/e2e; status=$$?; else status=$$up; fi; \
	if [ $$status -ne 0 ]; then docker compose logs; fi; \
	docker compose down -v; \
	exit $$status
