"""OpenAI Moderation API backend."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from config import BotConfig
from moderators.base import BaseModerator

logger = logging.getLogger("bad_words_bot")

MODERATION_ENDPOINT = "https://api.openai.com/v1/moderations"


class OpenAIModerator(BaseModerator):
    """Check text using OpenAI's Moderation API."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._warned_missing_key = False

    @property
    def name(self) -> str:
        return "openai"

    def _get_api_key(self) -> str | None:
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key.strip()
        return None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.openai_timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def check(self, text: str) -> list[str]:
        """Send text to OpenAI Moderation and return flagged categories."""
        if not text:
            return []

        api_key = self._get_api_key()
        if not api_key:
            if not self._warned_missing_key:
                logger.warning(
                    "OpenAI moderation is enabled, but OPENAI_API_KEY is "
                    "not set in .env. Skipping OpenAI checks.",
                )
                self._warned_missing_key = True
            return []

        self._warned_missing_key = False
        client = self._get_client()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "input": text,
            "model": self.config.openai_model,
        }

        try:
            response = await client.post(
                MODERATION_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=self.config.openai_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OpenAI moderation HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            return []
        except httpx.RequestError as exc:
            logger.error("OpenAI moderation request failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error in OpenAI moderation: %s", exc)
            return []

        flagged: list[str] = []
        results = data.get("results", [])
        for item in results:
            if not item.get("flagged", False):
                continue
            categories = item.get("categories", {})
            reasons = [cat for cat, is_set in categories.items() if is_set]
            if reasons:
                flagged.extend(reasons)
            else:
                flagged.append("flagged")

        seen: set[str] = set()
        unique_reasons: list[str] = []
        for reason in flagged:
            if reason not in seen:
                seen.add(reason)
                unique_reasons.append(reason)

        return unique_reasons
