# AGENTS.md — contexto del proyecto

> Fichero de contexto para agentes/colaboradores: **léelo antes de tocar
> código**. Si algo de aquí contradice al `README.md`, gana el `README.md`.

## Qué es

**OpenSubtitles Uploader**: reimplementación en Python del clásico uploader
(NW.js). Analiza un video local y sube su subtítulo a OpenSubtitles. Un mismo
núcleo sirve a una **GUI PySide6** y a una **CLI Typer/Rich**.
Python 3.12/3.13, gestionado con **Poetry ≥ 2**.

## Invariantes de arquitectura (hexagonal)

- `domain/` → reglas puras; **no** importa frameworks ni hace I/O.
- `application/ports.py` → contratos (`typing.Protocol`); `services.py` los usa.
- `adapters/` → implementaciones (`osapi`, `media`, `storage`, `ui`, `cli`).
- `bootstrap.py` → **única** raíz de composición.
- `config.py` → **único** módulo que lee el entorno, y lo hace de forma
  **perezosa**: usa `api_base_url()` / `http_timeout()`, nunca constantes de
  módulo (se evaluarían antes de `load_dotenv()`).
- La regla de dependencia se respeta: `domain`/`application` no importan
  adaptadores ni Qt.

## Dos cuentas separadas (no mezclar)

| Ámbito | Servicio | Credenciales | ¿Sube? |
|---|---|---|---|
| Metadatos / catálogo | REST `api.opensubtitles.com` | `.env`: `OPENSUBTITLES_USERNAME/PASSWORD` + `API_KEY` | **No** |
| Subida | XML-RPC `api.opensubtitles.org` | Login GUI/CLI (`opensubtitles.org`) | **Sí** |

## Comandos

```bash
poetry run pytest                                # unitarios (e2e desmarcados)
poetry run pytest -m e2e                         # requieren red
poetry run ruff check src tests scripts
poetry run ruff format --check src tests scripts
poetry run mypy src                              # strict
poetry run bandit -c pyproject.toml -r src
```

## ✅ Checklist al cargar el contexto

1. **Techos de dependencias (`<X`) — el punto más delicado.**
   Un techo bajo puede **bloquear parches de seguridad**. Revisa sobre todo
   **`cryptography`** (hoy `>=50.0.0,<51.0.0`): ya pasó que el techo `<46`
   dejó fuera los *fixes* de 46.0.5–50.0.0.
   ```bash
   poetry run pip index versions cryptography   # ¿hay versión más nueva?
   poetry run pip index versions pytest pytest-cov
   ```
   Si algún aviso se arregla por encima del techo, **súbelo**, regenera el lock
   (`poetry lock` solo re-resuelve lo afectado) y verifica:
   ```bash
   poetry install
   poetry run pytest            # incluye test_fernet_decrypts_legacy_vault
   poetry run pip-audit         # debe salir limpio
   ```
   Ver también *«Política de dependencias y techos»* en el `README.md`.

2. **Auditoría limpia.** `pip-audit` es un gate **bloqueante** en
   `.github/workflows/ci.yml` (job `audit`). Debe reportar
   `No known vulnerabilities found`.

3. **Fernet / vaults.** Nunca guardar credenciales en claro (keychain del SO o
   Fernet con ficheros `chmod 600`). Si tocas
   `adapters/storage/secret_store.py`, corre
   `tests/unit/test_storage.py::test_fernet_decrypts_legacy_vault`: garantiza
   que un vault escrito por una versión antigua sigue descifrándose.

4. **Secretos.** `.env` está en `.gitignore`: **no** lo commitees, no lo
   imprimas y no pegues sus valores en la conversación ni en logs.

5. **Errores e i18n.** Los errores del dominio llevan un `code` estable
   (`domain/errors.py`); la UI los traduce (EN/ES en `adapters/ui/i18n.py`).
   No metas textos de presentación en el núcleo.

6. **Antes de dar algo por terminado**, los cinco gates del CI en verde
   (ruff check, ruff format --check, mypy, bandit, pytest) + `pip-audit`.

## Notas del entorno

- `dist/` y `build/` son artefactos de PyInstaller (ignorados por git).
- Los tests `e2e` tocan la red y están deseleccionados por defecto.
- `poetry` puede necesitar caché escribible fuera de `$HOME` en entornos
  restringidos: `POETRY_CACHE_DIR` / `POETRY_DATA_DIR`.
