#!/usr/bin/env python3
"""Verify the two credential scopes of OpenSubtitles Uploader.

The application separates:

1. **Metadata/catalogue account** — REST (opensubtitles.com): search,
   movie identification, profile.  Credentials come from
   ``OPENSUBTITLES_USERNAME`` / ``OPENSUBTITLES_PASSWORD`` (a local
   ``.env`` file is loaded automatically).  It never uploads.
2. **Upload account** — legacy XML-RPC (opensubtitles.org), the one typed
   in the GUI / CLI ``login`` command.  It is the only one that can
   upload.  For scripted checks use ``OPENSUBTITLES_UPLOAD_USERNAME`` /
   ``OPENSUBTITLES_UPLOAD_PASSWORD``.

Usage:

    python scripts/verify_login.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))

from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.config import (
    environment_metadata_credentials,
    environment_upload_credentials,
)
from opensubtitles_uploader.domain.errors import ApiError, AuthError


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")
    metadata = environment_metadata_credentials()
    upload = environment_upload_credentials()

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

    print("\n2) Login de subida con contraseña INCORRECTA (debe fallar limpio)")
    bogus = f"osu_verify_{int(time.time())}"
    try:
        # XML-RPC only — REST /login is rate-limited and belongs to scope (1).
        client._xmlrpc.login(bogus, "definitely-wrong-password")
        results.append(check("El servidor aceptó credenciales falsas (¡problema!)", False))
    except AuthError as exc:
        msg = str(exc)
        words = ("401", "unauthorized", "wrong", "incorrect", "password")
        ok = any(word in msg.lower() for word in words)
        results.append(check("Login incorrecto rechazado con mensaje claro", ok, msg))
    except Exception as exc:  # pragma: no cover
        results.append(check(f"Error inesperado en login: {exc}", False))

    print("\n3) Cuenta de METADATOS (.env, REST)")
    if not api_key:
        results.append(check("Sin Api-Key: la búsqueda avisa correctamente", _no_key_hint(client)))
        print("   (configura OPENSUBTITLES_API_KEY para probar REST de verdad)")
    else:
        try:
            found = bool(client.search_features("Inception"))
            results.append(check("search_features('Inception')", found))
        except Exception as exc:  # pragma: no cover
            results.append(check(f"search_features — {exc}", False))
        if metadata:
            for attempt in (1, 2):
                try:
                    user = client.ensure_metadata_session()
                    results.append(
                        check(
                            "Login REST (metadatos) OK",
                            user is not None,
                            f"usuario: {user.username} · nivel: {user.level}" if user else "",
                        )
                    )
                    break
                except Exception as exc:  # pragma: no cover
                    if attempt == 1 and "rate" in str(exc).lower():
                        time.sleep(2.0)
                        continue
                    results.append(check(f"Login REST — {exc}", False))
                    break
            if client.metadata_user():
                results.append(check("whoami (metadatos) OK", True))
        else:
            print("   (OPENSUBTITLES_USERNAME/PASSWORD ausentes: la búsqueda usa solo la Api-Key)")

    print("\n4) Cuenta de SUBIDA (GUI, XML-RPC)")
    if not upload:
        print(
            "   (configura OPENSUBTITLES_UPLOAD_USERNAME/PASSWORD para probar el login de subida)"
        )
    else:
        try:
            session = client.login(*upload)
            results.append(
                check(
                    "Login de subida (XML-RPC) OK",
                    bool(session.token) and session.user.upload_capable,
                    f"usuario: {session.user.username}",
                )
            )
        except AuthError as exc:
            results.append(check(f"Login de subida rechazado: {exc}", False))
        except Exception as exc:  # pragma: no cover
            results.append(check(f"Login de subida — error inesperado: {exc}", False))
        finally:
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
