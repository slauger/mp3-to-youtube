"""
Metadata handling for publish.json files
"""

import json
from pathlib import Path
from typing import Any, Optional

import yaml


class MetadataError(Exception):
    """Base exception for metadata errors"""
    pass


def load_metadata(metadata_file: str) -> dict[str, Any]:
    """
    Load metadata from JSON or YAML file

    Expected format:
        {
            "title": "Song Title",
            "description": "Video description",
            "tags": ["tag1", "tag2"],
            "category": "music",
            "privacy": "unlisted",
            "madeForKids": false,

            "audio": "song.mp3",
            "cover": "cover.jpg",

            "source": {
                "generator": "suno-cli",
                "taskId": "abc123",
                ...
            }
        }

    Args:
        metadata_file: Path to JSON or YAML file

    Returns:
        Metadata dict
    """
    path = Path(metadata_file)

    if not path.exists():
        raise MetadataError(f"Metadata file not found: {metadata_file}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if path.suffix.lower() in ['.yaml', '.yml']:
            data = yaml.safe_load(content)
        else:
            data = json.load(open(path, encoding='utf-8'))

        return data

    except json.JSONDecodeError as e:
        raise MetadataError(f"Invalid JSON in {metadata_file}: {e}")
    except yaml.YAMLError as e:
        raise MetadataError(f"Invalid YAML in {metadata_file}: {e}")
    except Exception as e:
        raise MetadataError(f"Failed to load {metadata_file}: {e}")


def resolve_paths(metadata: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """
    Resolve relative paths in metadata to absolute paths

    Args:
        metadata: Metadata dict
        base_dir: Base directory for relative paths

    Returns:
        Metadata with resolved paths
    """
    result = metadata.copy()

    # Resolve audio path
    if 'audio' in result:
        audio_path = Path(result['audio'])
        if not audio_path.is_absolute():
            result['audio'] = str(base_dir / audio_path)

    # Resolve cover path
    if 'cover' in result:
        cover_path = Path(result['cover'])
        if not cover_path.is_absolute():
            result['cover'] = str(base_dir / cover_path)

    return result


def build_description(
    description: Optional[str] = None,
    source: Optional[dict] = None,
    include_source: bool = True
) -> str:
    """
    Build video description with optional source info

    Args:
        description: Base description text
        source: Source metadata (generator, style, etc.)
        include_source: Whether to append source info

    Returns:
        Full description string
    """
    parts = []

    if description:
        parts.append(description)

    if include_source and source:
        source_lines = []

        if 'generator' in source:
            source_lines.append(f"Generated with {source['generator']}")

        if 'style' in source:
            source_lines.append(f"Style: {source['style']}")

        if 'model' in source:
            source_lines.append(f"Model: {source['model']}")

        if source_lines:
            parts.append("\n---\n" + "\n".join(source_lines))

    return "\n\n".join(parts) if parts else ""


def create_template(output_file: str, audio_file: Optional[str] = None):
    """
    Create a template publish.json file

    Args:
        output_file: Path to create template
        audio_file: Optional audio file to reference
    """
    template = {
        "title": "Song Title",
        "description": "Video description here",
        "tags": ["music", "ai"],
        "category": "music",
        "privacy": "unlisted",
        "madeForKids": False,
        "audio": audio_file or "song.mp3",
        "cover": "cover.jpg",
        "source": {
            "generator": "suno-cli",
            "style": "pop, upbeat",
            "model": "V4_5ALL"
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2)
