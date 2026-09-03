# Python Backend Design — Checklist

Detailed reference for `python-backend-design`. Consult when implementing,
restructuring, or reviewing a Python backend. Grouped by concern.

## 1. Architecture & project structure

- Use a `src/` layout so imports are `from app...` and tests import the installed
  package:

  ```
  backend/
    src/app/
      main.py            # app factory, router registration, lifespan
      config.py          # pydantic-settings BaseSettings
      db.py              # engine + session factory
      api/               # HTTP layer: routers, Pydantic schemas, deps
      domain/            # entities, value objects, ports (Protocols)
      services/          # use-case orchestration, unit of work
      infrastructure/    # SQLAlchemy models, repositories, clients
    tests/
    alembic/             # or per-app migrations/ for Django
    pyproject.toml
  ```

- **Layer direction**: API → services → ports → repositories. Dependencies point
  inward; the domain never imports SQLAlchemy, FastAPI, or Django.
- **FastAPI**: use the dependency-injection system as the composition root —
  inject `Session`, repositories, and config into routes as dependencies.
- **Django**: keep business rules in `services.py`, not fat models or view
  functions; use apps (`models.py`/`views.py`/`forms.py`) for structure.
- **Flask**: use the application-factory pattern (`create_app(config)`) for
  testable config and to avoid import-time side effects.

## 2. API design

1. Design resources, not verbs: `GET /orders/{id}`, not `GET /getOrder`.
2. Plural nouns for collections; nest sub-resources sparingly
   (`/orders/{id}/items`).
3. Pick one versioning strategy and apply it consistently — URL path
   (`/v1/orders`) or header; never mix schemes.
4. HTTP semantics: `GET` safe/idempotent, `POST` create, `PUT` full replace
   (idempotent), `PATCH` partial, `DELETE` idempotent. Never mutate in `GET`.
5. Precise status codes: `200/201/202/204` success; `400`/`422` validation;
   `401` unauthenticated; `403` forbidden; `404` not found; `409` conflict;
   `429` rate-limited; `5xx` server fault.
6. Make mutations idempotent with an `Idempotency-Key` header; store the keyed
   response and return it on retries.
7. Paginate all list endpoints (`limit`/`offset` or cursor); return a stable
   envelope with `next_page_token` and `total` only when cheap.
8. Support filtering/sorting via query params (`?status=open&sort=-created_at`);
   validate all query inputs against a schema.
9. One consistent error envelope — RFC 7807 `application/problem+json`
   (`type`, `title`, `status`, `detail`, `instance`).
10. Define every request/response as a Pydantic model and set `response_model` on
    FastAPI routes. Reject unknown fields in strict mode at trust boundaries.

## 3. Data & persistence

- **ORM**: SQLAlchemy 2.0 style (`DeclarativeBase`, `Mapped[...]`, `select()`);
  Django ORM with `select_related`/`prefetch_related`. Treat the ORM as the
  access layer; never leak it into domain entities.
- **Pooling**: configure a pool (`pool_size`, `max_overflow`); async uses
  `NullPool`/`AsyncAdaptedQueuePool` with asyncpg. Pool size matches concurrency,
  not request count.
- **Session lifecycle**: one `Session` per request (FastAPI dependency `yield`),
  opened late, closed in `finally`; never shared across threads/tasks.
- **Migrations**: commit Alembic (autogenerate then review) or Django migrations
  for every schema change; never edit applied migrations; make them reversible
  and test upgrade + downgrade.
- **Transactions / unit of work**: wrap a logical operation in one transaction
  (`session.begin()`; Django `transaction.atomic()`/`ATOMIC_REQUESTS`); commit
  once at the boundary, roll back on any exception.
- **Indexes**: index every column used in `WHERE`, `JOIN`, `ORDER BY`; verify
  with `EXPLAIN`. Avoid low-cardinality columns unless selectivity warrants it.
- **Config/secrets**: load config from env with `pydantic-settings`
  (`BaseSettings`, `SettingsConfigDict(env_file=".env")`); never hardcode
  secrets. Use a secret manager (Vault/cloud KMS) in production, not `.env`.

## 4. Async & concurrency

- Async pays off for I/O-bound work with many concurrent waits (DB, HTTP, files).
- Declare FastAPI endpoints `async def` only when the whole path is non-blocking;
  `def` endpoints run in a threadpool (correct for sync SQLAlchemy).
