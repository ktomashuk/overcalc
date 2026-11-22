# Architecture Rules

This document holds the **binding rules** for how backend code in Overcalc is structured.
The *why* behind the system (bounded contexts, services, messaging) lives in the Notion design doc.
This file covers *how code is laid out and what may depend on what*.

If code and this document disagree, one of them is wrong. Fix it or open an ADR. Don't let them drift.

---

## 1. The four layers

Every module (a bounded context inside a service, or a whole service once extracted) has exactly four layers:

```
overcalc_<service>/[<module>/]
├── domain/           # what the business IS
├── application/      # what the business DOES
│   └── interfaces/   # what the business NEEDS from the outside world (ports)
├── infrastructure/   # HOW those needs are met (adapters)
└── presentation/     # how the outside world TALKS to us (entry points + wiring)
```

### 1.1 Dependency matrix

Rows may import columns. Anything not marked ✅ is forbidden.

| from \ to                  | domain | application.interfaces | application (rest) | infrastructure | presentation |
|----------------------------|:------:|:----------------------:|:------------------:|:--------------:|:------------:|
| **domain**                 |   ✅   |           ❌           |         ❌         |       ❌       |      ❌      |
| **application**            |   ✅   |           ✅           |         ✅         |       ❌       |      ❌      |
| **infrastructure**         |   ✅   |           ✅           |         ❌         |       ✅       |      ❌      |
| **presentation**           |   ✅   |           ✅           |         ✅         |       ✅       |      ✅      |

Key consequences:

- **Domain depends on nothing.** It can be copied into another project and its tests still pass.
- **Infrastructure never imports use cases or DTOs.** It implements ports. It doesn't call business logic.
  If an adapter seems to need a use case, the dependency points the wrong way. Usually that code belongs in `presentation/`.
- **Presentation is the only layer that knows every other layer exists.** It's the composition root.

### 1.2 Third-party libraries per layer

| Layer          | Allowed                                                             | Forbidden                                               |
|----------------|---------------------------------------------------------------------|---------------------------------------------------------|
| domain         | stdlib only (`dataclasses`, `decimal`, `enum`, `uuid`, `datetime`, `typing`) | everything else, **including pydantic**        |
| application    | stdlib, `domain`                                                     | FastAPI, SQLAlchemy, Kafka clients, pydantic, httpx     |
| infrastructure | SQLAlchemy, Kafka client, httpx, pydantic-settings, `overcalc_contracts`, `overcalc_platform` | FastAPI                  |
| presentation   | anything (FastAPI, pydantic, DI, `overcalc_contracts`, …)           | —                                                       |

Pydantic stays out of domain and application on purpose. Validation of *external input* is a presentation concern.
Invariants of the *model* are a domain concern and are enforced in plain Python.

---

## 2. Layer by layer

### 2.1 `domain/`

**Contains:** aggregates, entities, value objects, domain events, domain errors, domain services (rare).

Rules:

1. **No I/O, no async, no logging, no clock, no randomness.** Time and IDs are passed in as arguments,
   so domain tests are fully deterministic.
2. **Aggregates protect their invariants.** State changes go only through methods on the aggregate root.
   No public setters, and nothing outside the aggregate mutates its internals.
3. **Value objects are immutable** (`@dataclass(frozen=True, slots=True)`) and validate themselves in `__post_init__`.
   An invalid value object cannot exist.
4. **Aggregates record domain events.** They don't publish them. The aggregate appends to an internal list,
   and the application layer collects them with `pull_events()`.
5. **Domain events are past-tense facts** (`ExpressionParsed`, not `ParseExpression`), frozen dataclasses.
   They're **not** the Kafka contracts. Mapping to contracts happens in infrastructure.
6. **Domain errors subclass a single `DomainError`** per module and carry structured data (e.g. `position`),
   not just a message.
7. **Reference other aggregates by ID**, never by object.

```python
@dataclass(frozen=True, slots=True)
class Expression:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyExpression()
        if len(self.value) > MAX_EXPRESSION_LENGTH:
            raise ExpressionTooLong(len(self.value))


class Calculation:
    def __init__(self, id: CalculationId, expression: Expression, status: Status, ...) -> None: ...

    @classmethod
    def submit(cls, id: CalculationId, expression: Expression, now: datetime) -> "Calculation":
        calc = cls(id, expression, Status.REQUESTED, ...)
        calc._record(CalculationRequested(id, expression, occurred_at=now))
        return calc

    def complete(self, result: Result, now: datetime) -> None:
        if self.status.is_terminal:
            return  # idempotent: re-applying is a no-op
        ...
```

### 2.2 `application/`

