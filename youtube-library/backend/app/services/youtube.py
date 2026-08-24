import asyncio
from pathlib import Path
from datetime import datetime
from uuid import UUID

import httpx
import yt_dlp

from app.config import get_settings
from app.database import SessionLocal
from app.models import Channel, Video, VideoStatus

settings = get_settings()


async def get_channel_info(channel_url: str) -> dict | None:
    """Get basic channel information."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'playlist_items': '0',
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                result = ydl.extract_info(channel_url, download=False)
                if result:
                    return {
                        'id': result.get('channel_id') or result.get('id'),
                        'name': result.get('channel') or result.get('uploader') or result.get('title', 'Unknown'),
                        'url': channel_url
                    }
            except Exception as e:
                print(f"Error fetching channel info: {e}")
        return None

    return await asyncio.to_thread(_extract)


async def get_channel_videos(
    channel_url: str,
    skip_shorts: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Get videos from a channel or playlist, optionally filtering out Shorts.

    Entries come newest-first (channel videos tab / playlist order), so a
    limit keeps the newest N videos.
    """
    videos = []

    # Playlist URLs must be used as-is; for channels, use the videos tab
    is_playlist = 'list=' in channel_url or '/playlist' in channel_url
    if not is_playlist and '/videos' not in channel_url:
        channel_url = channel_url.rstrip('/') + '/videos'

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'ignoreerrors': True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                result = ydl.extract_info(channel_url, download=False)
                if result is None:
                    return []

                entries = result.get('entries', [])
                for entry in entries:
                    if entry is None:
                        continue

                    video_id = entry.get('id')
                    title = entry.get('title', 'Unknown Title')
                    duration = entry.get('duration')

                    # Skip playlists
                    if entry.get('_type') == 'playlist':
                        continue

                    # Skip Shorts (videos under 61 seconds)
                    if skip_shorts and duration is not None and duration < 61:
                        print(f"Skipping Short: {title} ({duration}s)")
                        continue

                    if video_id and len(video_id) == 11:
                        videos.append({
                            'youtube_id': video_id,
                            'title': title,
                            'url': f"https://www.youtube.com/watch?v={video_id}"
                        })
                        if limit and len(videos) >= limit:
                            break

            except Exception as e:
                print(f"Error fetching videos: {e}")

        return videos

    return await asyncio.to_thread(_extract)


async def fetch_channel_videos(channel_id: UUID):
    """Fetch all videos from a channel and add to database."""
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            return

        print(f"Fetching videos for channel: {channel.name}")

        # Get videos from YouTube (limited to the newest N if configured)
        videos = await get_channel_videos(channel.url, limit=channel.max_videos)
        print(f"Found {len(videos)} videos")

        # Get existing video IDs
        existing_ids = {v.youtube_id for v in db.query(Video).filter(
            Video.channel_id == channel_id
        ).all()}

        # Add new videos
        new_count = 0
        for video_data in videos:
            if video_data['youtube_id'] not in existing_ids:
                video = Video(
                    channel_id=channel_id,
                    youtube_id=video_data['youtube_id'],
                    title=video_data['title'],
                    status=VideoStatus.PENDING
                )
                db.add(video)
                new_count += 1

        # Update last_checked
        channel.last_checked = datetime.utcnow()
        db.commit()

        print(f"Added {new_count} new videos for {channel.name}")

        # Kick off processing right away instead of waiting for the scheduler.
        # The pipeline lock prevents duplicate runs; failures here must not
        # break the import itself.
        if new_count > 0:
            try:
                from app.services.pipeline import process_pending_videos
                asyncio.create_task(process_pending_videos(channel_id))
            except Exception as e:
                print(f"Could not auto-start processing for {channel.name}: {e}")

    except Exception as e:
        print(f"Error in fetch_channel_videos: {e}")
        db.rollback()
    finally:
        db.close()


async def download_video(video_id: UUID) -> tuple[str | None, str | None]:
    """Download video and audio files. Returns (video_path, audio_path)."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return None, None

        video.status = VideoStatus.DOWNLOADING
        db.commit()

        url = f"https://www.youtube.com/watch?v={video.youtube_id}"
        data_dir = Path(settings.data_dir)

        video_dir = data_dir / "videos"
        audio_dir = data_dir / "audio"
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        video_path = None
        audio_path = None

        # Download video (MP4)
        video_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(video_dir / '%(id)s.%(ext)s'),
            'ignoreerrors': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }

        def _download_video():
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                ydl.download([url])

        await asyncio.to_thread(_download_video)

        # Find the downloaded video file
        for ext in ['mp4', 'mkv', 'webm']:
            potential_path = video_dir / f"{video.youtube_id}.{ext}"
            if potential_path.exists():
                video_path = str(potential_path)
                break

        # Download audio (MP3)
        audio_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(audio_dir / '%(id)s.%(ext)s'),
            'ignoreerrors': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }

        def _download_audio():
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.download([url])

        await asyncio.to_thread(_download_audio)
        audio_path = str(audio_dir / f"{video.youtube_id}.mp3")

        # Verify files were actually created
        audio_exists = Path(audio_path).exists()

        if not audio_exists:
            # Download failed silently
            video.status = VideoStatus.ERROR
            video.error_message = "Download failed - no audio file created"
            db.commit()
            print(f"Download failed for {video.youtube_id}: no files created")
            return None, None

        # Update database
        video.video_path = video_path
        video.audio_path = audio_path
        db.commit()

        print(f"Downloaded: {video.youtube_id}")
        return video_path, audio_path

    except Exception as e:
        print(f"Error downloading video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.ERROR
            video.error_message = str(e)[:500]
            db.commit()
        return None, None
    finally:
        db.close()


async def download_thumbnail(video_id: UUID) -> str | None:
    """Download video thumbnail. Returns thumbnail path or None."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return None

        data_dir = Path(settings.data_dir)
        thumbnail_dir = data_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        thumbnail_path = thumbnail_dir / f"{video.youtube_id}.jpg"

        # Try different YouTube thumbnail URLs (highest quality first)
        thumbnail_urls = [
            f"https://img.youtube.com/vi/{video.youtube_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{video.youtube_id}/sddefault.jpg",
            f"https://img.youtube.com/vi/{video.youtube_id}/hqdefault.jpg",
            f"https://img.youtube.com/vi/{video.youtube_id}/mqdefault.jpg",
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for thumb_url in thumbnail_urls:
                try:
                    response = await client.get(thumb_url)
                    # YouTube returns a small placeholder for non-existent thumbnails
                    if response.status_code == 200 and len(response.content) > 1000:
                        thumbnail_path.write_bytes(response.content)
                        video.thumbnail_path = str(thumbnail_path)
                        db.commit()
                        print(f"Downloaded thumbnail: {video.youtube_id}")
                        return str(thumbnail_path)
                except Exception:
                    continue

        print(f"Could not download thumbnail for {video.youtube_id}")
        return None

    except Exception as e:
        print(f"Error downloading thumbnail for {video_id}: {e}")
        return None
    finally:
        db.close()
