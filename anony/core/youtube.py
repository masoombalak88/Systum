

import re
import asyncio
import requests

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
        self._session = requests.Session()

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def _fetch_search(self, query: str) -> list:
        """Blocking HTTP call — runs in a thread executor."""
        resp = self._session.get(
            f"{API_BASE}/YouTube",
            params={"query": query, "limit": 1},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self._fetch_search, query)

            if not results or not isinstance(results, list):
                logger.error("Empty or invalid API response: %s", results)
                return None

            data = results[0]
            logger.info("API DATA: %s", data)

            # ---------------------------------------------------------
            # Get media URL (audio or video)
            # ---------------------------------------------------------
            file_url = data.get("audioUrl") if not video else data.get("videoUrl")

            if not file_url:
                logger.error("No media URL found in API response: %s", data)
                return None

            # ---------------------------------------------------------
            # 🔥 FIX 1: Clean URL (remove newline, spaces, tabs)
            # ---------------------------------------------------------
            file_url = re.sub(r"\s+", "", file_url).strip()

            # ---------------------------------------------------------
            # 🔥 FIX 2: Force Telegram-compatible audio format (m4a)
            # ---------------------------------------------------------
            if not video:
                file_url = re.sub(r"itag=\d+", "itag=140", file_url)
                file_url = file_url.replace("mime=audio%2Fwebm", "mime=audio%2Fmp4")

            # ---------------------------------------------------------
            # 🔥 FIX 3: Remove unstable range parameter (optional)
            # ---------------------------------------------------------
            if "&range=" in file_url:
                file_url = file_url.split("&range=")[0]

            # ---------------------------------------------------------
            # 🔥 EXTRA DEBUG (optional but helpful)
            # ---------------------------------------------------------
            logger.info("FINAL URL: %s", file_url)
            logger.info("URL LENGTH: %s", len(file_url))

            return Track(
                id="api",
                channel_name=data.get("channelName"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=(data.get("title") or "")[:50],
                thumbnail=data.get("thumbnail"),
                url=self.base,
                file_path=file_url,
                view_count=None,
                video=video,
            )

        except requests.exceptions.HTTPError as ex:
            logger.warning("HTTP error during search: %s", ex)
            return None
        except requests.exceptions.ConnectionError as ex:
            logger.warning("Connection error during search: %s", ex)
            return None
        except requests.exceptions.Timeout:
            logger.warning("Search request timed out for query: %s", query)
            return None
        except Exception as ex:
            logger.warning("Search failed: %s", ex)
            return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        logger.warning("Playlist fetching is not supported via the custom API.")
        return []

    async def download(self, video_id: str, video: bool = False) -> str | None:
        return None

    # ------------------------------------------------------------------
    # Helpers (not used now but kept safe)
    # ------------------------------------------------------------------

    def _extract_id(self, media_url: str) -> str | None:
        match = re.search(r"(?:videoplayback.*?id=|/vi/)([A-Za-z0-9_-]{11})", media_url)
        return match.group(1) if match else None

    def _build_url_from_title(self, data: dict) -> str | None:
        return None