**Contains:** use cases, commands/queries (input DTOs), result DTOs, application errors, and `interfaces/` (ports).

Rules:

1. **One use case = one class = one file**, named as a verb phrase (`SubmitExpression`), with a single
   `async def __call__(self, command) -> Result`.
2. **A use case is the transaction boundary.** It opens a Unit of Work, loads **one** aggregate,
   calls domain methods, saves the aggregate, and hands its events to the UoW/outbox, all in one commit.
   Changes to more than one aggregate in one transaction are forbidden. Use events and eventual consistency instead.
3. **Use cases orchestrate. They don't decide.** Branching on business rules belongs in the domain.
   If a use case has an `if` about calculation semantics, move it into the aggregate.
4. **Use cases return DTOs, never aggregates.** Callers must not be able to mutate domain objects.
5. **Ports live in `application/interfaces/`** as `typing.Protocol` (preferred) or `abc.ABC`.
   They're defined in terms of domain types and the application's needs, not the technology
   (`CalculationRepository.get(id)`, not `execute_sql(...)`).
6. **Clock and ID generation are ports too** (`Clock`, `IdGenerator`), so use cases stay testable.
7. **Errors a caller must react to** (`CalculationNotFound`, `ConcurrencyConflict`) are defined in
   `application/interfaces/errors.py`. Infrastructure raises these and doesn't leak driver exceptions.

```
application/
├── interfaces/
│   ├── repositories.py     # CalculationRepository(Protocol)
│   ├── unit_of_work.py     # UnitOfWork(Protocol)
│   ├── clock.py
│   └── errors.py
├── use_cases/
│   └── submit_expression.py
└── dto.py
```

### 2.3 `infrastructure/`

**Contains:** adapters that implement ports. DB tables and repositories, UoW, outbox writer,
Kafka producer, HTTP clients for external systems, settings.

Rules:

1. **Every public class here implements a port** from `application.interfaces`, or is a helper for one.
2. **Domain models are not ORM models.** Use SQLAlchemy imperative mapping or explicit mappers.
   Never add SQLAlchemy columns or decorators to domain classes.
3. **Translation lives here:** domain event ↔ `overcalc_contracts` model, DB row ↔ aggregate.
4. **Wrap technology errors** (`IntegrityError`, `KafkaError`) into port-level errors from
   `application.interfaces.errors`, or let them crash the process if they aren't recoverable.
5. **No business decisions.** A repository doesn't filter "completed calculations older than X".
   It runs the query the port defines, and the port defines it because the domain needs it.
6. **Settings** are `pydantic-settings` classes here, read from env. Domain and application never read env.

### 2.4 `presentation/`

**Contains:** FastAPI routers and request/response schemas, Kafka subscribers, cron/background jobs,
CLI commands, and the composition root (`container.py`, `main.py`).

Rules:

1. **Thin.** Every entry point does: parse/validate input → build command → call use case → map output.
   About ten lines is normal. A long handler means logic is in the wrong layer.
2. **Request/response schemas are pydantic models** in `presentation/api/schemas.py`. They're the
   public contract and are deliberately separate from DTOs, so the API can evolve independently.
3. **Error mapping happens here and only here:** `DomainError` / application errors → RFC 9457 problem details
   (HTTP) or ack/retry/DLQ decision (Kafka).
4. **Subscribers** deserialize an `overcalc_contracts` event, check idempotency (inbox), map to a command,
   call the use case, and commit the offset. They never touch repositories directly.
5. **Wiring** (which adapter implements which port) lives only in `container.py`.
   No other module instantiates infrastructure classes.

---

## 3. Boundaries between modules and services

| From                           | May import                                   | Must not import                    |
|--------------------------------|----------------------------------------------|------------------------------------|
| a module inside a service      | its own layers                               | another module's layers            |
| a service                      | `overcalc_contracts`, `overcalc_platform`    | any other service's package        |
| `overcalc_contracts`           | pydantic, stdlib                             | any service, `overcalc_platform`   |
| `overcalc_platform`            | infra libs (SQLAlchemy, Kafka, OTel)         | any service, any domain concept    |

- **Modules (in the M1 modular monolith) communicate only through events** on an in-process bus,
  the same events that later go to Kafka. No direct calls into another module's use cases.
- **`overcalc_contracts` is used only in infrastructure and presentation.** Domain and application
  never see wire formats.
- **`overcalc_platform` is technical plumbing only.** If you're tempted to put a domain type in it, stop.
  That's how a distributed monolith starts.

---

## 4. Naming conventions

