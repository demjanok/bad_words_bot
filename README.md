# Bad Words Bot

Telegram group moderator that deletes messages containing blocked words.

The bot is intended for **group and supergroup chats**. It does not moderate
private chats or channel posts. Channel *comments* appear in a linked
discussion group; those are handled only because that discussion chat is a
group.

## Why it may only see comments on posts

Telegram bots start with **group privacy mode enabled**. In that mode the bot
does **not** receive ordinary group messages. It still receives:

- commands, mentions, and replies to the bot
- comments on channel posts in a linked discussion group

To moderate the whole group, do all the following:

1. Open [@BotFather](https://t.me/BotFather), send `/setprivacy`, choose this
   bot, and set privacy to **Disable**.
2. Add the bot to the group (or remove it and add it again if it was already
   there — privacy changes do not apply to groups the bot already joined).
3. Promote the bot to **administrator** with **Delete messages**.

Administrators receive all group messages even when privacy mode is on, but
the bot still needs delete permission to remove them.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```
TELEGRAM_BOT_TOKEN=123456:ABC...
OPENAI_API_KEY=sk-...   # Required if OpenAI moderation is enabled
LOG_LEVEL=INFO
```

Put blocked words in `bad_words.txt` (one word or phrase per line). Restart
is not required; the file is reloaded automatically when it changes.

```bash
python main.py
```

## Configuration (`config.yaml`)

Operating modes, active moderation backends, and response templates are configured in `config.yaml`.
Changes to this file are automatically hot-reloaded without restarting the bot:

```yaml
# Modes:
# - delete_and_warn : Delete message and send a warning
# - warn_only       : Send a warning without deleting the message
# - delete_only     : Delete message silently without warning
mode: delete_and_warn

# Lifetime of warning messages in seconds (0 to keep permanently)
warning_lifetime_seconds: 5

# Active moderation checks (enable one or both):
# - dictionary : check against bad_words.txt (fast Aho-Corasick algorithm)
# - openai     : check via OpenAI Moderation API (needs OPENAI_API_KEY in .env)
moderation_checks:
  - dictionary
  - openai

# Dictionary word lists (can specify multiple files, e.g. for different languages)
dictionary:
  files:
    - bad_words.txt
    - dictionaries/uk.txt
    - dictionaries/en.txt

# Optional OpenAI moderation settings
openai:
  model: "omni-moderation-latest"
  timeout: 5.0

# Custom warning templates (randomly picked).
# Available placeholders: {mention}, {words}
warning_messages:
  - "⚠️ {mention}, ваше повідомлення видалено через заборонений вміст."
  - "⚠️ {mention}, будь ласка, не вживайте ненормативну лексику."
  - "⛔️ {mention}, неприпустимий вміст у цьому чаті заборонено."
```

## Permissions checklist

- Group privacy disabled in BotFather, **or** bot is a group admin
- Bot is admin with **Delete messages**
- Bot was re-added after changing privacy (if it was already in the group)
