# One-command checks. CI runs the same targets, so "green locally" means "green in CI".
.PHONY: check lint typecheck arch test

check: lint typecheck arch test

lint:
	uv run ruff check .
	uv run ruff format --check .

# mypy runs per source tree: services/calculation/tests and the root tests/ are both
# packages named `tests`, which mypy would report as duplicate modules in a single run.
typecheck:
	cd services/calculation && uv run mypy src tests
	uv run mypy tests tools

arch:
	uv run lint-imports

# Each suite is its own `tests` package, so suites run one directory at a time
# (collecting several `tests` packages in one pytest run makes their module names clash).
test:
	uv run pytest services/calculation/tests
	uv run pytest tests/harness
	uv run pytest tests/architecture
