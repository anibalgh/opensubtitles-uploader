#!/usr/bin/env python3
"""Verify that login (and the OpenSubtitles APIs) really work.

It performs, in order:

1. **XML-RPC legacy** (used for the upload login): checks the endpoint is
   reachable via an anonymous ``GetSubLanguages`` call, then proves the
   whole login plumbing with a deliberately *wrong* password — the server
   must answer with a clean 401-style fault that our client maps to an
   :class:`AuthError` ("Wrong username or password").
2. **REST** (used for catalogue/search): when an API key is configured,
   runs a real feature search and, with credentials, a real ``/login`` +
   ``/infos/user``.
3. **Real login**: only when credentials are provided (see below), logs in
   for real and prints the user profile.

Credentials are read from the environment or from an optional ``.env``
file in the project root (never committed):

    OPENSUBTITLES_USERNAME=your_user
    OPENSUBTITLES_PASSWORD=your_password
    OPENSUBTITLES_API_KEY=your_api_key

Usage:

    python scripts/verify_login.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient  # noqa: E402
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource  # noqa: E402
from opensubtitles_uploader.domain.errors import ApiError, AuthError  # noqa: E402


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    _load_dotenv()
    username = os.environ.get("OPENSUBTITLES_USERNAME", "")
    password = os.environ.get("OPENSUBTITLES_PASSWORD", "")
    api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")

    client = OpenSubtitlesClient(
        api_key=ApiKeySource(None), user_agent="OpenSubtitles-Uploader v0.1.0 (verify)"
    )
    results: list[bool] = []

    print("\n1) Endpoint XML-RPC (subida) — comprobación anónima")
    try:
        languages = client._xmlrpc.get_sub_languages()
        results.append(
            check(
                "GetSubLanguages (XML-RPC responde)",
                len(languages) > 50,
                f"{len(languages)} idiomas",
            )
        )
    except Exception as exc:  # pragma: no cover
        results.append(check(f"GetSubLanguages — {exc}", False))

    print("\n2) Login con contraseña INCORRECTA (debe fallar limpio)")
    bogus = f"osu_verify_{int(time.time())}"
    try:
        # XML-RPC only — REST /login is rate-limited to 1 req/s and is
        # reserved for the real-login test below.
        client._xmlrpc.login(bogus, "definitely-wrong-password")
        results.append(check("El servidor aceptó credenciales falsas (¡problema!)", False))
    except AuthError as exc:
        msg = str(exc)
        words = ("401", "unauthorized", "wrong", "incorrect", "password")
        ok = any(word in msg.lower() for word in words)
        results.append(check("Login incorrecto rechazado con mensaje claro", ok, msg))
    except Exception as exc:  # pragma: no cover
        results.append(check(f"Error inesperado en login: {exc}", False))

    print("\n3) REST — búsqueda y login (requiere OPENSUBTITLES_API_KEY)")
    if not api_key:
        results.append(check("Sin Api-Key: la búsqueda avisa correctamente", _no_key_hint(client)))
        print("   (configura OPENSUBTITLES_API_KEY para probar REST de verdad)")
    else:
        try:
            found = bool(client.search_features("Inception"))
            results.append(check("search_features('Inception')", found))
        except Exception as exc:  # pragma: no cover
            results.append(check(f"search_features — {exc}", False))
        with contextlib.suppress(Exception):
            client._api_key.store(api_key)

    print("\n4) Login REAL (requiere OPENSUBTITLES_USERNAME y PASSWORD)")
    if not (username and password):
        print("   (sin credenciales: se omite. Crea un archivo .env o exporta las variables)")
    else:
        for attempt in (1, 2):  # retry once on REST rate limit (1 req/s)
            try:
                session = client.login(username, password)
                user = session.user
                results.append(
                    check(
                        "Login real OK (sesión REST/XML válida)",
                        bool(session.token or user.user_id),
                        f"usuario: {user.username} · nivel: {user.level or 'user'}",
                    )
                )
                if not user.upload_capable:
                    # The legacy .org upload database is separate from .com
                    # accounts; this is a capability warning, not a login failure.
                    print("   [i] cuenta sin acceso de subida (XML-RPC .org la rechaza):")
                    print("       el login/búsqueda funcionan; la subida necesita una cuenta .org.")
                if api_key:
                    try:
                        fresh = client.whoami()
                        results.append(
                            check("whoami REST OK", bool(fresh.user_id), f"{fresh.level}")
                        )
                    except Exception as exc:  # pragma: no cover
                        results.append(check(f"whoami — {exc}", False))
                break
            except AuthError as exc:
                if "rate limit" in str(exc).lower() and attempt == 1:
                    time.sleep(2.0)
                    continue
                results.append(check(f"Login real rechazado: {exc}", False))
            except Exception as exc:  # pragma: no cover
                results.append(check(f"Login real — error inesperado: {exc}", False))
                break
        with contextlib.suppress(Exception):
            client.logout()

    print()
    failures = sum(1 for ok in results if not ok)
    print(f"{len(results) - failures}/{len(results)} comprobaciones superadas")
    return 1 if failures else 0


def _no_key_hint(client: OpenSubtitlesClient) -> bool:
    """Without an API key, /features must fail with a clear api_key_required."""
    try:
        client.search_features("Inception")
        return False
    except ApiError as exc:
        return exc.code == "api_key_required"
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
