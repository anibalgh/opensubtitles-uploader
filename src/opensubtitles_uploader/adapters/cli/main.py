"""Typer/Rich command-line interface — same core as the GUI."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from opensubtitles_uploader.bootstrap import bootstrap
from opensubtitles_uploader.domain.errors import DomainError

app = typer.Typer(
    name="opensubtitles-uploader",
    help="Analyse local videos and upload their subtitles to OpenSubtitles.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
_context = bootstrap


def _err(message: str) -> None:
    console.print(f"[red]✗ {message}[/red]")
    raise typer.Exit(code=1)


@app.command()
def login(
    username: str = typer.Option(..., prompt=True, help="OpenSubtitles username"),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=False, help="Password"
    ),
    remember: bool = typer.Option(True, help="Store credentials in the OS keychain"),
) -> None:
    """Log in with your opensubtitles.org (upload) account."""
    ctx = _context()
    user = ctx.auth.login(username, password, remember=remember)
    console.print(f"[green]✓ Logged in as {user.username} (level: {user.level or 'user'})[/green]")


@app.command()
def logout() -> None:
    """Forget the stored credentials."""
    ctx = _context()
    ctx.auth.logout()
    console.print("[yellow]Logged out.[/yellow]")


@app.command()
def whoami() -> None:
    """Show the current logged-in user."""
    ctx = _context()
    user = ctx.client.whoami()
    console.print(f"[green]{user.username}[/green] — {user.level} (VIP: {user.vip})")


@app.command()
def analyze(
    file: Path = typer.Argument(..., exists=True, help="Video or subtitle file"),
) -> None:
    """Analyse a video (hash + media info + movie id) or a subtitle."""
    ctx = _context()
    from opensubtitles_uploader.domain.files import classify_file

    kind = classify_file(file)
    if kind == "video":
        video = ctx.videos.analyze(file)
        identified = ctx.videos.identify(video)
        movie = identified.movie
        table = Table(title=f"Video — {identified.name}")
        table.add_column("Property")
        table.add_column("Value")
        table.add_row("Moviehash", identified.os_hash)
        table.add_row("Size (bytes)", str(identified.size_bytes))
        if identified.media.duration_ms:
            table.add_row("Duration (ms)", str(identified.media.duration_ms))
        if identified.media.frame_rate:
            table.add_row("FPS", str(identified.media.frame_rate))
        if identified.media.frame_count:
            table.add_row("Frames", str(identified.media.frame_count))
        table.add_row("Resolution", f"{identified.media.width}x{identified.media.height}")
        table.add_row("High definition", str(identified.hd))
        table.add_row(
            "Movie",
            f"{movie.title} ({movie.year}) [{movie.imdb_id}]" if movie else "—",
        )
        console.print(table)
    elif kind == "subtitle":
        sub = ctx.subtitles.analyze(file)
        table = Table(title=f"Subtitle — {sub.name}")
        table.add_column("Property")
        table.add_column("Value")
        table.add_row("MD5", sub.md5)
        table.add_row("Size (bytes)", str(sub.size_bytes))
        table.add_row(
            "Language",
            sub.language.display() if sub.language else "not detected",
        )
        table.add_row("Hearing impaired", str(sub.hearing_impaired))
        table.add_row("Machine translated", str(sub.machine_translated))
        table.add_row("Foreign parts only", str(sub.foreign_parts_only))
        console.print(table)
    else:
        _err("Unsupported file type.")


@app.command()
def search(
    query: str = typer.Argument(..., help="Movie / show / episode title"),
    limit: int = typer.Option(10, help="Maximum number of results"),
) -> None:
    """Search movies/shows/episodes (fills the IMDB id)."""
    ctx = _context()
    try:
        results = ctx.catalog.search(query)[:limit]
    except DomainError as exc:
        _err(exc.message)
    if not results:
        _err("Not found.")
    table = Table(title=f"Results for “{query}”")
    table.add_column("IMDB")
    table.add_column("Title")
    table.add_column("Year")
    for movie in results:
        table.add_row(movie.imdb_id, movie.display_title(), str(movie.year or ""))
    console.print(table)


@app.command()
def upload(
    video: Path = typer.Argument(..., exists=True, help="Video file"),
    subtitle: Path = typer.Argument(..., exists=True, help="Subtitle file"),
    language: str = typer.Option(
        None, help="Subtitle language (ISO code, e.g. en/es/fr) — auto-detected when omitted"
    ),
    release_name: str | None = typer.Option(None, help="Release name"),
    translator: str | None = typer.Option(None, help="Translator"),
    comment: str | None = typer.Option(None, help="Comment for the subtitle"),
) -> None:
    """Analyse video + subtitle and upload the subtitle."""
    ctx = _context()

    analysed_video = ctx.videos.analyze(video)
    analysed_video = ctx.videos.identify(analysed_video)
    sub = ctx.subtitles.analyze(subtitle)

    selected_language = sub.language
    if language:
        from opensubtitles_uploader.adapters.media.dataset import language_by_tag

        selected_language = language_by_tag(language)

    if not selected_language:
        _err("Could not detect the subtitle language; pass --language en|es|fr…")

    from opensubtitles_uploader.application.services import build_upload_request

    request = build_upload_request(
        analysed_video,
        sub,
        language=selected_language,
        release_name=release_name or "",
        translator=translator or "",
        comment=comment or "",
    )
    movie = analysed_video.movie
    if movie is None:
        console.print("[yellow]No movie identified; continuing without an IMDB id.[/yellow]")
    else:
        console.print(f"[cyan]Identified: {movie.display_title()} ({movie.imdb_id})[/cyan]")
    outcome = ctx.uploads.upload(request)
    if outcome.succeeded:
        console.print(f"[green]✓ {outcome.url or 'Uploaded'}[/green]")
    else:
        console.print(
            f"[yellow]Already in the database: {len(outcome.existing)} match(es).[/yellow]"
        )
        for match in outcome.existing:
            where = ", ".join(match.matched_by) or "hash"
            link = match.url or match.subtitle_id
            console.print(f"  • {link} ({where})")


def main() -> None:  # pragma: no cover - entry point
    try:
        app()
    except DomainError as exc:
        _err(exc.message)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
