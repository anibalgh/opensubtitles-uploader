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
    "Log out": "Cerrar sesión",
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
    "language_required": "Selecciona el idioma del subtítulo antes de subir.",
    "imdb_id_required": "El video no tiene ID de IMDB. Se recomienda identificarlo para clasificar bien el subtítulo.",
    "imdb_id_invalid": "El ID de IMDB no es válido.",
    "search_query_required": "Escribe un título para buscar.",
    "upload_failed": "No se pudo subir el subtítulo.",
    "service_unavailable": "OpenSubtitles no está disponible ahora. Inténtalo más tarde.",
    "network_error": "No se pudo conectar con OpenSubtitles.",
    "api_error": "OpenSubtitles devolvió un error.",
    "already_exists": "El subtítulo ya existe.",
    "generic_error": "Algo salió mal :(",
    "ok": "Hecho",
    "cookie_policy": "Al usar la API aceptas la política de OpenSubtitles.",
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
        translated = self.tr(code)
        if translated != code:
            return translated
        return fallback or code
