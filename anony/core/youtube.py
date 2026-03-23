# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import re
import aiohttp

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

    def _extract_video_id(self, url: str) -> str | None:
        """Extract the 11-char video ID from a YouTube URL."""
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return match.group(1) if match else None

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        """
        Search by keyword or resolve a YouTube URL.
        Returns a Track with audioUrl/videoUrl stored in file_path so
        pytgcalls can stream it directly without a local download.
        """
        if self.valid(query):
            # It's a direct YouTube URL
            data = await self._fetch_by_url(query)
            video_id = self._extract_video_id(query)
        else:
            data = await self._fetch_by_query(query)
            video_id = self._extract_video_id(data.get("videoUrl", "")) if data else None

        if not data:
            return None

        stream_url = data.get("videoUrl") if video else data.get("audioUrl")

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
            file_path=stream_url,   # stream directly — no local download needed
        )

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        """Fetch YouTube playlist metadata via py_yt, stream URLs resolved lazily via download()."""
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
        Resolve a stream URL for the given video ID using the /Url endpoint.
        Returns the direct audioUrl (or videoUrl) so pytgcalls can stream it
        without writing anything to disk.
        """
        url = self.base + video_id
        data = await self._fetch_by_url(url)
        if not data:
            logger.warning("Could not resolve stream URL for video_id: %s", video_id)
            return None
        return data.get("videoUrl") if video else data.get("audioUrl")

