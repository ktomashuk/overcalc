# Overcalc

An overengineered calculator, built on purpose as interview prep. The project has two deliverables:

1. **The system:** a Python backend that follows Domain-Driven Design (FastAPI, SQLAlchemy, PostgreSQL,
   later Kafka and a React frontend). The layer and boundary rules in [ARCHITECTURE.md](ARCHITECTURE.md)
   are enforced in CI.
2. **The AI harness that builds it:** Claude Code agents take Jira tickets to reviewed pull requests,
   and every merge goes through the owner's review.

The design spec is [docs/superpowers/specs/2026-11-19-overcalc-architecture-design.md](docs/superpowers/specs/2026-11-19-overcalc-architecture-design.md).

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```sh
uv sync                       # create .venv with all workspace members and dev tools
uv run pre-commit install     # git hooks: ruff, mypy, import-linter, commit-message lint
make check                    # lint + typecheck + import contracts + tests (same as CI)
```

## Layout

| Path | What it is |
|---|---|
| `services/calculation/` | The calculation service (`overcalc_calculation`): `domain`, `application`, `infrastructure` and `presentation` layers |
| `tests/harness/` | Tests for the harness itself (permissions, hooks, agent definitions) |
| `.importlinter` | Layer contracts, identical to ARCHITECTURE.md §6 |
| `docs/superpowers/` | Spec and implementation plans |

## Harness

| Path | Role |
|---|---|
| `.claude/settings.json` | Committed permissions. Denies merging, force-pushing, pushing to `main`, destructive shell patterns and access to `settings.local.json`. Also wires up the hooks. |
| `.claude/settings.local.json` | **Not committed.** Owner-local overrides and the bot's GitHub token. |
| `.claude/hooks/ruff_on_edit.py` | PostToolUse hook: runs `ruff format` and `ruff check --fix` on each edited Python file, and reports unfixable findings back to the agent |
| `.claude/agents/implementer.md` | Subagent that delivers one ticket per run as a PR. It has no Jira tools; the orchestrator posts to Jira. |
| `.github/pull_request_template.md` | Sections every PR fills in |
| `.mcp.json` | Atlassian remote MCP server (Jira), authenticated per user via OAuth. Run `/mcp` once to log in. |

Skills come from the **superpowers** Claude Code plugin, **version 7.0.2**. Pin to that version when
reproducing agent behavior.

The deny rules are prefix matches, so they're defense in depth. The real enforcement is branch
protection and CI.

## Workflow

1. The owner moves a ticket to **Ready** and tells their Claude Code session to start it. That
   session is the orchestrator.
2. The orchestrator creates a worktree and branch (`OVC-<n>-slug`), dispatches the `implementer`
   subagent, posts its plan to the ticket and moves the ticket to **In Progress**.
3. The implementer works test-first, runs `make check`, then pushes as **`ktomashuk-bot`** and opens
   a PR from the template.
4. A review agent checks the PR, the implementer fixes the findings, and the ticket moves to **Review**.
5. The **owner** reviews. For changes, they tell the session "address the comments on PR #N". Only
   the owner merges; branch protection requires their approval and a green `check`.
