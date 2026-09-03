---
name: python-security
description: Secure Python development guidance. Use when writing, reviewing, or modifying security-sensitive Python code — authn/authz, input validation, SQL/ORM queries, template rendering, subprocess, file paths, deserialization, XML, secrets, cryptography/TLS, JWT/sessions, CORS/CSRF, headers, logging, dependencies, and CI security tooling. Maps OWASP Top 10 and CWE Top 25 to Python risks.
license: MIT
compatibility: "Agent Skills standard (SKILL.md). Works with OpenCode, Pi, Zed, Copilot, and DeepSeek Harness. Targets Python 3.9+ (Django/Flask/FastAPI, CLI tools, libraries)."
metadata:
  author: DarkSiteX
  version: "1.0"
  language: python
  topics: security, owasp, cwe, cryptography, supply-chain, sast, secrets
---

# Python Application Security

## Overview

Write and review Python that is secure by default. Map OWASP Top 10 and CWE
Top 25 risks to their Python manifestations (SQL injection, XSS, insecure
deserialization via `pickle`, SSRF, path traversal, broken access control,
cryptographic misuse, hardcoded secrets) and enforce mitigations at trust
boundaries. Applies to web apps (Django, Flask, FastAPI), CLI tools, and
libraries.

## When to Use

Use this skill when you are:

- writing or modifying code that touches untrusted input (request params,
  headers, files, env, user-supplied data);
- implementing authentication/authorization, sessions, JWTs, or cryptography;
- rendering templates, running subprocesses, reading/writing files, or
  deserializing data;
- managing secrets, dependencies, or CI/CD security gates;
- reviewing any Python code for security before merge.

Also load it alongside `python-backend-design` for API security (CORS, rate
limiting, headers) and `python-frontend-design` for XSS/CSP in templates.

## Core Principles

1. **Never trust input** — validate and normalize everything at the boundary;
   whitelist over blacklist; use schema libraries (Pydantic) and type hints.
2. **Parameterize, never interpolate** — bound SQL parameters, argv lists for
   subprocess (no `shell=True`), and autoescaped templates (no raw `|safe`).
3. **Never deserialize untrusted data with `pickle`** — use JSON, `yaml.safe_load`,
   schema validation, or `defusedxml`.
4. **Secrets stay secret** — env vars or a secret manager, never committed;
   strong primitives (`argon2`/`bcrypt`, `secrets`, modern TLS, no `verify=False`).
5. **Least privilege + defense in depth** — per-object authorization, pinned
   CORS/CSRF, rate limiting, security headers.
6. **Automate security** — pin dependencies + audit (pip-audit), run SAST
   (Bandit/Semgrep) and secrets scanning in pre-commit/CI.

## Quick Start

1. Identify the trust boundary and enumerate every untrusted input.
2. Apply the 14-point checklist in `references/checklist.md` to new/changed code.
3. Add Bandit + pip-audit + secrets scanning to pre-commit and CI.
4. Write negative security tests (401/403, IDOR, injection) before merging.

## Navigation

- **`references/checklist.md`** — full reference: OWASP/CWE threat-model table,
  the 14-point secure-coding checklist with before/after snippets, dependency &
  supply-chain guidance, SAST tooling, security testing, and anti-patterns. Load
  when implementing or reviewing security-sensitive code.

## Key Reminders

- `pickle.loads` on untrusted bytes = remote code execution; use JSON + schema.
- `subprocess(..., shell=True)` with interpolated input = command injection.
- Keep template autoescape on; never pass raw user input through `|safe`/`mark_safe`.
- Never `verify=False` in requests; never MD5/SHA1 for passwords.
