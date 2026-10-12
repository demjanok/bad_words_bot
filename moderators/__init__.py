"""Moderation registry and coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from config import BotConfig
from moderators.base import BaseModerator
from moderators.dictionary import DictionaryModerator
from moderators.openai_mod import OpenAIModerator

logger = logging.getLogger("bad_words_bot")


@dataclass(frozen=True)
class ModerationResult:
    """Aggregated result of all moderation checks."""

    sources: dict[str, list[str]] = field(default_factory=dict)
    all_matches: tuple[str, ...] = ()

    @property
    def is_flagged(self) -> bool:
        """True if any moderation check flagged the text."""
        return bool(self.all_matches)

    @property
    def mechanisms(self) -> list[str]:
        """List of mechanism names that detected violations."""
        return list(self.sources.keys())


class ModerationService:
    """Coordinates multiple moderation checks based on configuration."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.dictionary_mod = DictionaryModerator(config)
        self.openai_mod = OpenAIModerator(config)
        self._moderators: dict[str, BaseModerator] = {
            self.dictionary_mod.name: self.dictionary_mod,
            self.openai_mod.name: self.openai_mod,
        }

    async def check(self, text: str) -> ModerationResult:
        """Run active moderation checks concurrently and aggregate matches."""
        if not text:
            return ModerationResult()

        active_checks = self.config.moderation_checks
        active_moderators = [
            self._moderators[name]
            for name in active_checks
            if name in self._moderators
        ]

        if not active_moderators:
            return ModerationResult()

        results = await asyncio.gather(
            *(mod.check(text) for mod in active_moderators)
        )

        sources: dict[str, list[str]] = {}
        all_matches_list: list[str] = []

        for mod, matches in zip(active_moderators, results):
            if matches:
                sources[mod.name] = matches
                for match in matches:
                    # Strip source annotation for clean user-facing words
                    clean = match.split(" (")[0] if " (" in match else match
                    all_matches_list.append(clean)

        seen: set[str] = set()
        unique_matches: list[str] = []
        for match in all_matches_list:
            if match not in seen:
                seen.add(match)
                unique_matches.append(match)

        return ModerationResult(
            sources=sources,
            all_matches=tuple(unique_matches),
        )

    async def close(self) -> None:
        """Clean up active moderator resources."""
        await self.openai_mod.close()
