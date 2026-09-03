"""Minimal UI translation helper.

The default language is English (keys *are* the English strings).  An
optional Spanish catalogue provides translations; more languages can be
added without touching widgets.  Adapters (video/subtitle/API) are
expected to emit error *codes*; the UI maps them through ``tr_code``.
"""

from __future__ import annotations

LOCALES = ("en", "es")

# Key -> Spanish translation.
_ES: dict[str, str] = {
    # Top bar & login
    "Upload": "Subir",
    "Log in": "Iniciar sesión",
    "Log in above with your opensubtitles.org account to upload.": "Inicia sesión arriba con tu cuenta de opensubtitles.org para subir.",
    "Log out": "Cerrar sesión",
    "Uploads need a legacy opensubtitles.org account — this opensubtitles.com login works for search but not for uploading.": "La subida requiere una cuenta heredada de opensubtitles.org — este login de opensubtitles.com sirve para buscar, pero no para subir.",
    "Username": "Usuario",
    "Password": "Contraseña",
    "Settings": "Ajustes",
    "Remember me": "Recordarme",
    # Panels
    "Video file": "Archivo de video",
    "Subtitle file": "Archivo de subtítulos",
    "Drop a video file or select one": "Suelta un archivo de video o selecciónalo",
    "Drop a subtitle file or select one": "Suelta un archivo de subtítulos o selecciónalo",
    "browse": "examinar",
    "Reset": "Restablecer",
    "File name": "Nombre de archivo",
    "OSDb Hash": "Hash OSDb",
    "MD5 Hash": "Hash MD5",
    "Size": "Tamaño",
    "bytes": "bytes",
    "IMDB id": "ID de IMDB",
    "High definition": "Alta definición",
    "Movie AKA": "Título alternativo (AKA)",
    "Release name": "Nombre del release",
    "FPS": "FPS",
    "Total time": "Duración total",
    "ms": "ms",
    "Number of frames": "Número de fotogramas",
    "Language": "Idioma",
    "None": "Ninguno",
    "Translator": "Traductor",
    "Comment": "Comentario",
    "Hearing impaired": "Para sordos (sonidos)",
    "Auto-translated": "Traducción automática",
    "Foreign parts only": "Solo partes extranjeras",
    "Detected title": "Título detectado",
    "Auto-detect the language": "Detectar idioma automáticamente",
    "Save between sessions": "Guardar entre sesiones",
    "Search on IMDB directly": "Buscar directamente en IMDB",
    "Replace the currently loaded file with the detected one": "¿Reemplazar el archivo cargado por el detectado?",
    "Yes": "Sí",
    "No": "No",
    "OK": "Aceptar",
    "Edit": "Editar",
    "Upload now": "Subir ahora",
    "Retry": "Reintentar",
    "Open in browser": "Abrir en el navegador",
    "Close": "Cerrar",
    # Status / toasts
    "Analysing video…": "Analizando video…",
    "Analysing subtitle…": "Analizando subtítulos…",
    "Identifying movie…": "Identificando película…",
    "Searching…": "Buscando…",
    "Uploading…": "Subiendo…",
    "Video imported": "Video importado",
    "Subtitle imported": "Subtítulos importados",
    "Logged in as": "Sesión iniciada como",
    "Welcome": "Bienvenido",
    "Dropped file is not supported": "El archivo soltado no es compatible",
    "Subtitle was successfully uploaded!": "¡Subtítulo subido correctamente!",
    "Subtitle was already present in the database": "El subtítulo ya estaba en la base de datos",
    "The hash has been added!": "¡El hash se ha añadido!",
    "The file name has been added!": "¡El nombre de archivo se ha añadido!",
    "Open in OpenSubtitles": "Abrir en OpenSubtitles",
    "Open IMDB page": "Abrir página de IMDB",
    # Search dialog
    "Enter a title": "Escribe un título",
    "Search account:": "Cuenta de búsqueda:",
    "log in above with your upload account to submit subtitles.": "inicia sesión arriba con tu cuenta de subida para enviar subtítulos.",
    "Upload account — opensubtitles.org credentials. The .env (opensubtitles.com) account is used only for metadata/search.": "Cuenta de subida — credenciales de opensubtitles.org. La cuenta del .env (opensubtitles.com) se usa solo para metadatos/búsqueda.",
    "Search is ready (API key). Log in with your upload account to submit subtitles.": "Búsqueda lista (API key). Inicia sesión con tu cuenta de subida para enviar subtítulos.",
    "Configure an OpenSubtitles API key (⚙) to enable movie search.": "Configura una clave de API de OpenSubtitles (⚙) para buscar películas.",
    "Metadata/search account": "Cuenta de metadatos/búsqueda",
    "Upload account": "Cuenta de subida",
    "the account you log in with in the main window": "la cuenta con la que inicias sesión en la ventana principal",
    "not set — catalogue works with the API key alone (.env)": "no configurada — el catálogo funciona solo con la API key (.env)",
    "Search": "Buscar",
    "Not found": "No encontrado",
    "Search results": "Resultados de la búsqueda",
    "Choose": "Elegir",
    # Settings dialog
    "Theme": "Tema",
    "Dark": "Oscuro",
    "Light": "Claro",
    "Application language": "Idioma de la aplicación",
    "OpenSubtitles API key": "Clave de API de OpenSubtitles",
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Advanced": "Avanzado",
    "Media info tools": "Herramientas de metadatos",
    "mediainfo / ffprobe not found — fps, duration and frame count will be empty.": "No se encontró mediainfo/ffprobe: fps, duración y fotogramas quedarán vacíos.",
    "Check for updates": "Buscar actualizaciones",
    "Keyboard shortcuts": "Atajos de teclado",
    "Import file(s)": "Importar archivo(s)",
    "Clear file(s)": "Limpiar archivo(s)",
    "Next field": "Campo siguiente",
    "Close popup(s)": "Cerrar ventanas",
    "About": "Acerca de",
    "developed by": "desarrollado por",
    "Report an issue": "Informar de un problema",
    # Error / info codes (also emitted by the core)
    "file_not_supported": "El tipo de archivo no es compatible.",
    "file_not_found": "No se encontró el archivo.",
    "file_too_small": "El archivo es demasiado pequeño para calcular el hash.",
    "username_required": "Introduce un usuario.",
    "password_required": "Introduce una contraseña.",
    "auth_error": "Usuario o contraseña incorrectos.",
    "auth_required": "Inicia sesión en OpenSubtitles primero.",
    "upload_account_required": "La subida requiere iniciar sesión con una cuenta heredada de opensubtitles.org.",
    "language_required": "Selecciona el idioma del subtítulo antes de subir.",
    "imdb_id_required": "El video no tiene ID de IMDB. Se recomienda identificarlo para clasificar bien el subtítulo.",
    "imdb_id_invalid": "El ID de IMDB no es válido.",
    "search_query_required": "Escribe un título para buscar.",
    "upload_failed": "No se pudo subir el subtítulo.",
    "service_unavailable": "OpenSubtitles no está disponible ahora. Inténtalo más tarde.",
    "network_error": "No se pudo conectar con OpenSubtitles.",
    "api_key_required": "Configura una clave de API de OpenSubtitles en Ajustes (⚙) para usar esta función.",
    "api_error": "OpenSubtitles devolvió un error.",
    "rate_limited": "Demasiadas peticiones a OpenSubtitles. Espera un momento y reintenta.",
    "forbidden": "OpenSubtitles rechazó la petición (revisa tu clave/API o cuenta).",
    "not_found": "No encontrado.",
    "invalid_input": "OpenSubtitles rechazó los datos enviados.",
    "already_exists": "El subtítulo ya existe.",
    "generic_error": "Algo salió mal :(",
    "ok": "Hecho",
    "cookie_policy": "Al usar la API aceptas la política de OpenSubtitles.",
    # Startup check (main.py)
    "Startup check": "Comprobación de inicio",
    "The application will close.": "La aplicación se cerrará.",
    "unknown error.": "error desconocido.",
    "The metadata account is missing: create a .env file with OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD (opensubtitles.com credentials).": "Falta la cuenta de metadatos: crea un archivo .env con OPENSUBTITLES_USERNAME y OPENSUBTITLES_PASSWORD (credenciales de opensubtitles.com).",
    "Put the .env file next to the application (or export OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD and OPENSUBTITLES_API_KEY as environment variables).": "Coloca el archivo .env junto a la aplicación (o exporta OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD y OPENSUBTITLES_API_KEY como variables de entorno).",
    "The OpenSubtitles API key is missing: set OPENSUBTITLES_API_KEY (opensubtitles.com) to validate the metadata account.": "Falta la clave de API de OpenSubtitles: define OPENSUBTITLES_API_KEY (opensubtitles.com) para validar la cuenta de metadatos.",
    "The metadata account could not be validated against opensubtitles.com:": "La cuenta de metadatos no pudo validarse contra opensubtitles.com:",
}


