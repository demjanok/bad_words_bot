"""Dictionary-based bad word moderator using the Aho-Corasick algorithm."""

from __future__ import annotations

import logging
from pathlib import Path

import ahocorasick

from config import BotConfig
from moderators.base import BaseModerator

logger = logging.getLogger("bad_words_bot")


def _is_word_char(char: str) -> bool:
    """Check if character is a word character (equivalent to Unicode \\w)."""
    return char.isalnum() or char == "_"


class DictionaryModerator(BaseModerator):
    """Detect swear words across multiple dictionaries using Aho-Corasick."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._file_mtimes: dict[Path, float] = {}
        self._automaton: ahocorasick.Automaton | None = None
        self._words_count: int = 0

    @property
    def name(self) -> str:
        return "dictionary"

    @property
    def words_count(self) -> int:
        """Total number of loaded unique phrases across all dictionaries."""
        self._reload_if_changed()
        return self._words_count

    async def check(self, text: str) -> list[str]:
        """Find configured bad words/phrases in *text*.

        Returns matched phrases annotated with their source dictionary file,
        e.g. 'ass (en.txt)' or 'срака (uk.txt)'.
        """
        self._reload_if_changed()
        if self._automaton is None or not text:
            return []

        text_lower = text.casefold()
        found: list[str] = []

        for end_idx, (original, sources) in self._automaton.iter(text_lower):
            start_idx = end_idx - len(original) + 1

            # Left boundary check (avoid matching inside a longer word)
            if start_idx > 0 and _is_word_char(text_lower[start_idx - 1]):
                continue

            # Right boundary check (avoid matching inside a longer word)
            if (
                end_idx + 1 < len(text_lower)
                and _is_word_char(text_lower[end_idx + 1])
            ):
                continue

            matched_text = text[start_idx: end_idx + 1]
            sources_label = ", ".join(sources)
            found.append(f"{matched_text} ({sources_label})")

        return found

    def _reload_if_changed(self) -> None:
        dict_files = self.config.dictionary_files
        current_mtimes: dict[Path, float] = {}
        for path in dict_files:
            try:
                current_mtimes[path] = path.stat().st_mtime
            except OSError:
                current_mtimes[path] = -1.0

        if self._file_mtimes == current_mtimes and self._automaton is not None:
            return

        words_map: dict[str, list[str]] = {}
        total_files_loaded = 0

        for path in dict_files:
            if not path.is_file():
                if (
                    current_mtimes[path] != -1.0
                    or path not in self._file_mtimes
                ):
                    logger.warning("Dictionary file %s does not exist", path)
                continue

            file_words = _read_word_list(path)
            total_files_loaded += 1
            file_label = path.name

            for word in file_words:
                if word not in words_map:
                    words_map[word] = []
                if file_label not in words_map[word]:
                    words_map[word].append(file_label)

        self._file_mtimes = current_mtimes
        self._words_count = len(words_map)

        if not words_map:
            self._automaton = None
            logger.warning(
                "No bad words loaded from configured dictionaries (%s files)",
                len(dict_files),
            )
            return

        automaton = ahocorasick.Automaton()
        for word, sources in words_map.items():
            automaton.add_word(word, (word, tuple(sources)))
        automaton.make_automaton()

        self._automaton = automaton
        logger.info(
            "Loaded %s unique bad words from %s dictionary file(s) into "
            "Aho-Corasick automaton: %s",
            len(words_map),
            total_files_loaded,
            [p.name for p in dict_files if p.is_file()],
        )


def _read_word_list(path: Path) -> list[str]:
    """Read unique, non-empty phrases from *path*."""
    seen: set[str] = set()
    words: list[str] = []
    try:
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
    except OSError as exc:
        logger.error("Failed to read dictionary file %s: %s", path, exc)
    return words
