"""
CLI interface for mp3-to-youtube
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .convert import convert_mp3_to_mp4, ConversionError, check_ffmpeg_installed
from .youtube import (
    upload_video, set_thumbnail, init_auth,
    YouTubeError, check_youtube_available
)
from .metadata import load_metadata, resolve_paths, build_description, create_template, MetadataError

console = Console()


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
def cli():
    """
    mp3-to-youtube: Convert MP3 files to YouTube-ready videos and upload them

    \b
    Quick start:
      1. mp3-to-youtube auth --client-secrets path/to/client_secrets.json
      2. mp3-to-youtube publish song.mp3 --title "My Song"

    \b
    Or with metadata file:
      1. mp3-to-youtube template -o publish.json
      2. Edit publish.json with your details
      3. mp3-to-youtube publish --metadata publish.json
    """
    pass


@cli.command()
@click.argument('mp3_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output MP4 file path')
@click.option('--cover', '-c', type=click.Path(exists=True), help='Cover image (default: extract from MP3)')
@click.option('--resolution', '-r', default='1920x1080', help='Video resolution (default: 1920x1080)')
@click.option('--background', '-b', default='blur',
              help='Background for non-16:9 images: blur, black, or hex color (default: blur)')
@click.option('--overwrite', is_flag=True, help='Overwrite existing output file')
def convert(
    mp3_file: str,
    output: Optional[str],
    cover: Optional[str],
    resolution: str,
    background: str,
    overwrite: bool
):
    """
    Convert MP3 to MP4 video with cover image

    \b
    Examples:
      mp3-to-youtube convert song.mp3
      mp3-to-youtube convert song.mp3 -o video.mp4 -c cover.jpg
      mp3-to-youtube convert song.mp3 --background black
      mp3-to-youtube convert song.mp3 --background "#1a1a2e"
    """
    if not check_ffmpeg_installed():
        console.print("[red]Error: ffmpeg not installed[/red]")
        console.print("Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        sys.exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Converting MP3 to MP4...", total=None)

            output_file = convert_mp3_to_mp4(
                mp3_file=mp3_file,
                output_file=output,
                cover_file=cover,
                resolution=resolution,
                background=background,
                overwrite=overwrite
            )

        console.print(f"[green]✓[/green] Created: {output_file}")

    except ConversionError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('video_file', type=click.Path(exists=True))
@click.option('--title', '-t', required=True, help='Video title (max 100 chars)')
@click.option('--description', '-d', help='Video description')
@click.option('--tags', help='Comma-separated tags')
@click.option('--category', default='music', help='Category: music, gaming, education, etc. (default: music)')
@click.option('--privacy', '-p', type=click.Choice(['public', 'private', 'unlisted']),
              default='private', help='Privacy setting (default: private)')
@click.option('--thumbnail', type=click.Path(exists=True), help='Custom thumbnail image')
@click.option('--made-for-kids', is_flag=True, help='Mark as made for kids (COPPA)')
def upload(
    video_file: str,
    title: str,
    description: Optional[str],
    tags: Optional[str],
    category: str,
    privacy: str,
    thumbnail: Optional[str],
    made_for_kids: bool
):
    """
    Upload MP4 video to YouTube

    \b
    Examples:
      mp3-to-youtube upload video.mp4 -t "My Song" -p unlisted
      mp3-to-youtube upload video.mp4 -t "My Song" --tags "music,ai,suno"
    """
    if not check_youtube_available():
        console.print("[red]Error: YouTube API dependencies not installed[/red]")
        console.print("Install with: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    tag_list = [t.strip() for t in tags.split(',')] if tags else None

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Uploading to YouTube...", total=100)

            def on_progress(percent):
                progress.update(task, completed=percent)

            result = upload_video(
                video_file=video_file,
                title=title,
                description=description,
                tags=tag_list,
                category=category,
                privacy=privacy,
                made_for_kids=made_for_kids,
                progress_callback=on_progress
            )

        console.print(f"\n[green]✓[/green] Uploaded: {result['title']}")
        console.print(f"[green]✓[/green] URL: {result['url']}")
        console.print(f"[dim]Privacy: {result['privacy']}[/dim]")

        # Set thumbnail if provided
        if thumbnail:
            try:
                set_thumbnail(result['id'], thumbnail)
                console.print(f"[green]✓[/green] Thumbnail set")
            except YouTubeError as e:
                console.print(f"[yellow]Warning: Could not set thumbnail: {e}[/yellow]")

    except YouTubeError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('mp3_file', type=click.Path(exists=True), required=False)
@click.option('--metadata', '-m', type=click.Path(exists=True), help='Metadata JSON/YAML file')
@click.option('--title', '-t', help='Video title (overrides metadata)')
@click.option('--description', '-d', help='Video description (overrides metadata)')
@click.option('--tags', help='Comma-separated tags (overrides metadata)')
@click.option('--cover', '-c', type=click.Path(exists=True), help='Cover image (overrides metadata)')
@click.option('--category', default='music', help='Category (default: music)')
@click.option('--privacy', '-p', type=click.Choice(['public', 'private', 'unlisted']),
              default='private', help='Privacy setting (default: private)')
@click.option('--background', '-b', default='blur', help='Background mode: blur, black, or hex color')
@click.option('--keep-video', is_flag=True, help='Keep the intermediate MP4 file')
@click.option('--video-only', is_flag=True, help='Only create video, do not upload')
@click.option('--thumbnail', type=click.Path(exists=True), help='Custom thumbnail image (overrides metadata)')
def publish(
    mp3_file: Optional[str],
    metadata: Optional[str],
    title: Optional[str],
    description: Optional[str],
    tags: Optional[str],
    cover: Optional[str],
    category: str,
    privacy: str,
    background: str,
    keep_video: bool,
    video_only: bool,
    thumbnail: Optional[str]
):
    """
    Convert MP3 and upload to YouTube in one step

    \b
    Examples:
      # Quick publish with title
      mp3-to-youtube publish song.mp3 -t "My Song" -p unlisted

      # From metadata file
      mp3-to-youtube publish --metadata publish.json

      # Metadata file with overrides
      mp3-to-youtube publish --metadata publish.json -t "New Title" -p public
    """
    # Load metadata if provided
    meta = {}
    base_dir = Path.cwd()

    if metadata:
        try:
            meta = load_metadata(metadata)
            base_dir = Path(metadata).parent
            meta = resolve_paths(meta, base_dir)
        except MetadataError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    # Determine MP3 file
    audio_file = mp3_file or meta.get('audio')
    if not audio_file:
        console.print("[red]Error: No MP3 file specified[/red]")
        console.print("Provide MP3_FILE argument or 'audio' field in metadata")
        sys.exit(1)

    if not Path(audio_file).exists():
        console.print(f"[red]Error: Audio file not found: {audio_file}[/red]")
        sys.exit(1)

    # Determine title
    final_title = title or meta.get('title')
    if not final_title and not video_only:
        console.print("[red]Error: No title specified[/red]")
        console.print("Use --title or add 'title' field in metadata")
        sys.exit(1)

    # Determine other fields
    final_cover = cover or meta.get('cover')
    final_description = description or meta.get('description', '')
    final_tags = [t.strip() for t in tags.split(',')] if tags else meta.get('tags')
    final_category = category or meta.get('category', 'music')
    final_privacy = privacy or meta.get('privacy', 'private')
    final_thumbnail = thumbnail or meta.get('thumbnail')
    made_for_kids = meta.get('madeForKids', False)

    # Resolve thumbnail path if relative
    if final_thumbnail and not Path(final_thumbnail).is_absolute():
        final_thumbnail = str(base_dir / final_thumbnail)

    # Check dependencies
    if not check_ffmpeg_installed():
        console.print("[red]Error: ffmpeg not installed[/red]")
        sys.exit(1)

    if not video_only and not check_youtube_available():
        console.print("[red]Error: YouTube API dependencies not installed[/red]")
        sys.exit(1)

    try:
        # Step 1: Convert
        console.print(f"[bold]Converting:[/bold] {Path(audio_file).name}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Converting MP3 to MP4...", total=None)

            video_file_path = convert_mp3_to_mp4(
                mp3_file=audio_file,
                cover_file=final_cover,
                background=background,
                overwrite=True
            )

        console.print(f"[green]✓[/green] Video created: {video_file_path}")

        if video_only:
            console.print(f"\n[bold green]Done![/bold green] Video saved to: {video_file_path}")
            return

        # Step 2: Upload
        console.print(f"\n[bold]Uploading:[/bold] {final_title}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Uploading to YouTube...", total=100)

            def on_progress(percent):
                progress.update(task, completed=percent)

            result = upload_video(
                video_file=video_file_path,
                title=final_title,
                description=final_description,
                tags=final_tags,
                category=final_category,
                privacy=final_privacy,
                made_for_kids=made_for_kids,
                progress_callback=on_progress
            )

        console.print(f"\n[bold green]Published![/bold green]")
        console.print(f"[green]✓[/green] Title: {result['title']}")
        console.print(f"[green]✓[/green] URL: {result['url']}")
        console.print(f"[dim]Privacy: {result['privacy']}[/dim]")

        # Set thumbnail if provided
        if final_thumbnail:
            try:
                set_thumbnail(result['id'], final_thumbnail)
                console.print(f"[green]✓[/green] Thumbnail set")
            except YouTubeError as e:
                console.print(f"[yellow]Warning: Could not set thumbnail: {e}[/yellow]")

        # Cleanup
        if not keep_video:
            Path(video_file_path).unlink()
            console.print(f"[dim]Cleaned up temporary video file[/dim]")

    except (ConversionError, YouTubeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--client-secrets', type=click.Path(exists=True),
              help='Path to OAuth2 client secrets JSON file')
def auth(client_secrets: Optional[str]):
    """
    Set up YouTube authentication

    \b
    First time setup:
      1. Go to https://console.cloud.google.com/
      2. Create a project and enable YouTube Data API v3
      3. Create OAuth 2.0 credentials (Desktop app)
      4. Download the client secrets JSON
      5. Run: mp3-to-youtube auth --client-secrets path/to/file.json

    After setup, you can upload videos without re-authenticating.
    """
    if not check_youtube_available():
        console.print("[red]Error: YouTube API dependencies not installed[/red]")
        console.print("Install with: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    try:
        console.print("[bold]Setting up YouTube authentication...[/bold]")
        console.print("[dim]A browser window will open for authentication[/dim]\n")

        result = init_auth(client_secrets)

        console.print(f"[green]✓[/green] Authenticated successfully!")
        console.print(f"[green]✓[/green] Channel: {result['channel_title']}")
        console.print(f"[dim]Token saved to: {result['token_file']}[/dim]")

    except YouTubeError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', default='publish.json', help='Output file path (default: publish.json)')
@click.option('--audio', '-a', help='Audio file to reference in template')
def template(output: str, audio: Optional[str]):
    """
    Create a template publish.json file

    \b
    Example:
      mp3-to-youtube template -o my-song.json -a song.mp3
    """
    try:
        create_template(output, audio)
        console.print(f"[green]✓[/green] Created template: {output}")
        console.print(f"[dim]Edit the file and run: mp3-to-youtube publish --metadata {output}[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    cli()
