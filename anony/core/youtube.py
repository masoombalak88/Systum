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

# Mimic a real browser so Google CDN / the API worker doesn't block us
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.youtube.com/",
    "Origin": "https://www.youtube.com",
}


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
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    f"{API_BASE}/Url", params={"url": url}
                ) as resp:
                    if not resp.ok:
                        text = await resp.text()
                        logger.error(
                            "API /Url returned HTTP %s for %s — body: %s",
                            resp.status, url, text[:300],
                        )
                        return None
                    return await resp.json()
        except Exception as ex:
            logger.error("API /Url exception for %s: %s", url, ex)
            return None

    async def _fetch_by_query(self, query: str) -> dict | None:
        """Call /YouTube endpoint for a search query, returns top result."""
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    f"{API_BASE}/YouTube", params={"query": query, "limit": 1}
                ) as resp:
                    if not resp.ok:
                        text = await resp.text()
                        logger.error(
                            "API /YouTube returned HTTP %s for query=%r — body: %s",
                            resp.status, query, text[:300],
                        )
                        return None
                    results = await resp.json()
                    if results and isinstance(results, list):
                        return results[0]
                    logger.error("API /YouTube returned empty results for query=%r", query)
        except Exception as ex:
            logger.error("API /YouTube exception for query=%r: %s", query, ex)
        return None

    async def _download_stream(self, stream_url: str, filepath: str) -> str | None:
        """Download a remote stream URL to a local file with browser-like headers."""
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(stream_url, allow_redirects=True) as resp:
                    if not resp.ok:
                        text = await resp.text()
                        logger.error(
                            "Stream download got HTTP %s from %s — body: %s",
                            resp.status, stream_url[:80], text[:300],
                        )
                        return None

                    content_type = resp.headers.get("Content-Type", "")
                    content_length = resp.headers.get("Content-Length", "unknown")
                    logger.info(
                        "Downloading stream: Content-Type=%s, Content-Length=%s",
                        content_type, content_length,
                    )

                    with open(filepath, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            f.write(chunk)

            size = Path(filepath).stat().st_size
            if size < 1024:
                logger.error(
                    "Downloaded file is suspiciously small (%d bytes) — likely an error page, discarding.",
                    size,
                )
                Path(filepath).unlink(missing_ok=True)
                return None

            logger.info("Stream saved to %s (%d bytes)", filepath, size)
            return filepath

        except Exception as ex:
            logger.error("Stream download exception for %s: %s", stream_url[:80], ex)
            Path(filepath).unlink(missing_ok=True)
            return None

    def _extract_video_id(self, url: str) -> str | None:
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return match.group(1) if match else None

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
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
            logger.error("Playlist fetch failed: %s", ex)
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        ext = "mp4" if video else "webm"
        filepath = f"downloads/{video_id}.{ext}"

        if Path(filepath).exists():
            logger.info("Returning cached file: %s", filepath)
            return filepath

        url = self.base + video_id
        logger.info("Resolving stream info for video_id=%s", video_id)

        data = await self._fetch_by_url(url)
        if not data:
            logger.error("API returned no data for video_id=%s — cannot download", video_id)
            return None

        stream_url = data.get("videoUrl") if video else data.get("audioUrl")
        if not stream_url:
            logger.error(
                "API response missing %s for video_id=%s — response keys: %s",
                "videoUrl" if video else "audioUrl",
                video_id,
                list(data.keys()),
            )
            return None

        logger.info("Got stream URL for %s, starting download...", video_id)
        return await self._download_stream(stream_url, filepath)

