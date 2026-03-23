# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import re
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

# ── API base ────────────────────────────────────────────────────────────────
_BASE = "https://youtube-api.itz-murali.workers.dev"
_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+"
)


# ── Track dataclass ──────────────────────────────────────────────────────────
@dataclass
class Track:
    id: str                        # video id  (used as cache key / queue id)
    title: str
    duration: str                  # formatted  e.g. "3:42"
    duration_sec: int              # seconds    (checked against DURATION_LIMIT)
    thumbnail: str
    channel: str
    file_path: str                 # direct stream URL  (audio or video)
    url: str                       # original YT watch URL  (shown in messages)
    user: str = ""                 # set by the caller after search()
    message_id: Optional[int] = None


# ── helpers ──────────────────────────────────────────────────────────────────
def _duration_to_sec(duration: str) -> int:
    """Convert 'H:MM:SS' or 'M:SS' string to total seconds."""
    parts = [int(p) for p in duration.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return int(parts[0])


def _video_id_from_url(url: str) -> str:
    """Extract the 11-char video id from a full or short YouTube URL."""
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else url


def _build_track(data: dict, video: bool) -> Track:
    """Turn a raw API response dict into a Track."""
    stream_url = data["videoUrl"] if video else data["audioUrl"]
    vid_id = _video_id_from_url(data.get("videoUrl", data.get("audioUrl", "")))
    return Track(
        id=vid_id,
        title=data["title"],
        duration=data["duration"],
        duration_sec=_duration_to_sec(data["duration"]),
        thumbnail=data.get("thumbnail", ""),
        channel=data.get("channelName", ""),
        file_path=stream_url,        # ← direct stream, no download needed
        url=f"https://www.youtube.com/watch?v={vid_id}",
    )


# ── public API ───────────────────────────────────────────────────────────────
async def search(query_or_url: str, message_id: int, video: bool = False) -> Optional[Track]:
    """
    Search by keyword OR resolve a YouTube URL.
    Returns a Track with file_path already set to the stream URL.
    """
    is_url = bool(_YT_URL_RE.match(query_or_url))

    async with aiohttp.ClientSession() as session:
        if is_url:
            params = {"url": query_or_url}
            async with session.get(f"{_BASE}/Url", params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        else:
            params = {"query": query_or_url, "limit": 1}
            async with session.get(f"{_BASE}/YouTube", params=params) as resp:
                if resp.status != 200:
                    return None
                results = await resp.json()
                if not results:
                    return None
                data = results[0]   # top result

    track = _build_track(data, video)
    track.message_id = message_id
    return track


async def download(track_id: str, video: bool = False) -> Optional[str]:
    """
    Fallback: re-fetch the stream URL by video id when file_path is missing.
    Returns the direct stream URL (string) — no local file is written.
    """
    url = f"https://www.youtube.com/watch?v={track_id}"
    async with aiohttp.ClientSession() as session:
        params = {"url": url}
        async with session.get(f"{_BASE}/Url", params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    return data["videoUrl"] if video else data["audioUrl"]


async def playlist(limit: int, mention: str, pl_url: str, video: bool = False) -> list[Track]:
    """
    Playlist support is not available via this API.
    Returns an empty list so the caller shows the playlist_error message.
    """
    return []

