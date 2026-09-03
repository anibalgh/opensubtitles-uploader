"""File classification rules (pure domain constants)."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".3g2",
        ".3gp",
        ".3gp2",
        ".3gpp",
        ".60d",
        ".ajp",
        ".asf",
        ".asx",
        ".avchd",
        ".avi",
        ".bik",
        ".bix",
        ".box",
        ".cam",
        ".dat",
        ".divx",
        ".dmf",
        ".dv",
        ".dvr-ms",
        ".evo",
        ".flc",
        ".fli",
        ".flic",
        ".flv",
        ".flx",
        ".gvi",
        ".gvp",
        ".h264",
        ".m1v",
        ".m2p",
        ".m2ts",
        ".m2v",
        ".m4e",
        ".m4v",
        ".mjp",
        ".mjpeg",
        ".mjpg",
        ".mkv",
        ".moov",
        ".mov",
        ".movhd",
        ".movie",
        ".movx",
        ".mp4",
        ".mpe",
        ".mpeg",
        ".mpg",
        ".mpv",
        ".mpv2",
        ".mxf",
        ".nsv",
        ".nut",
        ".ogg",
        ".ogm",
        ".omf",
        ".ps",
        ".qt",
        ".ram",
        ".rm",
        ".rmvb",
        ".swf",
        ".ts",
        ".vfw",
        ".vid",
        ".video",
        ".viv",
        ".vivo",
        ".vob",
        ".vro",
        ".wm",
        ".wmv",
        ".wmx",
        ".wrap",
        ".wvx",
        ".wx",
        ".x264",
        ".xvid",
    }
)

SUPPORTED_SUBTITLE_EXTENSIONS: frozenset[str] = frozenset(
    {".srt", ".sub", ".smi", ".txt", ".ssa", ".ass", ".mpl"}
)

ALL_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_SUBTITLE_EXTENSIONS
)

# Extensions allowed in the native file dialogs, joined for filters.
VIDEO_DIALOG_PATTERN = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS))
SUBTITLE_DIALOG_PATTERN = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_SUBTITLE_EXTENSIONS))

# Machine-translation markers looked for in subtitle file names / contents.
_MACHINE_TRANSLATION_MARKERS: tuple[tuple[str, str], ...] = (
    ("auto", "translated"),
    ("babel", "fish"),
    ("google", "translate"),
    ("bing", "translation"),
)

# "Foreign parts only" markers found in subtitle file names.
_FOREIGN_ONLY_MARKERS: tuple[str, ...] = (
    "forced",
    "foreign",
)

# Content threshold under which a subtitle is assumed to be foreign-only.
FOREIGN_ONLY_MAX_SIZE = 5_000

# Number of parenthesis groups beyond which a subtitle is assumed to
# contain sound descriptions (hearing impaired).
HEARING_IMPAIRED_PARENTHESIS_THRESHOLD = 10


def classify_file(path: str | Path) -> str | None:
    """Return ``"video"``, ``"subtitle"`` or ``None`` (unsupported)."""
    ext = Path(path).suffix.lower()
    if ext in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    if ext in SUPPORTED_SUBTITLE_EXTENSIONS:
        return "subtitle"
    return None


def has_machine_translation_markers(text: str) -> bool:
    lowered = text.lower()
    return any(a in lowered and b in lowered for a, b in _MACHINE_TRANSLATION_MARKERS)


def has_foreign_only_markers(filename: str) -> bool:
    """Detect 'foreign parts only' markers, mirroring the original app.

    E.g. ``Movie.forced.srt`` or ``Movie (foreign parts).srt``.
    """
    lowered = filename.lower().replace("_", " ")
    return (
        "forced" in lowered
        or ("non-english" in lowered and "parts" in lowered)
        or ("foreign" in lowered and "non-foreign" not in lowered)
    )


def likely_hearing_impaired(content: str) -> bool:
    """More than N parenthesis groups usually means sound descriptions.

    Counts the number of *separate* parenthetical groups, e.g.
    ``(music playing)`` — not nesting depth.
    """
    if not content:
        return False
    groups = 0
    depth = 0
    for ch in content:
        if ch == "(":
            if depth == 0:
                groups += 1
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
    return groups > HEARING_IMPAIRED_PARENTHESIS_THRESHOLD
