---
name: python-backend-design
description: Best-practice guidance for designing Python backends with FastAPI, Django, or Flask — project layout, REST API design, persistence, async/await, reliability, and testing. Use when creating, restructuring, or reviewing a Python backend, API, or web service.
license: MIT
compatibility: "Agent Skills standard (SKILL.md). Works with OpenCode, Pi, Zed, Copilot, and DeepSeek Harness. Targets Python 3.10+ with FastAPI/Django/Flask, SQLAlchemy, pydantic."
metadata:
  author: DarkSiteX
  version: "1.0"
  language: python
  topics: api, fastapi, django, flask, sqlalchemy, async, reliability, testing
---

# Python Backend Design

## Overview

Design clean, testable, production-ready Python backends. The goal is a layered
architecture where HTTP, domain, and persistence concerns are separated, every
external boundary is validated with Pydantic, and operations are reliable under
concurrency and failure. Applies to FastAPI, Django, and Flask.

## When to Use

Use this skill when you are:

- creating a new Python API/service or scaffolding a backend project;
- restructuring an existing backend (fat models/views, missing layers, N+1 queries);
- adding endpoints, persistence, background jobs, or async paths;
- reviewing backend code for correctness, reliability, or test coverage.

Do not use it for pure frontend/UI work (see `python-frontend-design`) or for
domain-modelling isolation (see `python-hexagonal-architecture`).

## Core Principles

1. **Layered by dependency direction** — HTTP layer depends on services, which
   depend on ports (interfaces); the domain never imports FastAPI, Django, or
   SQLAlchemy. Use a `src/` layout (`app/api`, `app/domain`, `app/services`,
   `app/infrastructure`).
2. **Contracts at the boundary** — every request/response is a Pydantic model;
   set `response_model` on FastAPI routes so validation, serialization, and the
   OpenAPI schema come from one source of truth.
3. **Correct HTTP semantics** — resources and verbs, precise status codes, a
   consistent RFC 7807 error envelope, pagination, and idempotency on mutations.
4. **One transaction per operation, one session per request** — commit once at
   the boundary, roll back on error; never share sessions across requests/threads.
5. **Fail safely and observably** — structured JSON logs, timeouts + bounded
   retries on outbound calls, liveness/readiness endpoints, graceful shutdown,
   and config from the environment (12-factor), never hardcoded secrets.

## Quick Start

1. Choose the framework and scaffold a `src/` layout with an app factory.
2. Define domain/use-case services against `Protocol` ports; implement ports in
   `infrastructure/` (repositories, clients).
3. Expose routes that declare Pydantic request/response models and inject
   `Session`/config/repositories as FastAPI dependencies (composition root).
4. Add Alembic/Django migrations, environment config via `pydantic-settings`,
   and one `Session` per request.
5. Test at three levels: unit (domain/services), integration (real/test DB), and
   HTTP (`TestClient`/`httpx.ASGITransport`), including failure paths.

## Navigation

- **`references/checklist.md`** — the full numbered best-practices checklist
  (architecture, API design, persistence, async, reliability, testing) plus
  anti-patterns. Load when actually implementing or reviewing backend code.

## Key Reminders

- `async def` only when the whole call path is non-blocking; a `def` FastAPI
  endpoint runs in a threadpool and is correct for sync SQLAlchemy.
- Never call blocking code (sync DB, `requests`, `time.sleep`, CPU-heavy work)
  inside `async def`.
- Retry only idempotent requests, with exponential backoff + jitter and a cap.
- Log at the boundary once, structured, and never log secrets or PII.
- Match complexity to the problem: a small CRUD app needs an app factory and
  layers, not a full ports-and-adapters hexagon.
