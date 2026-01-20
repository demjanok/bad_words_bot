# Telegram Bot for Bad Words Filtering

Bot automatically deletes messages containing bad words.

## Installation

1. Install Python 3.8 or newer

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a bot via [@BotFather](https://t.me/BotFather) in Telegram and get your token

4. Set the environment variable with your token:

**Windows (PowerShell):**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_token_here"
```

**Linux/Mac:**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
```

5. Add the bot to your group and grant it administrator rights with permission to delete messages

## Usage

1. Start the bot:
```bash
python main.py
```

2. The bot will automatically delete messages containing bad words

## Configuration

### Adding Bad Words

Edit the `bad_words.txt` file and add bad words (one word per line):
```
bad
word
example
```

The bot checks words case-insensitively, so "BAD" and "bad" are considered the same.

## Important

- The bot must have administrator rights in the group
- The bot must have permission to delete messages
- If the bot cannot delete a message, it will send a warning

## License

MIT
