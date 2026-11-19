# Overcalc — Architecture & Delivery Design

**Status:** Approved v1.0 · **Date:** 2026-11-19 · **Owner:** Kirill
**Published:** https://app.notion.com/p/41d1a4293a0e8158b761da33e4d54e03 (alongside "Overcalc — System Design Document" and "Overcalc — Repository Structure").

This document revisits the existing Notion design together with the owner. It **keeps** most of the system design
(domain model, events, outbox/inbox, 4-layer architecture, ARCHITECTURE.md). It **changes** how the project is
sequenced and delivered, and it **adds** the AI harness as a first-class deliverable.
Where this document and the Notion pages disagree, this document wins, and the Notion pages get updated when it's published.

Marking convention: **[decided]** = the owner decided it in the design conversation. **[proposed]** = Claude's call,
open to correction while reviewing. **[builder]** = deliberately left to whoever implements it.

---

## 1. Intent

Overcalc is an intentionally overengineered calculator. The joke is the domain; the engineering is the point.

It serves an owner preparing for **middle-to-senior backend developer** interviews, and it has **two equally important
deliverables** [decided]:

1. **A backend codebase built to a senior standard:** project structure, linters and type checking, CI/CD,
   and services built with DDD.
2. **The AI harness and agentic workflow that built it:** agents and skills for coding, reviewing and documenting,
   driven by a Jira Kanban board. This is the owner's first real agentic setup. It gets built **iteratively** as
   the project needs it, not all at once.

The overriding constraint [decided]: **the owner must be able to navigate, understand and explain anything in the repo.**

