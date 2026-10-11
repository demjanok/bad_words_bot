"""Telegram event handlers for Bad Words Bot."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import random

from telegram import ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, ContextTypes, filters

from config import BotConfig
from moderators import ModerationService

logger = logging.getLogger("bad_words_bot")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"
BAD_WORDS_FILE = BASE_DIR / "bad_words.txt"

CONFIG = BotConfig(CONFIG_FILE)
MODERATION_SERVICE = ModerationService(CONFIG, BAD_WORDS_FILE)

GROUP_CHAT_TYPES = frozenset({ChatType.GROUP, ChatType.SUPERGROUP})
GROUP_MESSAGES = (
    filters.ChatType.GROUPS
    & (filters.TEXT | filters.CAPTION)
    & ~filters.COMMAND
    & ~filters.IS_AUTOMATIC_FORWARD
)


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
    """Handle group messages that contain blocked words or violations."""
    message = update.effective_message
    if message is None or not _is_group_chat(update):
        return
    if message.from_user is not None and message.from_user.is_bot:
        return

    text = _message_text(update)
    if text is None:
        return

    result = await MODERATION_SERVICE.check(text)
    if not result.is_flagged:
        return

    chat = update.effective_chat
    user = message.from_user
    username = user.username if user is not None else None
    mode = CONFIG.mode
    mechanisms_str = ", ".join(result.mechanisms)
    logger.info(
        "Detected violation in chat %s from %s | mechanism: %s | "
        "details: %s",
        chat.id if chat is not None else None,
        username,
        mechanisms_str,
        result.sources,
        extra={
            "mechanisms": result.mechanisms,
            "violations": result.sources,
            "mode": mode,
            "chat_id": chat.id if chat is not None else None,
            "user": username,
        },
    )

    should_delete = mode in {"delete_and_warn", "delete_only"}
    should_warn = mode in {"delete_and_warn", "warn_only"}

    if should_delete:
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

    if should_warn:
        await _send_temporary_warning(
            update,
            context,
            list(result.all_matches),
        )


async def _send_temporary_warning(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    matches: list[str],
) -> None:
    """Notify user and optionally remove warning after configured timeout."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    user = message.from_user
    mention = user.mention_html() if user is not None else "User"
    template = random.choice(CONFIG.warning_messages)
    warning = (
        template
        .replace("{mention}", mention)
        .replace("{words}", ", ".join(matches))
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

    lifetime = CONFIG.warning_lifetime_seconds
    if lifetime > 0:
        await asyncio.sleep(lifetime)
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


async def post_shutdown(_application: Application) -> None:
    """Clean up moderation resources on application shutdown."""
    await MODERATION_SERVICE.close()
