"""Base class for all moderation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseModerator(ABC):
    """Abstract moderator interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifying the moderator."""

    @abstractmethod
    async def check(self, text: str) -> list[str]:
        """Check text and return a list of triggered words/categories."""
