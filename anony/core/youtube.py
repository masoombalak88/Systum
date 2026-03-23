# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.

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
                logger.error("Empty or invalid API response: %s", results)
                return None

            data = results[0]
            logger.info("API DATA: %s", data)

            # 🔥 Direct URL (no download API needed)
            file_url = data.get("audioUrl") if not video else data.get("videoUrl")

            if not file_url:
                logger.error("No media URL found in API response: %s", data)
                return None

            return Track(
                id="api",  # dummy id (not used anymore)
                channel_name=data.get("channelName"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=(data.get("title") or "")[:50],
                thumbnail=data.get("thumbnail"),
                url=self.base,  # optional
                file_path=file_url,  # 🔥 DIRECT STREAM URL
                view_count=None,
                video=video,
            )

        except Exception as ex:
            logger.warning("Search failed: %s", ex)
            return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        logger.warning("Playlist fetching is not supported via the custom API.")
        return []

    async def download(self, video_id: str, video: bool = False) -> str | None:
        # ❌ Not needed anymore (kept for compatibility)
        return None

    # ------------------------------------------------------------------
    # Helpers (not used now but kept safe)
    # ------------------------------------------------------------------

    def _extract_id(self, media_url: str) -> str | None:
        match = re.search(r"(?:videoplayback.*?id=|/vi/)([A-Za-z0-9_-]{11})", media_url)
        return match.group(1) if match else None

    def _build_url_from_title(self, data: dict) -> str | None:
        return None