- Never block the event loop: no sync DB calls, `requests`, `time.sleep`, or
  CPU-heavy work inside `async def`. Offload CPU-bound work to
  `run_in_executor` or a queue.
- Background jobs: `BackgroundTasks` only for trivial in-process work; use
  Celery/RQ/arq for durable, retriable jobs. Persist the job before enqueueing.
- Idempotent workers: re-running with the same input must be safe — dedupe by job
  key, use DB uniqueness constraints, at-least-once with idempotency keys at the
  receiver for side effects (email, webhook, charge).
- One concurrency model per tier; don't mix sync and async engines on one pool.

## 5. Reliability & operations

- **12-factor config**: config in the environment, separate from code; stateless
  processes so any instance serves any request.
- **Structured logging**: JSON logs (request id, method, path, status, latency,
  trace id) via `structlog`; log once at the boundary; never secrets/PII.
- **Observability**: Prometheus `/metrics` (rate, latency percentiles, error
  rate, queue depth, pool usage); propagate trace context (OpenTelemetry) across
  HTTP/DB/queue boundaries.
- **Health**: `/health/live` (process up) and `/health/ready` (checks DB,
  migrations, dependencies); map to Kubernetes probes; fail readiness, not
  liveness, on degraded dependencies.
- **Graceful shutdown**: on `SIGTERM` stop accepting requests, drain in-flight
  work, close DB pools/connections (FastAPI/uvicorn lifespan; Gunicorn
  `--graceful-timeout`).
- **Timeouts & retries**: explicit timeouts on every outbound call
  (`httpx.Timeout`, `asyncio.wait_for`); retry only idempotent requests with
  exponential backoff + jitter and a max-attempt cap.
- **Rate limiting**: enforce at the edge/gateway or via middleware keyed by
  client/IP/API key; return `429` with `Retry-After`.
- **Containerization**: slim non-root images, multi-stage builds, health checks,
  entrypoint runs migrations before the server; pin dependencies with hashes.

## 6. Testing

- **Unit** (`pytest`): domain logic and services in isolation; mock only at
  external boundaries (HTTP clients, third-party SDKs, clock), never your own
  internals.
- **Integration**: run against a real Postgres (Testcontainers or dedicated CI
  instance) when behavior depends on the dialect; create/drop schema per run.
  Django: test runner + `pytest-django --reuse-db`. SQLAlchemy: Alembic to
  latest then truncate between tests.
- **HTTP**: FastAPI `TestClient` (or `httpx.AsyncClient` with `ASGITransport`);
  use `dependency_overrides` to swap repositories/services for fakes. Django
  test `Client`; Flask `app.test_client()`.
- **Failure paths**: validation (400/422), auth (401/403), not-found (404),
  conflict (409), DB outage (500 → clean error), timeout/retry exhaustion, and
  idempotent retry returning the same result.
- **Contract**: assert or snapshot the generated OpenAPI schema so response-model
  changes are caught.
- **Coverage**: high branch coverage on domain/services (`pytest-cov`); don't
  chase 100% mechanically.

## 7. Anti-patterns

- Fat models / fat views (business logic crammed into ORM models or handlers).
- N+1 queries in loops — use `selectinload`/`joinedload` (SQLAlchemy) or
  `select_related`/`prefetch_related` (Django); assert query counts in tests.
- Blocking code in async paths — freezes the event loop.
- One global shared session/connection across requests/threads.
- No transactions (partial writes on failure); wrap every unit of work.
- Hardcoded secrets/config or committing `.env`.
- Unpinned/undeclared dependencies, no lockfile.
- Migration drift (editing the DB by hand, skipping migrations).
- Swallowing exceptions or logging without context; generic 500s without a
  structured error contract.
- Missing timeouts/retries on outbound calls.
- No idempotency on mutating endpoints (duplicate charges/webhooks on retry).
- Premature microservice/hexagonal complexity for a small CRUD app.
- `except Exception: pass` and broad retry loops that hide bugs.

## Sources

- FastAPI: [Concurrency](https://fastapi.tiangolo.com/async/), [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/), [Response Model](https://fastapi.tiangolo.com/tutorial/response-model/), [Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
- [Flask application factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)
- [The Twelve-Factor App — Config](https://12factor.net/config)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)
- [Google AIP-158 — Pagination](https://google.aip.dev/158)
- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [Connection Pooling](https://docs.sqlalchemy.org/en/21/core/pooling.html)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [RFC 7807 — Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807)
- [Kubernetes liveness/readiness probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
