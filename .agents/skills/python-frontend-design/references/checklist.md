# Python Frontend Design — Checklist

Detailed reference for `python-frontend-design`. Covers server-rendered
templates (Jinja2/Django/Flask, often + htmx), Python-native UI frameworks
(Reflex, NiceGUI, Flet, Streamlit, Gradio, Dash/Plotly, Solara), and a Python
backend serving a JS frontend.

## 1. Which stack to choose

| Use case | Recommended approach | Why |
|---|---|---|
| Internal tool / admin CRUD | Flask or Django templates + htmx, or NiceGUI/Flet | Low complexity, no JS build |
| Public, SEO-sensitive website | Django or Flask + Jinja2, htmx for interactivity | Server-rendered HTML is crawlable, fast FCP |
| Data dashboard / ML demo | Streamlit, Dash/Plotly, or Gradio | Built-in widgets, caching, fast iteration |
| Prototype / spike | Streamlit or Gradio | Least code to first working UI |
| App-like, highly stateful UI | Reflex (React under the hood), or FastAPI + React/Vue | Real client state, routing, complex interactivity |
| Product API consumed by JS SPA | FastAPI + React/Vue | Auto OpenAPI gives a typed contract; Python owns API, JS owns view |

Decision rule: **prefer server-rendered HTML + htmx** unless you need offline
state, rich client-side canvas/WebGL, or a large team split across FE/BE. Add a
JS SPA only when the interactivity budget justifies a second language and build
pipeline.

## 2. Core frontend design principles

1. **Semantic HTML first** — `<nav>`, `<main>`, `<section>`, `<button>`,
   `<label>`, ordered headings. Foundation of accessibility and SEO.
2. **Meet WCAG 2.2 AA** — ≥ 4.5:1 text contrast, keyboard operability, visible
   focus, ≥ 24×24 px target size (WCAG 2.5.8).
3. **Mobile-first** — build for the smallest viewport, then add `min-width`
   queries; test at 360 px, 768 px, desktop.
4. **Never a bare screen** — every view needs loading, empty, error, and
   populated states. Errors must be visible, near the offending field, specific,
   and offer a fix.
5. **Design system with tokens** — spacing scale (4 px base), a small semantic
   color palette (`--color-danger`, `--color-success`), type scale, radii.
   Generate once (CSS variables or a theme module) and reuse.
6. **Progressive enhancement** — core flows work without JS; htmx/SPA behavior
   layers on top of a working GET/POST fallback.
7. **Design for failure/latency** — server-side validation echoed back, disable
   submit while pending, confirm destructive actions.
8. **Plan i18n from day one** — Django `gettext`/`{% trans %}`, Flask `Babel`,
   or framework i18n; never hardcode user-facing strings.
9. **Dark mode via one tokenized color source** — `prefers-color-scheme` is a
   single CSS-variable swap, not per-widget overrides.
