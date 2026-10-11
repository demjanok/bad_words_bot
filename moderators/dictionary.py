"""Dictionary-based bad word moderator."""

from __future__ import annotations

import logging
from pathlib import Path
import re

from moderators.base import BaseModerator

logger = logging.getLogger("bad_words_bot")


class DictionaryModerator(BaseModerator):
    """Detect swear words from a text file using whole-word matching."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._pattern: re.Pattern[str] | None = None
        self._words: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return "dictionary"

    @property
    def words(self) -> tuple[str, ...]:
        """Currently loaded phrases."""
        self._reload_if_changed()
        return self._words

    async def check(self, text: str) -> list[str]:
        """Find configured bad words/phrases in *text*."""
        self._reload_if_changed()
        if self._pattern is None or not text:
            return []
        return [match.group(0) for match in self._pattern.finditer(text)]

    def _reload_if_changed(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            if self._mtime is not None:
                return
            logger.warning(
                "Could not read %s; no phrases loaded",
                self.path,
            )
            self._mtime = -1.0
            self._words = ()
            self._pattern = None
            return

        if self._mtime == mtime:
            return

        words = _read_word_list(self.path)
        self._mtime = mtime
        self._words = tuple(words)
        self._pattern = _compile_pattern(words)
        logger.info("Loaded %s bad words from %s", len(words), self.path)


def _read_word_list(path: Path) -> list[str]:
    """Read unique, non-empty phrases from *path*."""
    seen: set[str] = set()
    words: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            phrase = line.casefold()
            if phrase in seen:
                continue
            seen.add(phrase)
            words.append(phrase)
    return words


def _compile_pattern(words: list[str]) -> re.Pattern[str] | None:
    """Build a Unicode-aware whole-word pattern, longest phrases first."""
    if not words:
        return None
    parts = sorted((re.escape(word) for word in words), key=len, reverse=True)
    pattern = rf"(?<!\w)(?:{'|'.join(parts)})(?!\w)"
    return re.compile(pattern, flags=re.IGNORECASE | re.UNICODE)