There is no deadline [decided]. That leaves room for a long tail of optional "proof of skill" integrations
(Grafana, Sentry, Keycloak + Google OAuth, PostHog tracking things like a user's favorite number or favorite operator).

## 2. Goals, non-goals, anti-goals

**Goals**
- A working calculator, built feature by feature in vertical slices, each one provable end to end.
- A modular monolith that later splits into services over Kafka without changing its external behavior.
- A versioned, explainable AI harness in the repo (`.claude/`) that an interviewer can be walked through like the code.
- An architecture where optional integrations plug in at the edges without editing the core.

**Non-goals**
- Production hosting, real users, SLAs.
- Symbolic math, graphing, calculus.
- Writing a harness from scratch. Existing skills (the superpowers plugin) get reused wherever they fit [decided].

**Anti-goals** (would make this a failure even if everything technically works)
- **Code the owner can't explain.** A repo full of green tests and agent-written code the owner can't defend has failed.
- **PRs too big to really review.** That quietly breaks the anti-goal above.
- **Speculative plugin frameworks.** "Support anything" abstraction layers are overengineering for real, not the joke kind.
  Only the cheap doors in §5.3 get left open.
- **Horizontal, layer-by-layer delivery** ("build the domain layer"), except for labeled enabler tickets (§6.2).
- **Infra eating the project.** The everyday local stack stays light.

## 3. Constraints

- **Human merge gate [decided]:** nothing is merged without the owner reading it, understanding it and approving it.
  The owner can always request changes.
- **Vertical slicing [decided]:** small, bite-sized changes, preferably with an E2E test. Some setup work is
  unavoidably horizontal, and that's accepted [decided].
- **Binding code rules:** `ARCHITECTURE.md` (4 layers, dependency matrix, per-layer libraries, naming, testing,
  enforcement). This design doesn't change it.
- **Stack:** Python ≥ 3.12, FastAPI, SQLAlchemy 2 (async), PostgreSQL, Docker, Kafka, React (optional, later), uv.
- **Current repo state:** a `uv init` stub (single `src/overcalc` package, `pytest`/`requests`/`pydantic` listed as
  runtime dependencies), no commits, no git remote. All of that gets replaced in Phase 0.

## 4. Approaches considered

### 4.1 System sequencing

| | Approach | Trade-off |
|---|---|---|
| **A** ✅ | **Monolith first, extract later.** One `calculation` service as a modular monolith (calculation / parsing / evaluation modules, in-process event bus). Ship feature slices there, then extract parser and evaluator behind Kafka as refactor slices. | Small, readable slices; learn domain and harness before distributed complexity; great extraction story. Kafka and the outbox arrive later. |
| B | **Distributed from day one.** The tracer bullet already crosses gateway → calculation → Kafka → parser → evaluator with stub logic. | Kafka exercised from the start, but heavy infra before any logic. Every slice touches 3–4 services, so PRs get big, which fights the merge-gate and understandability constraints. Hardest mode for a first agentic project. |
| C | **One service forever, Kafka only for outbound events.** | Least infra, most depth, but loses the saga, service extraction and inter-service contracts, which are core interview topics. Also loses the self-aware overengineering. |

**Picked: A** [decided]. It's the only option that keeps slices small and still delivers the distributed story.

### 4.2 Harness

| | Approach | Trade-off |
|---|---|---|
| **1** ✅ | **Reuse existing skills** (superpowers: brainstorming, writing-plans, TDD, subagent-driven development, code review, worktrees). Write project-specific agents and skills only where the generic ones don't fit. | Fast, and learning happens by reading good existing skills. Some behavior comes from outside the repo (plugin version must be pinned/noted). |
| 2 | Write every agent and skill from scratch. | Teaches more, but puts weeks of tooling ahead of any calculator. |

**Picked: 1** [decided]. **The first harness component is the coding agent** [decided] (§7.3).

## 5. System design

### 5.1 What carries over unchanged from the Notion design

Domain model and ubiquitous language, the `Calculation` aggregate and its state machine, the domain event catalogue
and envelope, choreography for the MVP saga, transactional outbox, inbox for idempotent consumers, partition key =
`calculation_id`, database per service (one Postgres instance, separate DBs and users), async API (202 + status/stream),
RFC 9457 errors, `Idempotency-Key`, exact decimals serialized as strings, monorepo with a uv workspace and the
`services/` + `libs/` layout, and the 4-layer layout per module.

The names that the E2E suite locks in (statuses, error codes, response shape, event names) are copied into
**Appendix A** of this document, so the repo doesn't depend on Notion access to build slices [proposed].

### 5.2 Modular monolith (Phases 0–1)

```
services/calculation/src/overcalc_calculation/
├── calculation/{domain,application,infrastructure,presentation}/
├── parsing/{domain,application,infrastructure,presentation}/
└── evaluation/{domain,application,infrastructure,presentation}/
```

- **Modules communicate only through events** on an in-process bus [proposed]. This resolves a contradiction:
  the Notion Repository Structure page said "application-level interfaces", while ARCHITECTURE.md §3 says
  "only through events". Events win, because that makes extraction (Phase 2) a matter of swapping the bus for Kafka.
- The in-process bus delivers the same event shapes that later go to Kafka, so subscribers in `presentation/`
  don't change when the transport does.
- `import-linter` forbids imports between modules from the first commit that has more than one module.

### 5.3 Extensibility: optional integrations plug in at the edges

Every optional integration has to fit one of three slots. If it doesn't, the design gets revisited (ADR) before
anyone builds it [proposed].

| Slot | Mechanism | Examples |
|---|---|---|
| **New event consumer** | Subscribes to `calculation.events.v1`. The producer doesn't know it exists. | History/CQRS read model, PostHog analytics ("favorite operator"), stats |
| **Adapter at an existing seam** | SDK or middleware set up in `presentation/`; exporters configured in the OTel collector | Sentry, Grafana stack (Tempo/Loki/Prometheus), Jaeger |
| **Edge concern** | Handled at the gateway; only an opaque ID reaches the core | Keycloak + Google OAuth (gateway validates the JWT, passes `user_id`) |

**Cheap doors left open now** (the only extensibility work done before a ticket asks for it) [proposed]:
1. **Events carry enough data for consumers.** For example, `CalculationCompleted` includes the operators used,
   so analytics never calls back into the core.
2. **An optional owner ID on `Calculation` from day one** (`owner_id: UserId | None`, always `None` until auth exists).
   Anonymous use keeps working forever. Auth fills it in later instead of forcing an aggregate change.
3. **OpenTelemetry is the single telemetry pipe** once observability lands. Services only talk to the collector,
   so changing the backend is a collector config change.
4. **Compose profiles:** `docker compose up` = core only. `--profile observability`, `--profile auth`,
   `--profile analytics` add extras.

### 5.4 Service extraction (Phase 2)

- Enabler first: Kafka (KRaft) in compose, outbox writer + relay, inbox, `libs/contracts`.
- Then one refactor slice per extraction: parser → `services/parser`, then evaluator → `services/evaluator`.
- **Acceptance rule for an extraction slice: the E2E suite passes unchanged.** If an E2E test has to change,
  the extraction changed behavior and the PR is wrong.
- `api-gateway` appears only once there is more than one service to route to, or when SSE/auth need it [proposed].
  Until then the calculation service serves the public API directly.

## 6. Delivery model

### 6.1 Vertical slices

Every ticket is a thin, user-visible change that cuts through every layer it needs, with an E2E acceptance test
[decided].

**E2E means the HTTP API** [proposed]: a pytest suite (httpx) runs against the stack started with docker compose,
in CI too. UI-level E2E (Playwright) arrives only if and when a frontend exists.

Initial slice list (Phase 1 order) [proposed]:

| # | Slice | E2E acceptance |
|---|---|---|
| 0 | Tracer bullet: `GET /health/ready` checks Postgres | compose up → 200 with `db: ok`; runs in CI |
| 1 | `POST /api/v1/calculations {"expression": "1 + 2"}` → result `3` (integers, `+` only), persisted | submit → poll `GET /api/v1/calculations/{id}` → `Completed`, `"3"` |
| 2 | `- * /`, correct precedence and associativity | `2 + 3 * 4` → `14`, `8 - 3 - 2` → `3` |
| 3 | Division by zero → typed error | `1 / 0` → `Failed`, error `DivisionByZero` (problem-details shape on sync validation errors) |
| 4 | Exact decimals | `0.1 + 0.2` → `"0.3"` |
| 5 | Parentheses, unary minus | `-(2 + 3) * 4` → `-20` |
| 6 | Syntax errors with position | `2 + * 3` → `Failed`, `SyntaxError` with `position` |
| 7 | Limits | > 1,000 chars or depth > 100 → typed rejection |

Even in the monolith the API is async (202 + poll), so the external contract doesn't change at extraction time
[proposed]. Inside the monolith, a calculation completes in-process quickly. The E2E tests poll with a short timeout.

### 6.2 Enabler tickets

Unavoidably horizontal work (CI changes, Kafka in compose, outbox plumbing, observability setup) is allowed as
explicitly labeled **enabler** tickets [decided]. Rules [proposed]: each one is as small as possible, states which
upcoming slice it unblocks, and comes with a check proving it works (a CI job, a smoke test, a compose healthcheck).

### 6.3 Phases

Each phase pairs a code capability with a harness capability. The code work is how the new harness piece gets tested [proposed].

| Phase | Code | Harness |
|---|---|---|
| **0** | Slice 0 (tracer bullet): uv workspace, `services/calculation` skeleton, ruff, mypy --strict, import-linter, pytest, Dockerfile, compose (Postgres), GitHub Actions CI, E2E job | **Coding agent** (§7.3), lint hooks, permission rules, branch protection, PR template |
| **1** | Slices 1–7 inside the modular monolith | **Jira ticket-writer skill**, **review agent** |
| **2** | Enabler (Kafka, outbox, inbox, contracts) → extract parser → extract evaluator | **Docs/ADR skill** |
| **3+** | Menu, any order: observability (OTel + Grafana), Sentry, history/CQRS service, gateway + SSE, auth (Keycloak + Google), PostHog analytics, React frontend, Schema Registry, K8s | Grow the harness as needed (e.g. an E2E/debugging agent) |

## 7. AI harness

### 7.1 Ticket lifecycle and who acts

| Board column | Actor | What happens |
|---|---|---|
| Backlog → Ready | agent drafts, **owner approves** | Agent breaks a phase into slice/enabler tickets. Owner decides what's ready. |
| In Progress | coding agent | Branch + worktree, short plan as a ticket comment, test-first implementation, checks green locally. |
| Review | review agent, then **owner** | Review agent checks the PR first and the coding agent fixes findings. Only then does the PR go to the owner, with CI green. |
| Changes requested | coding agent | Addresses the owner's PR comments and pushes again. |
| Done | **owner merges**, agent tidies up | Ticket moved; docs/ADRs updated if architecture changed. |

The ticket lifecycle is decided [decided: owner gate on merge]. The column-by-column split above is [proposed].
Until the Jira skill exists (Phase 1), tickets are created by hand or by the agent on request.

**Jira access** [proposed]: the Atlassian remote MCP server is declared in a committed `.mcp.json`. Each user
authenticates with OAuth, so there are no tokens in the repo, and the setup is versioned and reproducible instead of
depending on one account's claude.ai connector. Board columns: Backlog, Ready, In Progress, Review,
Changes Requested, Done. The project key is used in branch names (`<KEY>-12-short-slug`) and commit footers.

**Who drives the loop** [proposed]: in Phases 0–1 the **owner's interactive Claude Code session is the orchestrator**.
It picks a Ready ticket (when the owner says so), creates the worktree, and dispatches the `implementer` and
`reviewer` subagents following superpowers' `subagent-driven-development` (subagents can't start subagents, so the
review → fix → re-review loop lives in the orchestrator, not in the implementer). "Changes requested" is handled by
the owner telling the session "address the comments on PR #N". A headless trigger (GitHub Action running Claude Code
on a label or PR comment) is a later harness upgrade, not part of the initial design.