| Thing               | Convention                         | Example                          |
|---------------------|------------------------------------|----------------------------------|
| Aggregate           | noun                               | `Calculation`                    |
| Value object        | noun                               | `Expression`, `CalculationId`    |
| Domain event        | past-tense verb phrase             | `ExpressionEvaluated`            |
| Domain error        | what went wrong                    | `DivisionByZero`                 |
| Use case            | imperative verb phrase             | `SubmitExpression`               |
| Command / Query     | `<UseCase>Command` / `...Query`    | `SubmitExpressionCommand`        |
| Port                | role, no tech                      | `CalculationRepository`          |
| Adapter             | tech + role                        | `SqlAlchemyCalculationRepository`|
| Fake (tests)        | `InMemory` / `Fake` + role         | `InMemoryCalculationRepository`  |
| Kafka topic         | `<context>.events.v<N>`            | `parsing.events.v1`              |

---

## 5. Testing per layer

| Layer          | Test type     | Uses                                   | Must not use              |
|----------------|---------------|----------------------------------------|---------------------------|
| domain         | unit          | plain pytest, hypothesis               | mocks, fixtures with I/O  |
| application    | unit          | in-memory fakes of ports (`tests/fakes.py`) | `unittest.mock` for ports, real DB |
| infrastructure | integration   | Testcontainers (Postgres, Kafka)       | fakes of the thing under test |
| presentation   | API/component | httpx `AsyncClient`, fake use cases or full container | — |

- **Prefer fakes over mocks.** A fake is a real, simple implementation of a port, and it's reused across tests.
  Mocks couple tests to call sequences.
- Every port has **one fake** and **one contract test suite** that runs against both the fake and the real adapter.
  That keeps the fake honest.
- TDD: a failing test lands before (or in the same commit as) the code that makes it pass.

---

## 6. Enforcement

Rules nobody checks get broken. These are enforced in CI:

- **`import-linter`** (`.importlinter`) runs a contract set for every service, with these contracts:

```ini
[importlinter]
root_packages =
    overcalc_calculation
include_external_packages = True
contract_types =
    stdlib_only: tools.importlinter_contracts.stdlib_only.StdlibOnlyContract

[importlinter:contract:calculation-layers]
name = calculation: layered architecture
type = layers
layers =
    overcalc_calculation.presentation
    overcalc_calculation.infrastructure
    overcalc_calculation.application
    overcalc_calculation.domain

[importlinter:contract:calculation-infra-only-ports]
name = calculation: infrastructure only sees application.interfaces
type = forbidden
source_modules =
    overcalc_calculation.infrastructure
forbidden_modules =
    overcalc_calculation.application
# `pkg.**` doesn't match `pkg` itself, so each side lists the package and its descendants.
ignore_imports =
    overcalc_calculation.infrastructure -> overcalc_calculation.application.interfaces
    overcalc_calculation.infrastructure -> overcalc_calculation.application.interfaces.**
    overcalc_calculation.infrastructure.** -> overcalc_calculation.application.interfaces
    overcalc_calculation.infrastructure.** -> overcalc_calculation.application.interfaces.**
# Not every ignore line has a matching import at any given time (on main none do yet),
# and that is fine: they describe what is allowed, not what exists.
unmatched_ignore_imports_alerting = none

[importlinter:contract:calculation-pure-domain]
name = calculation: domain is pure
type = forbidden
source_modules =
    overcalc_calculation.domain
    overcalc_calculation.application
forbidden_modules =
    pydantic
    sqlalchemy
    fastapi
    aiokafka
    httpx
    overcalc_contracts
    overcalc_platform

[importlinter:contract:calculation-domain-stdlib-only]
name = calculation: domain imports only the stdlib
type = stdlib_only
source_modules =
    overcalc_calculation.domain
allowed_modules =
    overcalc_calculation.domain

[importlinter:contract:calculation-infra-no-web]
name = calculation: infrastructure has no web framework
type = forbidden
source_modules =
    overcalc_calculation.infrastructure
forbidden_modules =
    fastapi
```

  (Repeat per service. Once there are several, a small script generates the file.)
  `stdlib_only` is a custom contract type (`tools/importlinter_contracts/`): built-in `forbidden`
  can only deny named packages, so "stdlib only" (§1.2) needs an allowlist. `tests/architecture/`
  checks each contract against deliberate violations and keeps the block above identical to `.importlinter`.
- **`ruff`** with `flake8-tidy-imports` to ban relative imports beyond the same package.
- **`mypy --strict`** so ports and adapters can't drift silently.

---

## 7. Changing these rules

These rules are deliberately strict, and they can change. To change one:

1. Write an ADR explaining what you're changing and why.
2. Update this file and `.importlinter` in the same PR.
3. Don't add an exception "just for this one file". If it's justified once, it's a rule change.
