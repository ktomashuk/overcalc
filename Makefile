# One-command checks. CI runs the same targets, so "green locally" means "green in CI".
.PHONY: test

# Each suite is its own `tests` package, so suites run one directory at a time
# (collecting several `tests` packages in one pytest run makes their module names clash).
test:
	uv run pytest services/calculation/tests
