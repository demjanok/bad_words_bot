"""Configuration loader with hot-reloading for Bad Words Bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("bad_words_bot")

VALID_MODES = frozenset({"delete_and_warn", "warn_only", "delete_only"})
VALID_CHECKS = frozenset({"dictionary", "openai"})
DEFAULT_WARNING_MESSAGES = (
    "⚠️ {mention}, your message has been deleted because it "
    "contains inappropriate words.",
)


class BotConfig:
    """Load configuration from YAML and reload when the file changes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._mode: str = "delete_and_warn"
        self._warning_lifetime: int = 5
        self._warning_messages: tuple[str, ...] = DEFAULT_WARNING_MESSAGES
        self._moderation_checks: tuple[str, ...] = ("dictionary",)
        self._openai_model: str = "omni-moderation-latest"
        self._openai_timeout: float = 5.0

    @property
    def mode(self) -> str:
        self._reload_if_changed()
        return self._mode

    @property
    def warning_lifetime_seconds(self) -> int:
        self._reload_if_changed()
        return self._warning_lifetime

    @property
    def warning_messages(self) -> tuple[str, ...]:
        self._reload_if_changed()
        return self._warning_messages

    @property
    def moderation_checks(self) -> tuple[str, ...]:
        self._reload_if_changed()
        return self._moderation_checks

    @property
    def openai_model(self) -> str:
        self._reload_if_changed()
        return self._openai_model

    @property
    def openai_timeout(self) -> float:
        self._reload_if_changed()
        return self._openai_timeout

    def _reload_if_changed(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            if self._mtime is not None:
                return
            logger.warning(
                "Could not read %s; using default configuration",
                self.path,
            )
            self._mtime = -1.0
            return

        if self._mtime == mtime:
            return

        try:
            with self.path.open(encoding="utf-8") as handle:
                data: dict[str, Any] = yaml.safe_load(handle) or {}
        except Exception as exc:
            logger.error(
                "Failed to parse %s: %s; keeping current configuration",
                self.path,
                exc,
            )
            self._mtime = mtime
            return

        mode = str(data.get("mode", "delete_and_warn")).strip().lower()
        if mode not in VALID_MODES:
            logger.warning(
                "Invalid mode '%s' in %s; defaulting to delete_and_warn",
                mode,
                self.path,
            )
            mode = "delete_and_warn"
        self._mode = mode

        raw_lifetime = data.get("warning_lifetime_seconds", 5)
        try:
            self._warning_lifetime = max(0, int(raw_lifetime))
        except (TypeError, ValueError):
            self._warning_lifetime = 5

        raw_messages = data.get("warning_messages")
        if isinstance(raw_messages, list) and raw_messages:
            parsed = [
                str(msg).strip()
                for msg in raw_messages
                if str(msg).strip()
            ]
            self._warning_messages = (
                tuple(parsed) if parsed else DEFAULT_WARNING_MESSAGES
            )
        else:
            self._warning_messages = DEFAULT_WARNING_MESSAGES

        raw_checks = data.get("moderation_checks")
        if isinstance(raw_checks, list) and raw_checks:
            checks = [
                str(c).strip().lower()
                for c in raw_checks
                if str(c).strip().lower() in VALID_CHECKS
            ]
            self._moderation_checks = (
                tuple(checks) if checks else ("dictionary",)
            )
        else:
            self._moderation_checks = ("dictionary",)

        openai_cfg = data.get("openai") or {}
        if isinstance(openai_cfg, dict):
            self._openai_model = str(
                openai_cfg.get("model", "omni-moderation-latest")
            ).strip()
            try:
                self._openai_timeout = float(openai_cfg.get("timeout", 5.0))
            except (TypeError, ValueError):
                self._openai_timeout = 5.0
        else:
            self._openai_model = "omni-moderation-latest"
            self._openai_timeout = 5.0

        self._mtime = mtime
        logger.info(
            "Loaded configuration from %s (mode=%s, timeout=%ss, checks=%s)",
            self.path,
            self._mode,
            self._warning_lifetime,
            list(self._moderation_checks),
        )
