"""
YouTube upload functionality
"""

import pickle
import sys
from pathlib import Path
from typing import Any, Optional

# YouTube API imports
try:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False


class YouTubeError(Exception):
    """Base exception for YouTube upload errors"""
    pass


# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Default credentials paths
DEFAULT_CREDENTIALS_DIR = Path.home() / '.config' / 'mp3-to-youtube'
DEFAULT_TOKEN_FILE = DEFAULT_CREDENTIALS_DIR / 'token.pickle'
DEFAULT_CLIENT_SECRETS_FILE = DEFAULT_CREDENTIALS_DIR / 'client_secrets.json'

# YouTube category IDs
CATEGORIES = {
    'film': '1',
    'autos': '2',
    'music': '10',
    'pets': '15',
    'sports': '17',
    'travel': '19',
    'gaming': '20',
    'people': '22',
    'comedy': '23',
    'entertainment': '24',
    'news': '25',
    'howto': '26',
    'education': '27',
    'science': '28',
    'nonprofits': '29',
}


def check_youtube_available() -> bool:
    """Check if YouTube API dependencies are installed"""
    return YOUTUBE_AVAILABLE


def ensure_youtube_available():
    """Ensure YouTube API dependencies are installed"""
    if not YOUTUBE_AVAILABLE:
        raise YouTubeError(
            "YouTube API dependencies not installed.\n"
            "Install with: pip install google-auth-oauthlib google-api-python-client"
        )


def get_authenticated_service(
    client_secrets_file: Optional[str] = None,
    token_file: Optional[str] = None
) -> Any:
    """
    Authenticate with YouTube API and return service object

    Args:
        client_secrets_file: Path to OAuth2 client secrets JSON file
        token_file: Path to stored token pickle file

    Returns:
        YouTube API service object
    """
    ensure_youtube_available()

    client_secrets = Path(client_secrets_file) if client_secrets_file else DEFAULT_CLIENT_SECRETS_FILE
    token_path = Path(token_file) if token_file else DEFAULT_TOKEN_FILE

    if not client_secrets.exists():
        raise YouTubeError(
            f"OAuth2 client secrets file not found: {client_secrets}\n\n"
            "To set up YouTube uploads:\n"
            "1. Go to https://console.cloud.google.com/\n"
            "2. Create a new project (or select existing)\n"
            "3. Enable 'YouTube Data API v3'\n"
            "4. Go to 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'\n"
            "5. Select 'Desktop app' as application type\n"
            "6. Download the JSON file\n"
            f"7. Save it as: {DEFAULT_CLIENT_SECRETS_FILE}\n\n"
            "Or use --client-secrets to specify a different path"
        )

    credentials = None

    # Load saved token if exists
    if token_path.exists():
        with open(token_path, 'rb') as f:
            credentials = pickle.load(f)

    # Refresh or authenticate
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'wb') as f:
            pickle.dump(credentials, f)

    return build('youtube', 'v3', credentials=credentials)


def upload_video(
    video_file: str,
    title: str,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    category: str = "music",
    privacy: str = "private",
    made_for_kids: bool = False,
    client_secrets_file: Optional[str] = None,
    token_file: Optional[str] = None,
    progress_callback: Optional[callable] = None
) -> dict[str, Any]:
    """
    Upload video to YouTube

    Args:
        video_file: Path to video file (MP4)
        title: Video title (max 100 chars)
        description: Video description (max 5000 chars)
        tags: List of tags
        category: Category name (e.g., "music") or ID (e.g., "10")
        privacy: "public", "private", or "unlisted"
        made_for_kids: COPPA compliance flag
        client_secrets_file: Path to OAuth2 client secrets
        token_file: Path to stored token
        progress_callback: Optional callback(progress_percent) for upload progress

    Returns:
        Dict with video info: id, url, title, privacy
    """
    ensure_youtube_available()

    video_path = Path(video_file)
    if not video_path.exists():
        raise YouTubeError(f"Video file not found: {video_file}")

    if len(title) > 100:
        raise YouTubeError(f"Title too long (max 100 chars): {len(title)} chars")

    if description and len(description) > 5000:
        raise YouTubeError(f"Description too long (max 5000 chars): {len(description)} chars")

    if privacy not in ['public', 'private', 'unlisted']:
        raise YouTubeError(f"Invalid privacy setting: {privacy}")

    # Resolve category
    category_id = CATEGORIES.get(category.lower(), category)

    youtube = get_authenticated_service(client_secrets_file, token_file)

    body = {
        'snippet': {
            'title': title,
            'description': description or '',
            'tags': tags or [],
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': made_for_kids,
        }
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=1024 * 1024,
        resumable=True
    )

    try:
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(int(status.progress() * 100))

        video_id = response['id']

        return {
            'id': video_id,
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'title': response['snippet']['title'],
            'privacy': response['status']['privacyStatus']
        }

    except Exception as e:
        raise YouTubeError(f"Upload failed: {e}")


def set_thumbnail(
    video_id: str,
    thumbnail_file: str,
    client_secrets_file: Optional[str] = None,
    token_file: Optional[str] = None
) -> bool:
    """
    Set custom thumbnail for a video

    Note: Requires verified YouTube account

    Args:
        video_id: YouTube video ID
        thumbnail_file: Path to thumbnail image (JPG, max 2MB)
        client_secrets_file: Path to OAuth2 client secrets
        token_file: Path to stored token

    Returns:
        True if successful
    """
    ensure_youtube_available()

    thumb_path = Path(thumbnail_file)
    if not thumb_path.exists():
        raise YouTubeError(f"Thumbnail file not found: {thumbnail_file}")

    youtube = get_authenticated_service(client_secrets_file, token_file)

    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb_path))
        ).execute()
        return True
    except Exception as e:
        raise YouTubeError(f"Failed to set thumbnail: {e}")


def init_auth(client_secrets_file: Optional[str] = None) -> dict[str, Any]:
    """
    Initialize YouTube authentication

    Args:
        client_secrets_file: Path to client secrets JSON

    Returns:
        Dict with channel info on success
    """
    ensure_youtube_available()

    DEFAULT_CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy client secrets if provided
    if client_secrets_file:
        src = Path(client_secrets_file)
        if not src.exists():
            raise YouTubeError(f"Client secrets file not found: {client_secrets_file}")

        import shutil
        shutil.copy(src, DEFAULT_CLIENT_SECRETS_FILE)
        print(f"Copied client secrets to: {DEFAULT_CLIENT_SECRETS_FILE}")

    youtube = get_authenticated_service()

    # Test by getting channel info
    response = youtube.channels().list(part='snippet', mine=True).execute()

    if 'items' in response and len(response['items']) > 0:
        channel = response['items'][0]['snippet']
        return {
            'success': True,
            'channel_title': channel['title'],
            'channel_id': response['items'][0]['id'],
            'token_file': str(DEFAULT_TOKEN_FILE)
        }
    else:
        raise YouTubeError("No YouTube channel found for this account")
