"""Configure structured JSON logging for the bot."""

from __future__ import annotations

import logging
import os

from pythonjsonlogger.json import JsonFormatter

LOGGER_NAME = "bad_words_bot"


def setup_logging() -> logging.Logger:
    """Configure the root logger and return the application logger."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    service_name = os.getenv("SERVICE_NAME", "bad-words-bot")
    env = os.getenv("ENV", "dev")

    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            static_fields={
                "service": service_name,
                "env": env,
            },
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(LOGGER_NAME)
