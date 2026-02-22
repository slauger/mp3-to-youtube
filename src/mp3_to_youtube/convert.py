"""
Convert MP3 files to MP4 videos (for YouTube uploads)
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from mutagen.id3 import ID3, APIC
from PIL import Image


class ConversionError(Exception):
    """Base exception for conversion errors"""
    pass


def check_ffmpeg_installed() -> bool:
    """Check if ffmpeg is installed and available"""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_image_dimensions(image_path: str) -> tuple[int, int]:
    """
    Get image dimensions

    Returns:
        Tuple of (width, height)
    """
    with Image.open(image_path) as img:
        return img.size


def is_landscape_or_16x9(image_path: str) -> bool:
    """
    Check if image is already suitable for YouTube (16:9 or landscape)

    Returns:
        True if image is 16:9 or wider, False if square/portrait
    """
    width, height = get_image_dimensions(image_path)
    aspect_ratio = width / height
    # 16:9 = 1.777..., allow some tolerance
    return aspect_ratio >= 1.7


def extract_cover_from_mp3(mp3_file: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Extract cover art from MP3 ID3 tags

    Args:
        mp3_file: Path to MP3 file
        output_path: Optional path to save cover (default: temp file)

    Returns:
        Path to extracted cover file, or None if no cover found
    """
    try:
        audio = ID3(mp3_file)

        # Find APIC (cover art) frame
        for tag in audio.values():
            if isinstance(tag, APIC):
                # Determine file extension from mime type
                ext = 'jpg'
                if tag.mime == 'image/png':
                    ext = 'png'
                elif tag.mime == 'image/gif':
                    ext = 'gif'

                # Save to output path or temp file
                if output_path:
                    cover_path = output_path
                else:
                    fd, cover_path = tempfile.mkstemp(suffix=f'.{ext}')
                    os.close(fd)

                with open(cover_path, 'wb') as f:
                    f.write(tag.data)

                return cover_path

        return None

    except Exception as e:
        raise ConversionError(f"Failed to extract cover art: {e}")


def build_ffmpeg_filter(
    cover_path: str,
    resolution: str = "1920x1080",
    background: str = "blur"
) -> str:
    """
    Build ffmpeg filter string based on image dimensions and background mode

    Args:
        cover_path: Path to cover image
        resolution: Target resolution (e.g., "1920x1080")
        background: Background mode: "blur", "black", or hex color (e.g., "#1a1a1a")

    Returns:
        FFmpeg filter string
    """
    width, height = resolution.split('x')
    target_w, target_h = int(width), int(height)

    # Check if image is already suitable
    if is_landscape_or_16x9(cover_path):
        # Just scale to target resolution
        return f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"

    # Image is square or portrait - need to add background
    img_w, img_h = get_image_dimensions(cover_path)

    if background == "blur":
        # Blurred background with centered image
        # Scale image to fit height, then overlay on blurred/scaled background
        return (
            f"[0:v]scale={target_w}:{target_h},boxblur=30:30[bg];"
            f"[0:v]scale=-1:{target_h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    elif background == "black":
        # Black bars (letterbox/pillarbox)
        return f"scale=-1:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        # Custom color (hex)
        color = background.lstrip('#')
        return f"scale=-1:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:#{color}"


def convert_mp3_to_mp4(
    mp3_file: str,
    output_file: Optional[str] = None,
    cover_file: Optional[str] = None,
    resolution: str = "1920x1080",
    background: str = "blur",
    overwrite: bool = False
) -> str:
    """
    Convert MP3 to MP4 video with static cover image

    Args:
        mp3_file: Path to input MP3 file
        output_file: Path to output MP4 file (default: same name with .mp4)
        cover_file: Path to cover image (if None, extracts from MP3)
        resolution: Video resolution (default: 1920x1080)
        background: Background mode for non-16:9 images: "blur", "black", or hex color
        overwrite: Overwrite existing output file

    Returns:
        Path to created MP4 file

    Raises:
        ConversionError: If conversion fails
    """
    if not check_ffmpeg_installed():
        raise ConversionError(
            "ffmpeg is not installed. Please install ffmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  Arch: sudo pacman -S ffmpeg"
        )

    mp3_path = Path(mp3_file)
    if not mp3_path.exists():
        raise ConversionError(f"Input file not found: {mp3_file}")

    # Determine output file
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = mp3_path.with_suffix('.mp4')

    if output_path.exists() and not overwrite:
        raise ConversionError(f"Output file already exists: {output_path}\nUse --overwrite to replace it")

    # Handle cover art
    temp_cover = None
    try:
        if cover_file:
            if not Path(cover_file).exists():
                raise ConversionError(f"Cover file not found: {cover_file}")
            cover_path = cover_file
        else:
            cover_path = extract_cover_from_mp3(str(mp3_path))
            if not cover_path:
                raise ConversionError(
                    "No cover art found in MP3 file.\n"
                    "Provide a cover image with --cover option"
                )
            temp_cover = cover_path

        # Build ffmpeg filter
        vf = build_ffmpeg_filter(cover_path, resolution, background)

        # Check if filter is complex (contains ;)
        use_filter_complex = ';' in vf

        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-loop', '1',
            '-framerate', '1',
            '-i', cover_path,
            '-i', str(mp3_path),
        ]

        if use_filter_complex:
            cmd.extend(['-filter_complex', vf])
        else:
            cmd.extend(['-vf', vf])

        cmd.extend([
            '-c:v', 'libx264',
            '-tune', 'stillimage',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            '-movflags', '+faststart',
        ])

        if overwrite:
            cmd.append('-y')

        cmd.append(str(output_path))

        # Run ffmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise ConversionError(f"ffmpeg failed:\n{result.stderr}")

        return str(output_path)

    finally:
        if temp_cover and Path(temp_cover).exists():
            try:
                os.unlink(temp_cover)
            except OSError:
                pass
