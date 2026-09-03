---
name: python-frontend-design
description: Best practices for designing frontends with Python tooling — server-rendered templates (Jinja2/Django/Flask, often + htmx), Python-native UI frameworks (Streamlit, Gradio, Dash, Reflex, NiceGUI, Flet), or FastAPI serving a JS SPA. Covers stack selection, accessibility (WCAG 2.2 AA), responsive/mobile-first design, design tokens, performance (Core Web Vitals), and XSS-safe templating. Use when building or reviewing any UI in a Python project.
license: MIT
compatibility: "Agent Skills standard (SKILL.md). Works with OpenCode, Pi, Zed, Copilot, and DeepSeek Harness. Targets Python 3.10+ with Django/Flask/FastAPI, Jinja2, htmx, Streamlit/Gradio/Dash/Reflex."
metadata:
  author: DarkSiteX
  version: "1.0"
  language: python
  topics: frontend, ui, ux, accessibility, wcag, htmx, jinja2, streamlit, gradio, dash, reflex
---

# Python Frontend Design

## Overview

Design accessible, performant, maintainable frontends using Python tooling. Covers
server-rendered templates (Jinja2/Django/Flask, often with htmx), Python-native UI
frameworks (Streamlit, Gradio, Dash, Reflex, NiceGUI, Flet), and FastAPI serving a
separate JS SPA. The same disciplines apply everywhere: semantic HTML,
WCAG 2.2 AA accessibility, mobile-first responsive layout, a tokenized design
system, and explicit loading/empty/error states.

## When to Use

Use this skill when you are:

- choosing a frontend stack for a Python project;
- building a new UI (templates, dashboard, internal tool, or JS SPA backed by Python);
- redesigning or reviewing UI code for accessibility, performance, or XSS;
- adding interactivity with htmx or a Python-native component framework.

For the API/backend side of a FastAPI + JS split, also load
`python-backend-design`. For security-sensitive UI work (XSS, CSP), also load
`python-security`.

## Core Principles

1. **Semantic HTML first** — `<nav>`, `<main>`, `<section>`, `<button>`,
   `<label>`, ordered headings; framework widgets are not an excuse for div soup.
2. **Accessibility is a requirement, not a phase** — WCAG 2.2 AA from day one:
   contrast ≥ 4.5:1, keyboard operability, visible focus, ≥ 24×24 px targets.
3. **Mobile-first and progressively enhanced** — build for the smallest
   viewport; core flows must work without JavaScript, with htmx/SPA layered on top.
4. **Tokens, not hardcoded values** — a single design system for spacing,
   color (semantic tokens), typography, and radii, reused everywhere.
5. **Never a bare screen** — every view needs loading, empty, error, and
   populated states; errors are specific, near the field, and actionable.
6. **Keep presentation dumb** — no business logic or DB queries in templates;
   keep autoescaping on and never pass raw user input through `|safe`.

## Quick Start

1. Pick the stack from the decision table in `references/checklist.md`
   (prefer server-rendered + htmx unless you need offline state or a large FE team).
2. Define design tokens (spacing/color/type/radius) once, then reuse.
3. Build semantic templates/components with all four states handled.
4. Validate server-side and echo field-level errors back; disable submit while pending.
5. Run the accessibility and performance checklists before calling it done.

## Navigation

- **`references/checklist.md`** — full guidance: stack decision table, ten core
  principles, Python-specific patterns (templates/XSS, htmx, state management per
  framework), a testable accessibility checklist, a performance checklist, and
  anti-patterns. Load when actually building or reviewing a UI.

## Key Reminders

- XSS: autoescape is on by default in Django, Flask Jinja2 (`.html`), and
  Starlette; use `|safe`/`Markup` only for HTML you construct yourself.
- Return HTML fragments from htmx endpoints, not whole pages; detect `HX-Request`.
- Respect each framework's rerun/state model (Streamlit top-to-bottom reruns,
  Dash pure callbacks, Reflex `rx.State`) before writing stateful code.
- Meet Core Web Vitals: LCP < 2.5 s, INP < 200 ms, CLS < 0.1.