# Error codes -> human messages (English reference).
_EN_CODES: dict[str, str] = {
    "auth_error": "Wrong username or password.",
    "auth_required": "Log in to OpenSubtitles first.",
    "upload_account_required": (
        "Uploading needs a legacy opensubtitles.org account — this "
        "opensubtitles.com login works for search but not for uploading."
    ),
    "api_key_required": "Set an OpenSubtitles API key in Settings (⚙) to use this feature.",
    "api_error": "OpenSubtitles returned an error.",
    "network_error": "Cannot reach OpenSubtitles. Check your connection and try again.",
    "rate_limited": "Too many requests to OpenSubtitles. Wait a moment and retry.",
    "service_unavailable": "OpenSubtitles is temporarily unavailable. Try again later.",
    "forbidden": "OpenSubtitles refused the request (check your API key / account).",
    "not_found": "Not found.",
    "invalid_input": "OpenSubtitles rejected the request data.",
    "upload_failed": "The subtitle could not be uploaded.",
    "username_required": "Enter your username.",
    "password_required": "Enter your password.",
    "language_required": "Choose the subtitle language before uploading.",
    "file_not_supported": "This file type is not supported.",
    "file_not_found": "The file was not found.",
    "file_too_small": "The file is too small to compute a movie hash.",
    "imdb_id_required": "The video has no IMDB id. Identify the movie to classify the subtitle correctly.",
    "imdb_id_invalid": "The IMDB id is not valid.",
    "search_query_required": "Type a title to search.",
    "generic_error": "Something went wrong.",
}


class Translator:
    """Thread-unsafe; created once per locale and used from the GUI thread."""

    def __init__(self, locale: str = "en") -> None:
        self.locale = locale if locale in LOCALES else "en"

    def tr(self, text: str) -> str:
        if self.locale == "es":
            return _ES.get(text, text)
        return text

    def tr_code(self, code: str, fallback: str | None = None) -> str:
        if self.locale == "es":
            translated = _ES.get(code)
            if translated:
                return translated
        else:
            translated = _EN_CODES.get(code)
            if translated:
                return translated
        return fallback or code
