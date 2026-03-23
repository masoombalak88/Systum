# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import re
import aiohttp
from pathlib import Path

from py_yt import Playlist

from anony import logger
from anony.helpers import Track, utils


API_BASE = "https://youtube-api.itz-murali.workers.dev"


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def _fetch_by_url(self, url: str) -> dict | None:
        """Call /Url endpoint for a direct YouTube link."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE}/Url", params={"url": url}
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as ex:
            logger.warning("YouTube API /Url failed: %s", ex)
            return None

    async def _fetch_by_query(self, query: str) -> dict | None:
        """Call /YouTube endpoint for a search query, returns top result."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE}/YouTube", params={"query": query, "limit": 1}
                ) as resp:
                    resp.raise_for_status()
                    results = await resp.json()
                    if results and isinstance(results, list):
                        return results[0]
        except Exception as ex:
            logger.warning("YouTube API /YouTube failed: %s", ex)
        return None

    async def _download_stream(self, stream_url: str, filepath: str) -> str | None:
        """Download a remote stream URL to a local file. Returns filepath on success."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url) as resp:
                    resp.raise_for_status()
                    with open(filepath, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            f.write(chunk)
            return filepath
        except Exception as ex:
            logger.warning("Stream download failed: %s", ex)
            Path(filepath).unlink(missing_ok=True)
            return None

    def _extract_video_id(self, url: str) -> str | None:
        """Extract the 11-char video ID from a YouTube URL."""
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return match.group(1) if match else None

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        """Search by keyword or resolve a YouTube URL. Returns a Track (no download yet)."""
        if self.valid(query):
            data = await self._fetch_by_url(query)
            video_id = self._extract_video_id(query)
        else:
            data = await self._fetch_by_query(query)
            video_id = self._extract_video_id(data.get("videoUrl", "")) if data else None

        if not data:
            return None

        return Track(
            id=video_id or "",
            channel_name=data.get("channelName"),
            duration=data.get("duration"),
            duration_sec=utils.to_seconds(data.get("duration")),
            message_id=m_id,
            title=str(data.get("title", ""))[:25],
            thumbnail=data.get("thumbnail", ""),
            url=self.base + video_id if video_id else query,
            view_count="",
            video=video,
        )

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        """Fetch YouTube playlist metadata via py_yt."""
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                video_id = data.get("id", "")
                track = Track(
                    id=video_id,
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=str(data.get("title", ""))[:25],
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0],
                    url=data.get("link", "").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception as ex:
            logger.warning("Playlist fetch failed: %s", ex)
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        """
        Resolve stream URL via the API, then download it to a local file.
        Returns the local file path for pytgcalls to use.
        """
        ext = "mp4" if video else "webm"
        filepath = f"downloads/{video_id}.{ext}"

        if Path(filepath).exists():
            return filepath

        url = self.base + video_id
        data = await self._fetch_by_url(url)
        if not data:
            logger.warning("Could not resolve stream info for video_id: %s", video_id)
            return None

        stream_url = data.get("videoUrl") if video else data.get("audioUrl")
        if not stream_url:
            logger.warning("No stream URL in API response for video_id: %s", video_id)
            return None

        return await self._download_stream(stream_url, filepath)

