# mp3-to-youtube

Convert MP3 files to YouTube-ready videos and upload them.

## Features

- Convert MP3 + cover image to MP4 video
- Automatic 16:9 conversion with blur/black background for square covers
- Extract cover art from MP3 ID3 tags
- Upload to YouTube with title, description, tags
- Metadata file support (JSON/YAML)

## Requirements

- Python 3.10+
- FFmpeg (`brew install ffmpeg` or `apt install ffmpeg`)

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Set up YouTube authentication

```bash
# Get OAuth credentials from Google Cloud Console
# https://console.cloud.google.com/ -> APIs & Services -> Credentials

mp3-to-youtube auth --client-secrets path/to/client_secrets.json
```

### 2. Publish a song

```bash
# Simple: MP3 with embedded cover
mp3-to-youtube publish song.mp3 -t "My Song" -p unlisted

# With separate cover image
mp3-to-youtube publish song.mp3 -t "My Song" -c cover.jpg -p unlisted

# From metadata file
mp3-to-youtube publish --metadata publish.json
```

## Commands

### `convert` - MP3 to MP4

```bash
mp3-to-youtube convert song.mp3
mp3-to-youtube convert song.mp3 -c cover.jpg -o video.mp4
mp3-to-youtube convert song.mp3 --background black
mp3-to-youtube convert song.mp3 --background "#1a1a2e"
```

### `upload` - Upload to YouTube

```bash
mp3-to-youtube upload video.mp4 -t "My Song" -p unlisted
mp3-to-youtube upload video.mp4 -t "My Song" --tags "music,ai"
```

### `publish` - Convert + Upload

```bash
mp3-to-youtube publish song.mp3 -t "My Song"
mp3-to-youtube publish --metadata publish.json
mp3-to-youtube publish song.mp3 -t "My Song" --video-only  # No upload
```

### `template` - Create metadata template

```bash
mp3-to-youtube template -o publish.json
```

## Metadata File Format

```json
{
  "title": "Song Title",
  "description": "Video description",
  "tags": ["music", "ai"],
  "category": "music",
  "privacy": "unlisted",
  "madeForKids": false,

  "audio": "song.mp3",
  "cover": "cover.jpg",

  "source": {
    "generator": "suno-cli",
    "style": "pop, upbeat"
  }
}
```

## Background Modes

For non-16:9 cover images (e.g., square Suno covers):

| Mode | Description |
|------|-------------|
| `blur` | Blurred version of cover as background (default) |
| `black` | Black bars (letterbox) |
| `#hex` | Custom color, e.g., `#1a1a2e` |

## License

MIT
