"""Entry point for Bad Words Bot."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    MessageHandler,
)

from handlers import (
    CONFIG,
    GROUP_MESSAGES,
    MODERATION_SERVICE,
    check_message,
    on_my_chat_member,
    post_init,
    post_shutdown,
    start,
)
from logging_config import setup_logging

logger = setup_logging()


def main() -> None:
    """Start the bot."""
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. Put it in the environment "
            "or in a .env file.",
        )
        sys.exit(1)

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    words_count = MODERATION_SERVICE.dictionary_mod.words_count
    if "dictionary" in CONFIG.moderation_checks and not words_count:
        logger.warning(
            "Dictionary moderation is enabled, but no bad words are loaded "
            "from configured dictionary files.",
        )

    _ = CONFIG.mode

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER),
    )
    application.add_handler(MessageHandler(GROUP_MESSAGES, check_message))

    logger.info("Bot started")
    application.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.EDITED_MESSAGE,
            Update.MY_CHAT_MEMBER,
        ],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
