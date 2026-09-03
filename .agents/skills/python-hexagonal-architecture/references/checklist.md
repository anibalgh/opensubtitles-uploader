# Hexagonal Architecture (Ports & Adapters) in Python

## 1. Core concepts

**Definition.** Hexagonal Architecture (a.k.a. *Ports & Adapters*) isolates an application's **core** — the domain model plus the application (use-case) logic that encodes business rules — behind a boundary. Everything outside (UI, HTTP, CLI, tests, databases, message brokers, email, cloud APIs) reaches the core, or is reached by it, only through **ports**, each of which is implemented by one or more **adapters**. Cockburn's stated motivation: "allow an application to equally be driven by users, programs, automated test or batch scripts, and to be developed and tested in isolation from its eventual run-time devices and databases" ([Cockburn](https://alistair.cockburn.us/hexagonal-architecture)).

- **Domain/application core**: pure business logic with **no imports from web frameworks, ORMs, or I/O**. Entities, value objects, domain services, and use-case orchestration live here.
- **Driving (primary) adapters / "ports in"**: call *into* the core (REST controller, CLI, test suite, event consumer). They translate external input into commands/DTOs and hand them to an application service.
- **Driven (secondary) adapters / "ports out"**: the core calls *out* through them (repository, message publisher, email gateway). The core depends on the **interface**, never the concrete adapter.
- **Dependency rule**: source-code dependencies point **inward only**. The core imports port interfaces (and nothing else from the outer layers); adapters import the core. This is the Dependency Inversion Principle applied at the architecture level ([AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html), [Percival & Gregory](https://www.cosmicpython.com/book/chapter_02_repository)).
- **Ports are interfaces**: in Python, ports are `typing.Protocol` or `abc.ABC` classes owned by the core (placed in `application/` or `domain/`). "Ports in" can also be plain callables or command-handler functions — Python doesn't need a class for a driving port.

**Python mapping.**

- **`typing.Protocol`** (structural subtyping) is the idiomatic choice for ports: an adapter satisfies a port by shape, no inheritance required — true duck typing with static checking.
- **`abc.ABC` + `@abstractmethod`** when you want nominal typing (explicit registration/inheritance) or runtime enforcement via `__subclasshook__`/`NotImplementedError`.
- **`@dataclass` / `@dataclass(frozen=True)`** for entities, value objects, commands, and DTOs; `frozen=True` gives value-object immutability for free.
- **`typing`** (`Protocol`, `TypeVar`, `Generic`, `Final`, `NewType`) expresses ports and generic repositories without runtime cost.
- **Dependency injection** is done at a **composition root** (`bootstrap.py`), usually by hand or with a small container; the core never constructs its own adapters.
- The "hexagon" maps naturally to the **Repository + Unit of Work** patterns from *Architecture Patterns with Python*: repositories are driven ports whose adapters hide SQLAlchemy/Django ORM, and the Unit of Work coordinates transactions ([Percival & Gregory](https://www.cosmicpython.com/book/chapter_02_repository)).

## 2. Recommended project layout

Use a `src/` layout so the package is importable only after install and imports stay explicit:

```
src/myapp/
  domain/                # pure business logic — NO framework/ORM/I-O imports
    model.py             # entities, value objects, domain events
    services.py          # domain services (multi-entity invariants)
  application/           # use cases + ports (the "service layer")
    ports.py             # Protocol/ABC ports (repositories, uow, publishers)
    services.py          # application services / command handlers
    dtos.py              # commands, queries, and response DTOs
    events.py            # integration event schemas
  adapters/              # everything that touches the outside world
    web/                 # FastAPI/Flask/Django routes, Pydantic schemas (driving)
    repositories/        # SQLAlchemy/Django ORM impls of repository ports (driven)
    messagebus/          # Redis/RabbitMQ/Kafka, email, external HTTP clients (driven)
    cli/                 # argparse/typer commands (driving)
  bootstrap.py           # composition root: build sessions, wire adapters to ports
  config.py              # env/settings; only place that reads config eagerly
tests/
  unit/                  # domain + application (fast, in-memory fakes)
  integration/           # adapters against real DB/broker
  e2e/                   # full app through driving adapters
pyproject.toml
```

**What goes where.** `domain/` knows nothing about persistence or transport. `application/` defines *what the system does* (use cases) and *what it needs* (ports) but not *how*. `adapters/` implements *how*. `bootstrap.py` is the only module allowed to import concrete adapters and the core together, and the only place adapters get constructed. This mirrors Cosmic Python's `domain / service_layer / adapters` split ([Percival & Gregory](https://www.cosmicpython.com/book/chapter_02_repository)).

## 3. Concrete best practices

1. **Keep the domain pure and framework-agnostic.** `domain/` imports only `stdlib`, `typing`, and `dataclasses`. No `sqlalchemy`, no `fastapi`, no `requests`, no ORM base classes.
2. **Model entities and value objects with `dataclasses`; freeze value objects.**

   ```python
   # domain/model.py
   from dataclasses import dataclass

   @dataclass(frozen=True)
   class Money:
       amount: int
       currency: str

   @dataclass
   class Order:
       id: str
       sku: str
       qty: int
   ```

3. **Declare driven ports as `typing.Protocol` (or `abc.ABC`) in `application/ports.py`, owned by the core.**

   ```python
   # application/ports.py
   from typing import Protocol
   from myapp.domain.model import Order

   class OrderRepository(Protocol):
       def add(self, order: Order) -> None: ...
       def get(self, order_id: str) -> Order | None: ...
       def list_for(self, sku: str) -> list[Order]: ...
   ```

4. **Depend on the port, not the adapter.** Application services accept the `Protocol` as a parameter; they never import or instantiate a concrete repository.
5. **Put a Unit of Work port around multi-entity transactions.**

   ```python
   class UnitOfWork(Protocol):
       orders: OrderRepository
       def __enter__(self) -> "UnitOfWork": ...
       def __exit__(self, *args) -> None: ...
       def commit(self) -> None: ...
       def rollback(self) -> None: ...
   ```

6. **Use DTOs (commands/queries) at the boundary.** Driving adapters translate raw HTTP/CLI input into typed command objects before calling the core.

   ```python
   # application/dtos.py
   from dataclasses import dataclass

   @dataclass(frozen=True)
   class AllocateCommand:
       order_id: str
       sku: str
       qty: int
   ```

7. **Implement the repository pattern for persistence.** The SQLAlchemy adapter implements the `Protocol`; the domain never sees a `Session`.

   ```python
   # adapters/repositories/sqlalchemy_repo.py
   from sqlalchemy.orm import Session
   from myapp.domain.model import Order

   class SqlAlchemyOrderRepository:
       def __init__(self, session: Session) -> None:
           self._session = session
       def add(self, order: Order) -> None: self._session.add(order)
       def get(self, order_id: str) -> Order | None:
           return self._session.get(Order, order_id)
       def list_for(self, sku: str) -> list[Order]:
           return self._session.query(Order).filter_by(sku=sku).all()
   ```

8. **Wire everything at a single composition root** (`bootstrap.py`). This is the only place concrete adapters are constructed and passed to the core.

   ```python
   # bootstrap.py
   def bootstrap() -> FastAPI:
       session_factory = create_engine_and_factory()
       repo = SqlAlchemyOrderRepository(session_factory)
       app = FastAPI()
       app.state.allocate = lambda cmd: allocate(cmd, repo)  # or a MessageBus
       return app
   ```

9. **Keep Django/FastAPI/SQLAlchemy out of the domain and application layers.** Web code lives in `adapters/web/`, ORM mappings in `adapters/repositories/`. The core tests run with zero frameworks.
10. **Prefer `Protocol` over `ABC`** when adapters should satisfy the port structurally (e.g., a third-party client you can't subclass); prefer `ABC` when you want explicit contract inheritance. Don't use `Protocol` with `@runtime_checkable` unless you actually call `isinstance`.
11. **Keep ports narrow and stable** (one responsibility per port; e.g., `OrderRepository` vs. `EventPublisher`), so adapters stay swappable and fakes stay small.
12. **Push side effects to the edges.** The core returns values/events; adapters perform I/O. A use case should be a pure function of (command, ports) → (result, events).

## 4. Anti-patterns / pitfalls

- **ORM/base-class leakage**: importing `Base` or `models.Model` into `domain/`, or decorating domain entities with SQLAlchemy `Column`s. Use separate mapping classes or SQLAlchemy 2.0 `Mapped` on adapter-side tables.
- **Framework in the service layer**: `HTTPException`, `Request`, `Session`, or decorators like `@app.get` inside `application/`. Frameworks change; the core shouldn't.
- **Direct DB/network calls in the core** instead of going through a port.
- **"Hexagon with holes"**: ports that expose infrastructure types (e.g., a repository protocol returning SQLAlchemy objects), or commands carrying ORM models.
- **Constructor self-wiring**: core objects doing `repository = SqlAlchemyRepository(...)` themselves — this inverts the dependency rule and kills testability. Build at the composition root.
- **Over-abstracting**: one port + one adapter + zero tests + an interface-per-class explosion. If it isn't actually swappable or fakeable, a `Protocol` is ceremony. Avoid dozens of one-method protocols that mirror a framework's API.
- **Anemic domain**: putting all logic in `services.py` with empty entities. Keep invariants in the domain; the service layer *orchestrates* ([Percival & Gregory](https://www.cosmicpython.com/book/chapter_02_repository)).
- **Faking the wrong layer in tests**: unit-testing the adapter against mocks of the ORM, but integration-testing only happy paths. Test the domain with plain objects and the adapters against real DBs/brokers.
- **`mypy` silencing**: `# type: ignore` on ports/adapters to "make it pass" — you lose the static check that adapters really satisfy ports.
- **Circular imports** between `domain`, `application`, and `adapters` — enforce one-directional imports with a linter (e.g., `import-linter`).

## 5. Tooling & testing guidance

- **pytest** for everything. Structure: `tests/unit` (domain + application with in-memory fakes implementing the ports — instant, no I/O), `tests/integration` (real DB/broker adapters, rolled back per test), `tests/e2e` (drive the app through FastAPI's `TestClient`/CLI).
- **In-memory fakes** are first-class: a `FakeOrderRepository(dict)` implements the same `Protocol` and is the primary test double for the core. This is exactly Cockburn's "test adapters" and Eric Gunnerson's "simulators" idea ([Gunnerson, Microsoft](https://learn.microsoft.com/en-gb/archive/blogs/ericgu/unit-test-success-using-ports-adapters-and-simulators)).
- **mypy** (`strict` where feasible) verifies adapters conform to `Protocol` ports and that `domain/` has no forbidden imports. Add a `mypy` config disallowing `# type: ignore` in the core.
- **Dependency injection**: prefer **manual wiring** at the composition root (explicit, debuggable) or a tiny container. When you need one, consider **`dependency-injector`** (full-featured, providers) or **`punq`** (tiny, runtime introspection). Avoid containers that require the core to import them.
- **import-linter** to enforce the dependency rule as CI (contract: `domain` → nothing; `application` → `domain`; `adapters` → `application`/`domain`).
- **Ruff/Black/isort** for consistent, idiomatic formatting; **pytest-cov** to keep the domain's branch coverage high (it should be near-total since it's pure).
- **Test the wiring itself**: an e2e test that calls `bootstrap()` and exercises one use case end-to-end catches composition-root mistakes early.
- Use **`TestClient` (FastAPI) / Django test client** in e2e, and **`freezegun`/`time-machine`** or injected clock ports for time-dependent core logic.

## 6. Sources

- [Alistair Cockburn — Hexagonal Architecture (Ports & Adapters)](https://alistair.cockburn.us/hexagonal-architecture) — the canonical original definition of the pattern, ports/adapters, driving vs. driven sides, and its motivation. *The* primary source.
- [Architecture Patterns with Python — Harry Percival & Bob Gregory (cosmicpython.com), Chapter 2: Repository](https://www.cosmicpython.com/book/chapter_02_repository) — the authoritative Python-specific treatment; repository/UoW, dependency inversion, and the `domain / service_layer / adapters` structure used throughout this doc. (See also the book's [Chapter 10: Dependency Injection](https://www.cosmicpython.com/book/chapter_10_dependency_injection).)
- [AWS Prescriptive Guidance — Hexagonal architecture pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html) — vendor-neutral, practitioner-grade description of ports, adapters, and the dependency rule from Amazon's architecture guidance docs.
- [Eric Gunnerson, Microsoft — "Unit Test Success using Ports, Adapters, and Simulators"](https://learn.microsoft.com/en-gb/archive/blogs/ericgu/unit-test-success-using-ports-adapters-and-simulators) — engineering-blog proof that ports/adapters make systems testable via simulators; underpins the fake-adapter testing guidance.
- [DEV Community (elpic) — "Hexagonal Architecture in Python: Wiring Adapters, Dependency Injection, and the Application Layer"](https://dev.to/elpic/hexagonal-architecture-in-python-wiring-adapters-dependency-injection-and-the-application-layer-61l) — a current, Python-specific walkthrough of wiring adapters and DI in FastAPI, used to ground the composition-root and adapter snippets.
- [Manning liveBook — *Microservice APIs* (Python/Flask/FastAPI), Ch. 7: Service implementation patterns](https://livebook.manning.com/book/microservice-apis/chapter-7) — a published book chapter on hexagonal service layout for Python web services; corroborates the recommended folder structure.

*Note on prioritization:* Cockburn and Cosmic Python surfaced directly and anchor the document. Netflix TechBlog and 8th Light did not return a dedicated Python hexagonal post in the search results, so I substituted AWS Prescriptive Guidance and a Microsoft engineering blog for institutional weight, plus Python-specific engineering-blog coverage.