### 7.2 Guardrails: enforcement over trust

The same idea as import-linter: rules nobody checks get broken. **Prompts guide, and hooks/permissions/CI enforce** [proposed].

- **Branch protection on `main`:** PRs only, required owner approval, required green CI, no force-push.
  The agents open PRs from a separate bot account, so the owner's approval is a real, enforceable review (§10).
- **Agent permissions** (`.claude/settings.json`, committed): deny `gh pr merge`, `git push --force*`,
  `git push` to `main`, and destructive shell patterns. The owner's local overrides go in `settings.local.json` (not committed).
- **PR size:** one ticket per PR, a soft limit of ~400 changed lines excluding lockfiles and generated files.
  The review agent flags anything bigger, and the owner can bounce it.
- **PR description template:** what changed, why (ticket link), what to look at closely, how it was verified.
- **Changing the rules** (`ARCHITECTURE.md`, `.importlinter`, CI config, `.claude/` guardrails) is called out in
  the PR description, and an ADR is required where ARCHITECTURE.md §7 demands one.

### 7.3 The coding agent (first harness component)

The owner wants it set up properly according to current industry practice [decided]. Practice here moves fast,
so the components below follow the general principles that have held up: small scoped context, isolated
workspaces, test-first, mechanical verification, and a human gate at merge [proposed].