10. **Keep the mental model simple** — the UI reflects the backend's nouns and
    verbs (htmx's Locality of Behavior: behavior lives next to the markup).

## 3. Python-specific best practices

**Templates & XSS.** Autoescape is on by default in Django, Flask Jinja2
(`.html`), and Starlette's `Jinja2Templates`. Keep it on; escape on output,
validate on input. Use `|safe`/`Markup` only for HTML you construct yourself,
never raw user input. Sanitize user HTML with `bleach`/`nh3` + a strict allowlist.

**Separate presentation from logic.** Dumb templates: no business logic, no DB
queries, minimal branching. Compute in views/services and pass plain data
(dataclasses, dicts, Pydantic models). Use template inheritance (`{% extends %}`)
and includes; a `_partials/` directory of HTML fragments is the htmx reuse unit.

**API contract (FastAPI + JS).** Define request/response Pydantic schemas with
`response_model` so FastAPI generates and validates the contract; the OpenAPI
JSON is the source of truth for JS codegen. Version endpoints, return stable
field names, never leak ORM objects or internal exceptions.

**State management.**
- *Streamlit*: script reruns top-to-bottom on interaction; persist with
  `st.session_state`; cache with `st.cache_data` (pure) / `st.cache_resource`
  (connections/models).
- *Reflex*: state in `rx.State` classes (vars + event handlers); distinguish app
  vs per-session state; keep client state minimal.
- *Gradio*: cross-event state in `gr.State` inside `Blocks`, per-user or global.
- *Dash*: pure declarative `@callback(Output, Input, State)`; callbacks must be
  pure (no side effects) and return complete outputs.

**Avoid N+1 and cache fragments.** `select_related`/`prefetch_related` (Django)
or `selectinload` (SQLAlchemy) before the template loop. Cache expensive HTML
fragments (Redis/`cachetools`/`st.cache_data`) keyed by their inputs; invalidate
on write.

**htmx patterns.** Return HTML *fragments*, not full pages: a POST handler
re-renders the partial and returns it with `hx-target`/`hx-swap` on the
triggering element. Use `hx-boost` for SPA-like navigation, `hx-select` to
extract a sub-tree, `hx-swap-oob` for multi-region updates. Keep `hx-*`
attributes adjacent to the markup they modify (Locality of Behavior). In
Flask/FastAPI, detect the `HX-Request` header to render partial vs full page.

## 4. Accessibility checklist (testable)

- [ ] All images have meaningful `alt`; decorative ones `alt=""`.
- [ ] Every form control has an associated `<label>` (or `aria-label`); errors
      linked via `aria-describedby` and announced.
- [ ] Full keyboard flow: logical Tab order, visible focus, no traps,
      skip-to-content link.
- [ ] Text contrast ≥ 4.5:1 (3:1 large text); color never the only signal.
- [ ] Interactive targets ≥ 24×24 px (WCAG 2.5.8).
- [ ] Focus never obscured by sticky/fixed elements (WCAG 2.4.11).
- [ ] Dragging has a non-drag alternative (WCAG 2.5.7); no dependence on motion.
- [ ] Correct heading hierarchy and `lang` attribute; unique page `<title>`.
- [ ] `prefers-reduced-motion` respected for animations.
- [ ] Screen-reader test: VoiceOver/NVDA + axe or Lighthouse on the actual page.

## 5. Performance checklist

- [ ] Meet Core Web Vitals: LCP < 2.5 s, INP < 200 ms, CLS < 0.1.
- [ ] Server-render above-the-fold HTML; defer non-critical JS (`defer`/`async`).
- [ ] Reserve space (`width`/`height`, `aspect-ratio`) for images/embeds to
      prevent CLS.
- [ ] Compress and modern-format images (`srcset`, WebP/AVIF); lazy-load below
      the fold.
- [ ] `Cache-Control`/ETags, CDN for static assets, minified CSS/JS.
- [ ] Eliminate N+1; profile with Django Debug Toolbar / SQLAlchemy echo.
- [ ] Cache expensive fragments and computed values; invalidate correctly.
- [ ] Python-native apps: `st.cache_data`/`st.cache_resource`, `lru_cache` on
      pure helpers, memoized callbacks.

## 6. Anti-patterns / pitfalls

- Rendering unescaped user input (`|safe` on raw data) → stored XSS.
- Mixing presentation and logic in views/templates → unmaintainable UI.
- N+1 queries in template loops → slow pages.
- Returning whole pages from htmx endpoints → layout duplication; return fragments.
- Serving a heavy SPA for a content site → SEO/FCP regressions, no payoff.
- Ignoring Streamlit rerun semantics → hidden state bugs.
- Unstable API contracts → breaking JS clients; pin schemas + version.
- Hardcoded colors/spacing across files → inconsistent UI; use tokens.
- Blocking the main thread; slow callbacks in Dash/Streamlit.
- No loading/empty/error states → dead screens.
- Accessibility as an afterthought → retrofitting costs more than building it in.

## 7. Sources

- [FastAPI — Templates](https://fastapi.tiangolo.com/advanced/templates/) — official Jinja2/Starlette templating docs.
- [Django — Security](https://docs.djangoproject.com/en/6.0/topics/security/) — official XSS/escaping canon.
- [Flask — Templates & security](https://flask.palletsprojects.com/en/stable/templating/) — official Jinja2 autoescaping docs.
- [Streamlit — Session State](https://docs.streamlit.io/develop/concepts/architecture/session-state) — official rerun/state/caching model.
- [Reflex — State Overview](https://reflex.dev/docs/state/overview/) — official state classes/events docs.
- [Gradio — State in Blocks](https://www.gradio.app/guides/state-in-blocks) — official cross-event state docs.
- [Dash — Flexible Callback Signatures](https://dash.plotly.com/flexible-callback-signatures) — official callback contract.
- [htmx — hx-target](https://htmx.org/attributes/hx-target/) and [htmx Essays](https://htmx.org/essays/) — fragment swapping and hypermedia/Locality of Behavior.
- [web.dev — Web Vitals](https://web.dev/articles/vitals/) and [Learn Responsive Design](https://web.dev/learn/design/) — Google's CWV + responsive reference.
- [Nielsen Norman Group — Error-Message Guidelines](https://www.nngroup.com/articles/error-message-guidelines/) — usability authority on error states.
- [W3C — WCAG 2.2](https://www.w3.org/TR/WCAG22/) — normative accessibility standard.
