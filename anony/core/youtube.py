# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import re
import aiohttp

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

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE}/YouTube",
                    params={"query": query, "limit": 1},
                ) as resp:
                    resp.raise_for_status()
                    results = await resp.json()

            if not results or not isinstance(results, list):
                return None

            data = results[0]
            print(data)
            return Track(
                id=self._extract_id(data.get("audioUrl") or data.get("videoUrl") or ""),
                channel_name=data.get("channelName"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=(data.get("title") or "")[:25],
                thumbnail=data.get("thumbnail"),
                url=self._build_url_from_title(data),
                view_count=None,
                video=video,
            )
        except Exception as ex:
            logger.warning("Search failed: %s", ex)
            return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        # Playlist fetching is not supported by the custom API.
        # Returning empty list to avoid breaking callers.
        logger.warning("Playlist fetching is not supported via the custom API.")
        return []

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE}/Url",
                    params={"url": url},
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            media_url = data.get("videoUrl") if video else data.get("audioUrl")
            if not media_url:
                logger.warning("No %s URL returned for video_id: %s", "video" if video else "audio", video_id)
                return None

            return media_url

        except Exception as ex:
            logger.warning("Download failed: %s", ex)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_id(self, media_url: str) -> str | None:
        """Best-effort extraction of a video ID from a CDN/stream URL."""
        match = re.search(r"(?:videoplayback.*?id=|/vi/)([A-Za-z0-9_-]{11})", media_url)
        return match.group(1) if match else None

    def _build_url_from_title(self, data: dict) -> str | None:
        """Return a watchable URL if we can recover the video ID."""
        vid_id = self._extract_id(data.get("audioUrl") or data.get("videoUrl") or "")
        return (self.base + vid_id) if vid_id else None

