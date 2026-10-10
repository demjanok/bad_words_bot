"""Telegram moderator bot that deletes swear words in group chats."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from logging_config import setup_logging

logger = setup_logging()

BASE_DIR = Path(__file__).resolve().parent
BAD_WORDS_FILE = BASE_DIR / "bad_words.txt"
WARNING_LIFETIME_SECONDS = 5

# Groups and supergroups only. Channel comments live in a linked
# discussion *group*, but ordinary group messages are ignored by Telegram
# unless privacy mode is disabled or the bot is an administrator.
GROUP_CHAT_TYPES = frozenset({ChatType.GROUP, ChatType.SUPERGROUP})
GROUP_MESSAGES = (
    filters.ChatType.GROUPS
    & (filters.TEXT | filters.CAPTION)
    & ~filters.COMMAND
    & ~filters.IS_AUTOMATIC_FORWARD
)


class BadWordMatcher:
    """Load swear words from disk and match them as whole words/phrases."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._pattern: re.Pattern[str] | None = None
        self._words: tuple[str, ...] = ()

    @property
    def words(self) -> tuple[str, ...]:
        """Currently loaded phrases."""
        self._reload_if_changed()
        return self._words

    def find_matches(self, text: str) -> list[str]:
        """Return the configured phrases found in *text*."""
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


MATCHER = BadWordMatcher(BAD_WORDS_FILE)


def _message_text(update: Update) -> str | None:
    message = update.effective_message
    if message is None:
        return None
    text = message.text or message.caption
    if not text:
        return None
    return text


def _is_group_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type in GROUP_CHAT_TYPES


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain that moderation only runs in groups."""
    if update.message is None:
        return
    if _is_group_chat(update):
        text = (
            "I moderate this group and delete messages that contain "
            "blocked words. I need to be an administrator with the "
            "Delete messages permission."
        )
    else:
        text = (
            "I only moderate group chats, not private messages.\n\n"
            "1. Open @BotFather, send /setprivacy, and choose Disable.\n"
            "2. Add me to your group.\n"
            "3. Promote me to administrator with Delete messages.\n"
            "4. If I was already in the group before privacy was "
            "disabled, remove me and add me again."
        )
    await update.message.reply_text(text)


async def check_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Delete group messages that contain blocked words."""
    message = update.effective_message
    if message is None or not _is_group_chat(update):
        return
    if message.from_user is not None and message.from_user.is_bot:
        return

    text = _message_text(update)
    if text is None:
        return

    found = MATCHER.find_matches(text)
    if not found:
        return

    chat = update.effective_chat
    user = message.from_user
    username = user.username if user is not None else None
    logger.info(
        "Blocked message in chat %s from %s (matches: %s)",
        chat.id if chat is not None else None,
        username,
        found,
    )

    try:
        await message.delete()
    except Forbidden:
        logger.error(
            "Cannot delete messages in chat %s. Promote the bot to "
            "administrator and grant Delete messages.",
            chat.id if chat is not None else None,
        )
        return
    except BadRequest as exc:
        logger.error("Failed to delete message: %s", exc)
        return

    await _send_temporary_warning(update, context)


async def _send_temporary_warning(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Notify the user, then remove the notice after a short delay."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    user = message.from_user
    mention = user.mention_html() if user is not None else "User"
    warning = (
        f"⚠️ {mention}, your message has been deleted because it "
        "contains inappropriate words."
    )
    send_kwargs: dict[str, object] = {
        "chat_id": chat.id,
        "text": warning,
        "parse_mode": ParseMode.HTML,
    }
    if message.message_thread_id:
        send_kwargs["message_thread_id"] = message.message_thread_id

    try:
        sent = await context.bot.send_message(**send_kwargs)
    except TelegramError as exc:
        logger.error("Failed to send warning: %s", exc)
        return

    await asyncio.sleep(WARNING_LIFETIME_SECONDS)
    try:
        await context.bot.delete_message(
            chat_id=chat.id,
            message_id=sent.message_id,
        )
    except TelegramError as exc:
        logger.warning("Failed to delete warning message: %s", exc)


async def on_my_chat_member(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Log whether the bot can actually moderate a group it joined."""
    event = update.my_chat_member
    if event is None or event.chat.type not in GROUP_CHAT_TYPES:
        return

    new_member = event.new_chat_member
    chat_label = event.chat.title or event.chat.id
    status = new_member.status

    if status in {"left", "kicked"}:
        logger.info("Bot was removed from %s", chat_label)
        return

    if isinstance(new_member, ChatMemberOwner) or (
        isinstance(new_member, ChatMemberAdministrator)
        and new_member.can_delete_messages
    ):
        logger.info("Bot can delete messages in %s", chat_label)
        return

    logger.warning(
        "Bot cannot delete messages in %s (status=%s). Promote it to "
        "administrator with the Delete messages permission. If privacy "
        "mode is still enabled, ordinary group messages will also be "
        "invisible until /setprivacy is Disable and the bot is re-added.",
        chat_label,
        status,
    )


async def post_init(application: Application) -> None:
    """Warn at startup if Telegram privacy mode will hide group messages."""
    me = await application.bot.get_me()
    logger.info("Starting as @%s", me.username)
    if not me.can_read_all_group_messages:
        logger.warning(
            "Group privacy mode is enabled, so Telegram will not send "
            "ordinary group messages (only commands, mentions, replies, "
            "and comments on linked channel posts). Disable it in "
            "@BotFather with /setprivacy -> Disable, then remove and "
            "re-add the bot to each group. Making the bot an "
            "administrator also grants access to all group messages.",
        )


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

    MATCHER.find_matches("")
    if not MATCHER.words:
        logger.warning(
            "No bad words loaded from %s. The bot will not delete "
            "any messages until the file contains at least one phrase.",
            BAD_WORDS_FILE,
        )

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
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
