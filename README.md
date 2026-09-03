# OpenSubtitles Uploader (Python)

> Sube tus subtítulos a [OpenSubtitles](https://www.opensubtitles.com) tan
> fácil como arrastrar y soltar — reimplementación en **Python 3.12/3.13**,
> **multiplataforma (Windows, macOS y Linux)**, con interfaz moderna Qt
> (PySide6) y **arquitectura hexagonal**, del clásico *OpenSubtitles
> Uploader* (NW.js).

La aplicación analiza un **video local** (hash OSDb, tamaño, fps, duración,
fotogramas, resolución), identifica la **película/serie/episodio**, analiza
el **subtítulo** (MD5, idioma, subtítulos para sordos, traducción automática,
solo partes extranjeras) y lo **sube a OpenSubtitles** con un clic.  El
núcleo de negocio no depende de Qt, HTTP ni disco, por lo que es 100 %
testeable y reutilizable desde la GUI **o** desde la línea de comandos.

---

## ✨ Funcionalidades (estado actual)

| Funcionalidad | Descripción |
|---|---|
| 🔐 **Arranque con validación** | Al abrir la GUI se valida la **cuenta de metadatos** (`.env`, opensubtitles.com) contra la API REST; si falta o es incorrecta, muestra el problema en un diálogo y **cierra la app**. |
| 👤 **Login de subida (ventana)** | Valida la cuenta de **opensubtitles.org** (XML-RPC) con diálogo de error claro si es incorrecta. **Recordar** guarda las credenciales en el *keychain* del SO (o cifradas con Fernet como respaldo). |
| 🎬 **Carga de video** | Arrastrar y soltar o examinar; calcula el *moviehash* de OpenSubtitles leyendo solo los primeros/últimos 64 KiB (instantáneo incluso con videos de varios GB). |
| 🧠 **Identificación automática** | Por *moviehash* vía REST; si no hay coincidencia, por nombre de archivo y búsqueda en el catálogo; **prefiere el episodio cuyo `SxxEyy` coincide** con el nombre del archivo. Rellena IMDB id y carátula. |
| 📊 **Metadatos técnicos** | vía `mediainfo` o `ffprobe` (opcional): fps, duración (ms), fotogramas, resolución y alta definición. Si no hay binarios, la app funciona sin esa ficha. |
| 💬 **Carga de subtítulos** | MD5, auto-detección de idioma (contenido + nombre de archivo, offline y sin dependencias), detección de *hearing impaired*, *machine translated* y *foreign parts only*. |
| 🔎 **Búsqueda** | Busca películas/series/episodios y asigna el IMDB id sin salir de la app. |
| ⬆️ **Subida robusta** | Antes de subir ejecuta `TryUploadSubtitles`: si el subtítulo **ya existe** lo informa con enlace; si el servidor responde `IDMovieImdb` (autoritativo por hash, clave en series) lo usa en la subida. El contenido se envía en **zlib (RFC 1950) + base64**, el formato exacto que espera el endpoint XML-RPC. |
| 🎨 **Interfaz moderna** | Qt con tema claro/oscuro por tokens, drag & drop nativo, icono oficial por plataforma (`.ico`/`.icns`/`.png`), estados de carga/error y **diálogos modales** para errores de login/subida (motivo siempre visible). |
| ⌨️ **Atajos** | `Ctrl+O` importar archivos, `Ctrl+W` limpiar, `Ctrl+Enter` subir, `Ctrl+F` buscar, `Esc` cerrar diálogos. |
| 🌐 **Idioma de la UI** | Inglés y español (Ajustes); mensajes de error localizados. |
| 🧩 **CLI** | Mismo núcleo en terminal: `login`, `logout`, `whoami`, `analyze`, `search`, `upload`. |

## 🔑 Dos cuentas distintas, dos cometidos

OpenSubtitles mantiene **dos bases de datos separadas**, y la app respeta esa
separación:

| Ámbito | Cuenta | Servicio | Desde dónde |
|---|---|---|---|
| 🔍 **Metadatos / catálogo** (búsqueda, identificación, perfil) | opensubtitles.com | REST `api.opensubtitles.com` | `.env`: `OPENSUBTITLES_USERNAME` / `OPENSUBTITLES_PASSWORD` (+ `OPENSUBTITLES_API_KEY`) |
| ⬆️ **Subida de subtítulos** | opensubtitles.org (legacy) | XML-RPC `api.opensubtitles.org/xml-rpc` | Login de la **ventana** (GUI) o `login` en CLI |

- La cuenta del `.env` **nunca sube** (`upload_capable=False`).
- El login de la ventana **solo** valida la cuenta de subida `.org` y es el
  único que habilita `UploadSubtitles`.
- La barra de estado y los Ajustes muestran qué cuenta se usa en cada ámbito;
  si se intenta subir sin sesión `.org`, la app abre un diálogo explicándolo.

## 🧱 Requisitos

- **Python 3.12 o 3.13** (PySide6 todavía no publica wheels para 3.14).
- [Poetry](https://python-poetry.org) ≥ 2.0.
- *(Opcional, recomendado)* `mediainfo` o `ffprobe` en el `PATH` para la
  ficha técnica del video.
- Una **API key gratuita** de opensubtitles.com: <https://www.opensubtitles.com>
  → tu perfil → *API* → *API keys*.
- **Cuenta de metadatos** opensubtitles.com y **cuenta de subida**
  opensubtitles.org (pueden ser la misma si la cuenta existe en ambos
  sistemas).

## 🚀 Instalación y configuración

```bash
git clone git@github.com:anibalgh/opensubtitles-uploader.git
cd opensubtitles-uploader
poetry install                     # o: poetry install -E keyring (keychain del SO)
```

Cree un archivo `.env` en la raíz (ignorado por git; la app lo carga sola y
las variables de entorno reales tienen prioridad):

```
OPENSUBTITLES_API_KEY=tu_api_key_de_opensubtitles.com
OPENSUBTITLES_USERNAME=usuario_metadatos_com      # catálogo/búsqueda (.com)
OPENSUBTITLES_PASSWORD=pass_metadatos_com
OPENSUBTITLES_UPLOAD_USERNAME=usuario_subida_org  # opcional: login de subida
OPENSUBTITLES_UPLOAD_PASSWORD=pass_subida_org     # (scripts de verificación)
```

> La API key y las credenciales de metadatos también pueden ir como
> variables de entorno reales.  Las credenciales de **subida** se escriben en
> el login de la GUI (opción *Recordar* guarda en el keychain).

### Interfaz gráfica

```bash
poetry run opensubtitles-uploader-gui
```

Al iniciar se valida la cuenta de metadatos (`.env`); si es correcta se abre
la ventana.  Luego: arrastre o examine el **video** y su **subtítulo** →
revise la ficha (use la lupa 🔎 si no se identificó) → inicie sesión con su
**cuenta de subida** (arriba a la derecha) → **Subir**.

### Línea de comandos (mismo núcleo)

```bash
poetry run opensubtitles-uploader --help
poetry run opensubtitles-uploader login --username TU_USUARIO_ORG
poetry run opensubtitles-uploader analyze video.mkv sub.eng.srt
poetry run opensubtitles-uploader search "The Terror"
poetry run opensubtitles-uploader upload video.mkv sub.eng.srt --language en
```

Comandos: `login`, `logout`, `whoami`, `analyze`, `search`, `upload`.

## 🏛️ Arquitectura (hexagonal)

```
src/opensubtitles_uploader/
├── domain/          # reglas puras: sin frameworks ni I/O
│   ├── model.py     # VideoFile, SubtitleFile, MovieRef, MediaInfo, Session…
│   ├── files.py     # extensiones y heurísticas de subtítulos (flags)
│   ├── naming.py    # limpieza de títulos y detección SxxEyy
│   ├── pairing.py   # emparejamiento video ⇄ subtítulo
│   └── errors.py    # errores tipados (AuthError, ApiError, UploadFailedError…)
├── application/     # casos de uso + puertos (typing.Protocol)
│   ├── ports.py     # OpenSubtitlesAuth/Catalog/Uploader, MediaProbe,
│   │                # FileHasher, LanguageDetector, SettingsStore, SecretStore…
│   └── services.py  # AuthService, VideoService, SubtitleService,
│                    # CatalogService, UploadService
├── adapters/        # implementaciones concretas
│   ├── osapi/       # client.py (REST+XML-RPC), xmlrpc.py, keys.py (Api-Key)
│   ├── media/       # hashing OSDb/MD5, probe (mediainfo/ffprobe),
│   │                # detector de idioma offline, dataset de idiomas
│   ├── storage/     # settings.json + secretos (keychain o Fernet)
│   ├── ui/          # PySide6: theme, i18n (EN/ES), icons, workers,
│   │                # dialogs, main_window, main (punto de entrada)
│   └── cli/         # Typer + Rich (mismo núcleo)
├── data/            # os_languages.json + icons (os-icon .png/.ico/.icns)
├── bootstrap.py     # raíz de composición: cablea adaptadores → núcleo
└── config.py        # rutas de usuario (platformdirs), .env y variables de entorno
tests/               # unit/ + e2e/ (los e2e requieren red, desactivados)
scripts/             # verify_login.py, build_app.py
```

### Cómo se conecta con OpenSubtitles

- **REST** (`api.opensubtitles.com/api/v1`, header `Api-Key`): búsqueda de
  features (`GET /features`), identificación por *moviehash*
  (`GET /subtitles?moviehash=…`), login/perfil de la cuenta de metadatos
  (`POST /login`, `GET /infos/user`) e idiomas (`GET /infos/languages`).
- **XML-RPC** (`api.opensubtitles.org/xml-rpc`, solo usuario/contraseña de la
  cuenta `.org`): `LogIn` → `TryUploadSubtitles` (¿ya existe? + `IDMovieImdb`
  autoritativo) → `UploadSubtitles` con `subcontent = base64(zlib(RFC1950))`.

Si OpenSubtitles llegara a publicar la subida en REST, solo habría que añadir
un adaptador nuevo sin tocar el núcleo (ventaja de los puertos).

## 📦 Empaquetado — binarios por sistema operativo

PyInstaller **no compila en cruz**: el binario debe generarse **en el mismo
SO donde se va a ejecutar**.  En las tres plataformas el procedimiento es el
mismo; abajo tienes los comandos exactos y el resultado.

Prerrequisitos comunes:

1. Python 3.12 o 3.13 instalado.
2. Poetry instalado.
3. Clonar el repo y ejecutar `poetry install -E build` (instala PyInstaller).

### 🪟 Windows (PowerShell)

```powershell
git clone git@github.com:anibalgh/opensubtitles-uploader.git
cd opensubtitles-uploader
poetry install -E build
poetry run python scripts/build_app.py gui      # → dist\OpenSubtitlesUploader.exe
poetry run python scripts/build_app.py cli      # (opcional) → dist\opensubtitles-uploader-cli.exe
```

- Icono `.ico` incrustado en el ejecutable.
- *(Opcional)* instale `mediainfo` (`winget install MediaArea.MediaInfo`) o
  FFmpeg para la ficha técnica.

### 🍎 macOS (Terminal)

```bash
git clone git@github.com:anibalgh/opensubtitles-uploader.git
cd opensubtitles-uploader
poetry install -E build
poetry run python scripts/build_app.py gui      # → dist/OpenSubtitlesUploader.app
poetry run python scripts/build_app.py cli      # (opcional) → dist/opensubtitles-uploader-cli
```

- Icono `.icns` incrustado en la app bundle.
- *(Opcional)* `brew install ffmpeg` o `brew install mediainfo`.
- Para distribuir fuera de tu equipo: firme y notarice la app
  (`codesign` + `notarytool`), o el usuario final deberá hacer clic derecho →
  *Abrir* la primera vez.

### 🐧 Linux (bash)

```bash
git clone git@github.com:anibalgh/opensubtitles-uploader.git
cd opensubtitles-uploader
poetry install -E build
poetry run python scripts/build_app.py gui      # → dist/OpenSubtitlesUploader
poetry run python scripts/build_app.py cli      # (opcional) → dist/opensubtitles-uploader-cli
```

- Icono `.png` referenciado; los recursos (iconos + lista de idiomas) quedan
  incrustados en el binario.
- *(Opcional)* `sudo apt install ffmpeg` o `sudo apt install mediainfo`
  (Debian/Ubuntu); en otras distros use su gestor equivalente.

### Notas del empaquetado

- El script `scripts/build_app.py` incluye automáticamente la carpeta de
  datos (`os_languages.json` + iconos) dentro del binario; los ajustes,
  secretos y `.env` **no** se empaquetan (se leen del usuario al ejecutar).
- Al ejecutar el binario, el `.env` se busca: **junto al ejecutable**,
  en el directorio actual, en la raíz del repo (desarrollo) y en la carpeta
  de configuración del usuario.  Si falta, la app lo indica y se cierra
  (también puede exportar las variables como entorno real).
- Entradas: GUI → `opensubtitles_uploader.adapters.ui.main:main`
  (sin consola), CLI → `opensubtitles_uploader.adapters.cli.main:main`.
- Resultado en `dist/`; artefactos intermedios en `build/` (ignorados por
  git).
- Para instaladores finales (NSIS/MSI, DMG, .deb/AppImage) puede envolver el
  binario generado con la herramienta que prefiera; el icono oficial ya está
  incluido.

### Releases automáticas (GitHub Actions)

El repositorio incluye `.github/workflows/release.yml`: al publicar un tag
`v*`, se compilan los binarios **GUI y CLI en paralelo para Windows, macOS
y Linux** (matriz de runners con PyInstaller) y se publica una **GitHub
Release** con los tres artefactos (`OpenSubtitlesUploader-windows.zip`,
`OpenSubtitlesUploader-macos.zip`, `OpenSubtitlesUploader-linux.tar.gz`),
cada uno con la GUI (`OpenSubtitlesUploader`) y la CLI
(`opensubtitles-uploader-cli`).

```bash
git tag v0.2.0
git push origin v0.2.0     # dispara el workflow y crea la Release
```

También puede ejecutarse manualmente desde *Actions → Release binaries →
Run workflow*.  Nota: los binarios no están firmados (macOS pedirá *Abrir*
la primera vez; Windows mostrará el aviso de SmartScreen).

## 🧪 Desarrollo y calidad

```bash
poetry run pytest                                   # 56 tests unitarios
poetry run ruff check src tests scripts             # linter
poetry run mypy src                                 # chequeo estático estricto
poetry run bandit -c pyproject.toml -r src          # análisis de seguridad
poetry run ruff format --check src tests scripts    # formato
```

Verificación en vivo de cuentas/APIs (usa `.env`):

```bash
poetry run python scripts/verify_login.py
```

Los tests `e2e` (red real) están desactivados por defecto:
`poetry run pytest -m e2e`.

## ⚠️ Avisos

- **Arranque con validación**: la GUI valida la cuenta de metadatos del
  `.env` contra opensubtitles.com antes de abrir la ventana; si falta o es
  incorrecta, muestra el motivo y se cierra.  El login de la ventana valida
  por separado la cuenta de subida `.org`.
- Esta aplicación **no es** OpenSubtitles: usa su API pública y depende de su
  disponibilidad (errores `503/506` = mantenimiento o caída temporal).
- El MD5 del subtítulo se usa solo como huella de contenido (requisito del
  servicio), nunca como contraseña.
- Las credenciales de subida y la API key se guardan en el keychain del SO
  cuando es posible; nunca en texto plano.  Las de metadatos viven en `.env`
  (ignorado por git).

## 📄 Licencia

MIT — inspirado en
[vankasteelj/opensubtitles-uploader](https://github.com/vankasteelj/opensubtitles-uploader)
(GPL-3.0 original), reimplementado desde cero en Python (PySide6).  El icono
es el oficial del proyecto original; la lista de idiomas procede de su
`os-lang.json`.
