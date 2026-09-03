---
name: python-hexagonal-architecture
description: Implement Hexagonal Architecture (Ports and Adapters) in Python — a framework-agnostic domain core, ports defined as typing.Protocol/ABC, and driving (web/CLI) plus driven (database/HTTP client) adapters wired at a composition root. Use when designing a new Python service/domain, refactoring toward testability, or separating business rules from FastAPI/Django/SQLAlchemy.
license: MIT
compatibility: "Agent Skills standard (SKILL.md). Works with OpenCode, Pi, Zed, Copilot, and DeepSeek Harness. Targets Python 3.10+."
metadata:
  author: DarkSiteX
  version: "1.0"
  language: python
  topics: hexagonal-architecture, ports-and-adapters, ddd, clean-architecture, dependency-injection
---

# Hexagonal Architecture in Python

## Overview

Hexagonal Architecture (Ports and Adapters) isolates the domain — the business
rules — from everything external. The core defines **ports** (interfaces for
inbound and outbound operations) and depends on nothing framework-specific;
**adapters** (web frameworks, databases, HTTP clients, message brokers) plug into
those ports. Dependencies always point inward: adapters → application → domain.

In Python this is expressed with `typing.Protocol` (or `abc.ABC`) for ports,
dataclasses/Pydantic for entities and value objects, and a **composition root**
that injects concrete adapters — often FastAPI's dependency-injection system or a
`bootstrap.py`.

## When to Use

Use this skill when you are:

- designing a new Python domain/service that should outlive a framework choice;
- refactoring a codebase where business rules are tangled with FastAPI/Django/SQLAlchemy;
- making a domain unit-testable without a database or web server;
- introducing a second adapter (a different DB, a CLI, a message queue) and
  wanting to swap it without touching business logic.

Do not over-apply it: a small CRUD app may only need layered modules. See the
anti-patterns in `references/checklist.md`.

## Core Principles

1. **Dependency rule** — the domain imports nothing from the outside; ports are
   defined in the domain/application layer and implemented by adapters.
2. **Ports as interfaces** — use `typing.Protocol` (preferred, structural
   subtyping) or `abc.ABC`; keep them small and driven by the domain's needs.
3. **Framework-agnostic core** — no FastAPI, Django, SQLAlchemy, or ORM models in
   the domain; persistence happens behind repository ports.
4. **Composition root** — one place wires real adapters to ports (DI container,
   `bootstrap.py`, or FastAPI dependencies); the domain never self-wires.
5. **Test through ports** — unit-test the domain with in-memory fakes; use real
   adapters only in integration tests.

## Quick Start

1. Lay out `domain/`, `application/`, and `adapters/` packages under `src/`.
2. Define ports as `Protocol`s (e.g. `OrderRepository`, `PaymentGateway`).
3. Put use-cases in `application/` that call ports; keep entities pure.
4. Implement adapters (SQLAlchemy repo, HTTP client, FastAPI router) against the ports.
5. Wire everything in a composition root and test the domain with fakes.

## Navigation

- **`references/checklist.md`** — the full reference: recommended `src/` layout,
  the twelve numbered best practices with code snippets, anti-patterns, and
  tooling/testing guidance. Load when actually implementing or refactoring.

## Key Reminders

- Keep the domain free of ORM models, web frameworks, and I/O.
- Prefer `Protocol` over `ABC` for ports; let adapters satisfy the protocol structurally.
- Never import a concrete adapter in the domain/application layer.
- Match the pattern to the problem — don't hexagon a script.
