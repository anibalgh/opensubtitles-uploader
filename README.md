# OpenSubtitles Uploader (Python)

> Sube tus subtítulos a [OpenSubtitles](https://www.opensubtitles.com) tan
> fácil como arrastrar y soltar — reimplementación en Python, con interfaz
> moderna y multiplataforma, del clásico *OpenSubtitles Uploader* (NW.js).

Esta aplicación analiza un **video local** (hash OSDb, tamaño, resolución,
fps, duración, nº de fotogramas), intenta identificar la **película/serie**,
analiza el **subtítulo** asociado (MD5, idioma, subtítulos para sordos,
traducción automática, solo partes extranjeras) y lo **sube a OpenSubtitles**
con un solo clic.  Corre en **Windows, macOS y Linux** gracias a Qt
(PySide6) y está escrita en Python 3.12+ con arquitectura hexagonal
(puertos y adaptadores), de modo que el núcleo es 100 % testeable y
ajeno a la interfaz.

---

## ✨ Funcionalidades (paridad con el proyecto original)

| Funcionalidad | Descripción |
|---|---|
| 🔐 **Login / logout** | Sesión contra la API REST de OpenSubtitles; credenciales guardadas en el *keychain* del sistema (o cifradas con Fernet como respaldo). |
| 🎬 **Carga de video** | Arrastrar y soltar o seleccionar; calcula el *moviehash* de OpenSubtitles y el tamaño, sin leer todo el archivo (solo primeros/últimos 64 KiB). |
| 🧠 **Identificación automática** | Por *moviehash* vía la API; si no hay coincidencia, por nombre de archivo y búsqueda en el catálogo.  Rellena IMDB id y carátula. |
| 📊 **Metadatos técnicos** | vía `mediainfo` o `ffprobe` (opcional): fps, duración (ms), fotogramas, resolución y detección de alta definición. |
| 💬 **Carga de subtítulos** | MD5, auto-detección de idioma (contenido + nombre de archivo, offline), detección de *hearing impaired*, *machine translated* y *foreign parts only*. |
| 🔎 **Búsqueda IMDB** | Busca películas/series/episodios y asigna el IMDB id sin salir de la app. |
| ⬆️ **Subida** | Verifica si ya existe en la base de datos y sube con todos los metadatos; enlace directo al subtítulo recién creado. |
| 🎨 **Interfaz moderna** | Qt (Material-like), tema claro/oscuro, drag & drop nativo del sistema, diálogos de archivo nativos, avisos y estados de carga/error. |
| ⌨️ **Atajos** | `Ctrl+O` abrir archivos, `Ctrl+W` limpiar, `Ctrl+Enter` subir, `Esc` cerrar diálogos, etc. |
| 🧩 **CLI** | El mismo núcleo disponible como herramienta de terminal (`opensubtitles-uploader`), ideal para automatización y depuración. |

## 📸 ¿Cómo se usa?

1. Arrastre (o pulse *Examinar*) un archivo de **video** y su **subtítulo**
   sobre la ventana.
2. Si el video ya está identificado, la aplicación rellena sola la ficha;
   si no, use la lupa 🔎 para buscar la película por título.
3. Compruebe los datos, elija el **idioma** del subtítulo si la
   auto-detección falló y pulse **Subir**.

## 🧱 Requisitos

- **Python 3.12 o 3.13** (PySide6 todavía no publica wheels para 3.14).
- [Poetry](https://python-poetry.org) ≥ 2.0 para instalar.
- *(Opcional, recomendado)* `mediainfo` o `ffprobe` en el `PATH` para
  rellenar fps/duración/fotogramas.
- Una **clave de API de OpenSubtitles** (gratuita): regístrese en
  <https://www.opensubtitles.com> → *API* → *API keys*, y péguela en
  *Ajustes* de la aplicación (o en la variable de entorno
  `OPENSUBTITLES_API_KEY`).

## 🚀 Instalación y ejecución

```bash
git clone git@github.com:anibalgh/opensubtitles-uploader.git
cd opensubtitles-uploader
poetry install            # o: poetry install --extras keyring (keychain del SO)
```

Interfaz gráfica:

```bash
poetry run opensubtitles-uploader-gui
```

Línea de comandos (mismo núcleo):

```bash
poetry run opensubtitles-uploader --help
poetry run opensubtitles-uploader login --username TU_USUARIO
poetry run opensubtitles-uploader upload video.mkv sub.eng.srt --language en
```

## 🏛️ Arquitectura (hexagonal)

```
src/opensubtitles_uploader/
├── domain/        # reglas de negocio puras (sin frameworks ni I/O)
│   ├── model.py   # VideoFile, SubtitleFile, MovieRef, MediaInfo…
│   ├── files.py   # extensiones soportadas y heurísticas de subtítulos
│   ├── naming.py  # limpieza de títulos, detección SxxEyy
│   └── pairing.py # emparejamiento video ⇄ subtítulo
├── application/   # casos de uso + puertos (Protocols)
│   ├── ports.py   # OpenSubtitlesAuth/Catalog/Uploader, MediaProbe,
│   │              # FileHasher, LanguageDetector, SettingsStore, SecretStore…
│   └── services.py# AuthService, VideoService, SubtitleService,
│                  # CatalogService, UploadService
├── adapters/      # implementaciones concretas
│   ├── osapi/     # cliente híbrido: REST (catálogo/búsqueda) + XML-RPC (subida)
│   ├── media/     # hashing OSDb/MD5, probe mediainfo/ffprobe, detector de idioma
│   ├── storage/   # settings JSON + secretos (keychain/Fernet)
│   ├── ui/        # interfaz PySide6 (Qt)
│   └── cli/       # Typer + Rich
├── bootstrap.py   # raíz de composición: cablea adaptadores → núcleo
└── config.py      # rutas de datos de usuario (platformdirs) y entorno
```

### Cómo se conecta con OpenSubtitles

La API REST pública (`api.opensubtitles.com/api/v1`) no expone todavía un
endpoint de subida; el flujo real de subida (verificado en 2026) sigue
pasando por el XML-RPC heredado:

- **REST** (requiere `Api-Key` de <https://www.opensubtitles.com>): búsqueda
  de películas/series (`GET /features`), identificación por *moviehash*
  (`GET /subtitles?moviehash=…`), idiomas (`GET /infos/languages`).
- **XML-RPC** (`https://api.opensubtitles.org/xml-rpc`, solo usuario y
  contraseña): `LogIn` → `TryUploadSubtitles` (¿ya existe en la BD? +
  identificación de la película) → `UploadSubtitles` (`subcontent` =
  gzip sin cabecera + base64, tal y como espera el servicio).

Si OpenSubtitles publicara la subida en REST, solo habría que añadir un
adaptador nuevo sin tocar el núcleo (ventaja de los puertos).

- El **núcleo** (`domain` + `application`) no importa Qt, HTTP ni disco.
- Los **puertos** son `typing.Protocol`; los tests usan *fakes* en memoria.
- La **raíz de composición** (`bootstrap.py`) es el único lugar que junta
  adaptadores concretos y núcleo.
- Errores tipados (`AuthError`, `ApiError`, `UploadFailedError`…) que cada
  interfaz traduce a su propio mensaje.

### Skills aplicados

Este repositorio se construyó siguiendo los skills de
`.agents/skills/`: `python-hexagonal-architecture` (layout `src/`,
puertos/adaptadores, composición), `python-backend-design` (contratos en los
bordes, timeouts/retries, configuración 12-factor, logging estructurado),
`python-frontend-design` (tokens de diseño, estados loading/empty/error,
accesibilidad) y `python-security` (secretos nunca en texto plano, sin
`shell=True`, validación de entrada, TLS verificado).

## 🧪 Desarrollo

```bash
poetry run pytest                    # tests unitarios + integración
poetry run ruff check src tests      # linter
poetry run mypy src                  # chequeo estático estricto
poetry run bandit -r src             # análisis de seguridad estático
python scripts/verify_login.py       # verifica el login/APIs en vivo (usa .env)
```

Los tests de red reales (marcados `e2e`) están desactivados por defecto:
`poetry run pytest -m e2e` requiere credenciales/API key reales.  Para
probar el login contra el servicio real sin tocar los tests, cree un
archivo `.env` (ignorado por git) con `OPENSUBTITLES_USERNAME`,
`OPENSUBTITLES_PASSWORD` y `OPENSUBTITLES_API_KEY`, y ejecute
`python scripts/verify_login.py`.

## ⚠️ Avisos

- Esta aplicación **no es** OpenSubtitles: usa su API pública y depende de su
  disponibilidad.  Un error `503/506` suele significar mantenimiento o caída
  temporal del servicio.
- El hash MD5 de subtítulos se usa solo como huella de contenido (requisito
  del servicio); no se emplea para contraseñas.
- La clave de API y las credenciales se guardan en el almacén de secretos del
  sistema operativo cuando es posible; nunca en texto plano.

## 📄 Licencia

MIT — inspirado en
[vankasteelj/opensubtitles-uploader](https://github.com/vankasteelj/opensubtitles-uploader)
(GPL-3.0 original), reimplementado desde cero en Python.