**Shape**
- A project subagent at `.claude/agents/implementer.md` (Claude Code subagent format: frontmatter with name,
  description, tool allowlist, model; the body is its system prompt).
- **Scope: exactly one ticket per run.** Input: the ticket (key, acceptance criteria). Output: a PR plus a ticket comment.
- **Reuses superpowers skills**: the orchestrator uses `using-git-worktrees` (one worktree per ticket, so the
  owner's checkout stays untouched) and `subagent-driven-development` (§7.1). The implementer itself follows
  `test-driven-development` and `verification-before-completion`. Its prompt references these skills instead of
  copying them. The superpowers plugin version in use is recorded in the repo README so behavior is reproducible.

**What the agent must do on every ticket**
1. Read the ticket, `CLAUDE.md`, `ARCHITECTURE.md` and the code the ticket touches. Post a short plan as a
   ticket comment (files, tests, approach).
2. Write the E2E acceptance test (or the enabler's check) first and watch it fail, then go inward with unit tests as needed.
3. Keep each commit small with conventional-commit messages. No unrelated refactors. Anything noticed along the way
   gets reported in the PR as a suggested follow-up ticket.
4. Run the full local check (one command, e.g. `just check`: ruff, mypy --strict, import-linter, unit + integration
   tests, E2E) and only then open the PR using the template.
5. Never merge, never force-push, never weaken a check (skip tests, add `# type: ignore`, loosen `.importlinter`)
   without saying so explicitly in the PR.

**Enforcement around it**
- `PostToolUse` hook on edits: `ruff format` + `ruff check --fix` on the edited Python file, with fast feedback
  to the agent [proposed].
- `pre-commit` hooks (ruff, mypy, import-linter, commit-message lint) catch the same things for human commits too [proposed].
- CI is the final authority. Hooks only make failures show up earlier.

**How we know it works:** its first real job is the Phase 0 tracer-bullet ticket. The owner reviews that PR with
the same rules as every later one. Problems found there feed back into the agent definition through a normal PR.

### 7.4 Later harness components (summarized, designed when their phase starts)

- **Jira ticket-writer skill (Phase 1):** turns a phase or idea into tickets that each state user-visible behavior
  and an E2E acceptance check. It splits layer-shaped tickets and labels enablers.
- **Review agent (Phase 1):** fresh context, read-only tools. Checks the PR against ARCHITECTURE.md (layers,
  per-layer libraries, naming, testing rules), the vertical-slice rule, PR size and test quality. Builds on the
  existing code-review skill plus a project checklist derived from ARCHITECTURE.md.
- **Docs/ADR skill (Phase 2):** writes ADRs and keeps the Notion pages in sync when architecture changes.

## 8. Decisions log

| Decision | Status |
|---|---|
| Two equal deliverables: codebase + AI harness | decided |
| Owner must be able to explain everything; human merge gate | decided |
| Vertical slices with E2E; labeled enablers accepted | decided |
| Optional integrations supported by design, built only on demand | decided |
| System approach A: monolith first, extract later | decided |
| Harness: reuse existing skills; coding agent first | decided |
| Modules communicate only via in-process events | proposed |
| E2E = HTTP API against compose; Playwright only with a frontend | proposed |
| Async API (202 + poll) even inside the monolith | proposed |
| Four cheap doors (§5.3); no other speculative extensibility | proposed |
| Gateway introduced only when needed | proposed |
| Enforcement over trust (branch protection, permissions, hooks, CI) | proposed |
| ~400-line soft PR limit; one ticket per PR | proposed |
| Public GitHub repo; agents use a separate bot account | decided |
| New Jira project `OVC` (Kanban) | decided |
| Owner's interactive session orchestrates implementer/reviewer subagents; headless later | proposed |
| Jira via committed `.mcp.json` (OAuth, no secrets in repo) | proposed |
| Phase 1 in-process event delivery is best-effort; outbox closes the gap in Phase 2 | proposed |
| Superseded: Notion SDD §13 milestones and Repository Structure §7 timeline (replaced by §6.3 here) | proposed |

## 9. Left to the builder

- Kafka client (`aiokafka` vs `confluent-kafka`), decided with an ADR at the start of Phase 2.
- `justfile` vs `Makefile` for the one-command checks.
- Exact hook scripts, CI job layout and caching.
- DI approach in `container.py` (hand-wired vs a library).
- In-process bus implementation details (sync dispatch vs an asyncio queue). Delivery is **best-effort in Phase 1,
  dispatched after the use case's commit** [proposed]: a crash between commit and dispatch can strand a calculation
  in `Requested`. That's a documented, known gap, closed in Phase 2 by the outbox. Consumers are written idempotently
  from the start anyway (domain-level idempotency is already an aggregate invariant).
- Exact AST shape inside the monolith (it becomes a versioned contract only in Phase 2).

## 10. Accounts and hosting

- **GitHub, public repo** [decided]. A public repo gets branch protection on a free account and doubles as portfolio material.
- **Separate bot GitHub account for the agents** [decided]. GitHub doesn't let a PR's author approve it, so the agent
  can't open PRs as the owner without breaking the merge gate. The bot is a repo collaborator with write access, and its
  fine-grained token is scoped to this repo only (contents, pull requests, issues). The owner reviews and merges as
  themselves. Branch protection requires 1 approving review from someone other than the author, plus green CI.
  The bot token lives in the owner's local environment (e.g. `GH_TOKEN` for the agent session), never in the repo.
- **New Jira project `OVC`** [decided], team-managed Kanban, columns Backlog, Ready, In Progress, Review,
  Changes Requested, Done. The Atlassian connector can't create Jira projects, so the owner creates it in the
  Jira UI as a Phase 0 step. Issue types: Story (vertical slice), Task (enabler), Bug.
- Creating the GitHub repo, the bot account and the Jira project are manual owner steps at the start of Phase 0.
  Agents take over from there.

---

## Appendix A. Contract names carried over from the Notion design

These names get locked in by the E2E suite and must survive extraction unchanged.

**Calculation statuses:** `Requested`, `Parsed`, `Completed`, `Failed`. Terminal: `Completed`, `Failed`.
Forward-only transitions; re-applying an event is a no-op.

**Error codes** (domain): `SyntaxError` (with `position`), `DivisionByZero`, `Overflow`, `ExpressionTooComplex`,
`Timeout` (only once the timeout sweeper exists).

**Public API (v1):**
- `POST /api/v1/calculations` `{"expression": str}` → `202` `{"calculation_id": uuid}` + `Location` header.
  Optional `Idempotency-Key` header (resubmits return the same calculation).
  Input that's invalid by shape (missing field, wrong type, over the length limit) → `4xx` RFC 9457 problem details.
- `GET /api/v1/calculations/{id}` → `{"calculation_id", "expression", "status", "result": str | null,
  "error": {"code", "message", "position"?} | null}`. `result` is a decimal serialized as a string.
- `GET /health/live`, `GET /health/ready`.
- Later: `GET /api/v1/calculations/{id}/stream` (SSE), `GET /api/v1/history?cursor=&limit=`.

**Domain events:** `CalculationRequested`, `ExpressionParsed`, `ExpressionRejected`, `ExpressionEvaluated`,
`EvaluationFailed`, `CalculationCompleted`, `CalculationFailed`. Envelope (once on Kafka): `event_id`, `event_type`,
`schema_version`, `occurred_at`, `correlation_id`, `causation_id`, `payload`.
`CalculationCompleted` additionally carries `operators_used` (door #1, §5.3) and `owner_id` (door #2).
