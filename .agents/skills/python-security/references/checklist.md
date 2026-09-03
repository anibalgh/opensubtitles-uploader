# Python Application Security — Checklist

Detailed reference for `python-security`. Consult when writing, reviewing, or
hardening security-sensitive Python (web apps, CLI tools, libraries).

## 1. Threat-model summary

Map [OWASP Top 10 (2021)](https://owasp.org/Top10/) and [MITRE CWE Top 25 (2024)](https://cwe.mitre.org/top25/archive/2024/2024_cwe_top25.html) to Python-specific risks:

| Risk | OWASP / CWE | Python manifestation |
|---|---|---|
| Injection | A03:2021; CWE-79/89/77/94 | SQL via f-string queries; `os.system`/`subprocess(..., shell=True)`; `eval`/`exec` on user input |
| XSS | A03:2021; CWE-79 | Jinja2/Django templates with `\| safe`, `mark_safe`, `autoescape off` |
| Insecure deserialization | A08:2021; CWE-502 | `pickle.loads`, `yaml.load`, `marshal`, `shelve`, `torch.load` on untrusted bytes |
| SSRF | A10:2021; CWE-918 | `requests.get(user_url)` / `urllib` fetching attacker-controlled URLs |
| Path traversal | A01:2021; CWE-22 | `open(user_filename)` / `send_file` with unvalidated names |
| Broken access control | A01:2021; CWE-862/863 | Missing per-object authz; IDOR in views; FastAPI without dependency checks |
| Cryptographic failures | A02:2021; CWE-327 | MD5/SHA1 for passwords; `random` for tokens; disabled TLS verification |
| Hardcoded secrets | A07:2021; CWE-798 | API keys committed to git; default creds |
| Vulnerable components | A06:2021; CWE-1395 | Unpinned transitive deps with known CVEs; dependency confusion |
| Security misconfiguration | A05:2021; CWE-16 | `debug=True` in prod; permissive CORS; missing headers |
| Logging failures | A09:2021; CWE-117/778 | Logging secrets, log injection |
| Memory safety | CWE-787/125/416 | Native C extensions (NumPy, lxml, Pillow) — keep them patched |

## 2. Secure coding checklist

1. **Validate and normalize all untrusted input** (request params, headers,
   files, env). Reject what is not expected; whitelist over blacklist. Use
   schema libraries (`pydantic`, `marshmallow`, `cerberus`) and type hints.

2. **Parameterize every SQL query — never interpolate.** Bound parameters; for
   SQLAlchemy prefer the ORM or `text()` with `:params`:

   ```python
   # BAD
   db.execute(f"SELECT * FROM users WHERE name = '{name}'")
   # GOOD
   db.execute(text("SELECT * FROM users WHERE name = :n"), {"n": name})
   # psycopg3: cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
   ```

3. **Keep template autoescaping on; avoid `| safe`.** Jinja2 autoescapes by
   default for HTML; Django templates too. Never pass raw user HTML to `| safe`,
   `mark_safe`, or `|tojson` without sanitization. Sanitize user HTML with
   `bleach`/`nh3` and a strict allowlist.

4. **Never use `shell=True`; pass argv lists.**

   ```python
   # BAD
   subprocess.run(f"ping {host}", shell=True)
   # GOOD
   subprocess.run(["ping", host], check=True)   # host cannot inject flags/commands
   ```

5. **Resolve and confine file paths with `pathlib`.**

   ```python
   from pathlib import Path
   base = Path("/srv/uploads").resolve()
   p = (base / user_path).resolve()
   if not p.is_relative_to(base):          # Python 3.9+
       raise ValueError("path escape")
   ```

6. **Guard SSRF.** Resolve the host, block private/loopback/link-local ranges and
   metadata endpoints (`169.254.169.254`), disallow redirects to internal hosts,
   and route fetches through an egress proxy.

   ```python
   import ipaddress, socket
   ip = ipaddress.ip_address(socket.gethostbyname(host))
   if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
       raise ValueError("SSRF blocked")
   ```

7. **Never deserialize untrusted data with `pickle`.** Pickle executes code on
   load (`__reduce__`), enabling RCE. Prefer JSON, `yaml.safe_load`, or explicit
   schemas. Use `defusedxml` for XML to stop billion-laughs/XXE:

   ```python
   import defusedxml.ElementTree as ET   # not xml.etree.ElementTree
   tree = ET.fromstring(xml_bytes)
   ```

8. **Manage secrets properly.** Read from env vars or a secret manager (Vault,
   AWS Secrets Manager, cloud key stores). Never hardcode keys, commit `.env`, or
   log secrets. Gitignore `.env`, `*.pem`, `*.key`. Use `python-dotenv` only for
   local dev; inject real secrets via the orchestrator in prod.

9. **Use `cryptography` and strong primitives.** Password hashing: `argon2`
   (Argon2id) or `bcrypt`; never MD5/SHA1, never reversible encryption for
   passwords. Tokens: `secrets.token_urlsafe` (not `random`). Integrity: SHA-256
   via `hashlib`. TLS: `ssl` with `check_hostname=True` and a modern minimum
   (`TLSVersion.TLSv1_2`); never `verify=False` in requests.

10. **Harden JWTs and sessions.** Validate `alg` (reject `none`, require
    RS256/HS256 as designed), `exp`/`nbf`/`iss`/`aud`, and verify the signature
    against a trusted key; never accept untrusted `kid` without pinning. Use
    signed, `HttpOnly`, `Secure`, `SameSite` cookies; set `SESSION_COOKIE_SECURE`
    and rotate the `SECRET_KEY`.

11. **Enforce CSRF and CORS.** Enable Django's `CsrfViewMiddleware` and
    `{% csrf_token %}`. In FastAPI, add `CORSMiddleware` with explicit
    `allow_origins`, `allow_credentials=True` only with a pinned origin list
    (never `*` with credentials), and allow only needed methods/headers.

12. **Rate-limit and throttle** auth endpoints, APIs, and expensive routes
    (`slowapi`/`limits`, Django-ratelimit, or a gateway) to blunt brute-force/DoS.

13. **Set security headers.** `Content-Security-Policy`, `Strict-Transport-Security`,
    `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors`,
    `Referrer-Policy`. Use middleware (Django `SECURE_*` settings, `django-csp`,
    or custom middleware) and force HTTPS.

14. **Log without sensitive data.** Redact passwords, tokens, auth headers, and
    PII; validate/sanitize before writing to logs to prevent log injection (strip
    newlines); use structured logging and audit authz-sensitive events.

## 3. Dependency & supply-chain security

- **Pin everything** (exact versions, ideally hashes) and commit a lockfile —
  `pip-tools` (`requirements.in` + `requirements.txt`), Poetry (`poetry.lock`),
  PDM, or `uv` (`uv.lock`). Regenerate on change.
- **Audit continuously** with [pip-audit](https://github.com/pypa/pip-audit) and
  `pip list --outdated`; fail CI on new CVEs. Prefer `pip-audit` over the retired
  `safety` free DB.
- **Generate an SBOM** (`cyclonedx-bom` / `syft`) for consumers and compliance.
- **Publish with PyPI Trusted Publishing** (OIDC, no long-lived tokens) and sign
  with PEP 740 attestations; store secrets as short-lived CI secrets.
- **Vet packages**: check maintainers, release recency, source repo, license, and
  download stats; watch for typosquats and dependency confusion (PEP 708). Prefer
  internal mirrors/proxies with an allowlist.

## 4. SAST & tooling

- **[Bandit](https://github.com/PyCQA/bandit)** — Python AST security linter
  (`bandit -r src/`); baseline and fail the build on high/medium.
- **Semgrep** — fast cross-language rules; run OWASP ruleset plus
  `python.lang.security.*`.
- **pip-audit / `pip check`** — `pip check` verifies dependency constraints;
  pip-audit checks CVEs.
- **CodeQL (GitHub Security Lab)** — e.g. `py/unsafe-deserialization`; **Snyk
  Code** Python rules.
- **Secrets scanning** — gitleaks, trufflehog, or GitHub secret scanning.
- **pre-commit hooks** — `bandit`, `detect-secrets`, `ruff` (with security rules),
  lockfile drift check.

## 5. Security testing

- **Authz unit tests**: assert unauthenticated and unprivileged users get
  401/403, and that object-level checks (IDOR) are enforced.
- **Property-based fuzzing with Hypothesis** on parsers, validators, and
  deserializers; `atheris` for C-extension fuzzing.
- **Header/transport checks**: assert CSP, HSTS, and cookie flags in integration
  tests (`pytest` + Django test client / `httpx`).
- **Dependency and SAST gates** in CI on every PR.

## 6. Anti-patterns / pitfalls

```python
# BAD: pickle on untrusted data (RCE)
pickle.loads(request.body)
# GOOD: JSON with schema validation
import json, pydantic
class Payload(pydantic.BaseModel):
    name: str
data = Payload.model_validate(json.loads(request.body))

# BAD: yaml.load (arbitrary objects)
yaml.load(raw)                 # and yaml.load(raw, Loader=yaml.Loader)
# GOOD
yaml.safe_load(raw)

# BAD: subprocess with shell + interpolation
subprocess.check_output("git log " + ref, shell=True)
# GOOD
subprocess.check_output(["git", "log", ref])

# BAD: weak password hash / weak randomness
hashlib.md5(pw.encode()).hexdigest(); random.randint(0, 2**32)
# GOOD
argon2.PasswordHasher().hash(pw); secrets.token_urlsafe(32)

# BAD: interpolated SQL / disabled TLS
f"SELECT * FROM t WHERE id={x}"; requests.get(url, verify=False)
# GOOD: bound params; keep verify=True (bundle pinned CA)
```

## 7. Sources

- [OWASP Top 10 (2021)](https://owasp.org/Top10/) — industry-standard web risk ranking.
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) — authoritative mitigation guidance (incl. the Deserialization sheet).
- [CPython security_warnings.rst](https://github.com/python/cpython/blob/main/Doc/library/security_warnings.rst) — PSF's canonical warnings (pickle/ssl/etc.).
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and [PyPI blog](https://blog.pypi.org/posts/2023-04-20-introducing-trusted-publishers/) — official PyPA release security.
- [PEP 708](https://peps.python.org/pep-0708/) — PyPA dependency-confusion mitigation.
- [pip-audit](https://github.com/pypa/pip-audit) — PyPA's vulnerability auditor.
- [Bandit (PyCQA)](https://github.com/PyCQA/bandit) — Python security linter docs.
- [Snyk Code Python rules](https://docs.snyk.io/scan-fix-and-prevent/scan-with-snyk/snyk-code/snyk-code-security-rules/python-rules) — vendor Python security rule catalog.
- [GitHub CodeQL py/unsafe-deserialization](https://codeql.github.com/codeql-query-help/python/py-unsafe-deserialization/) — GitHub Security Lab query docs.
- [MITRE CWE Top 25 (2024)](https://cwe.mitre.org/top25/archive/2024/2024_cwe_top25.html) — most dangerous weaknesses ranking.
