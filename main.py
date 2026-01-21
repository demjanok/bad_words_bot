import logging
import os

from logging_config import setup_logging

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logger = setup_logging()

# Load bad words list
def load_bad_words():
    """Loads the list of bad words from file"""
    try:
        with open('bad_words.txt', 'r', encoding='utf-8') as f:
            bad_words = [line.strip().lower() for line in f if line.strip()]
        logger.info(f"Loaded {len(bad_words)} bad words")
        return bad_words
    except FileNotFoundError:
        logger.warning("bad_words.txt file not found, using default list")
        return []

# Default list of bad words (used if file not found)
DEFAULT_BAD_WORDS = ['bad', 'word', 'example']  # Add your words here

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks message for bad words"""
    if not update.message or not update.message.text:
        return
    
    message_text = update.message.text.lower()
    
    # Load bad words list
    bad_words = load_bad_words()
    if not bad_words:
        bad_words = DEFAULT_BAD_WORDS
    
    # Check for bad words in message
    found_bad_words = [word for word in bad_words if word in message_text]
    
    if found_bad_words:
        try:
            # Delete the message
            await update.message.delete()
            
            # Send warning to user
            user_name = update.message.from_user.first_name or "User"
            warning_message = (
                f"⚠️ {user_name}, your message has been deleted "
                f"because it contains inappropriate words."
            )
            
            sent_message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=warning_message
            )
            
            # Delete warning after 5 seconds
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=sent_message.message_id,
                message_thread_id=None
            )
            
            logger.info(f"Deleted message from {update.message.from_user.username} due to bad word")
            
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            # If deletion failed (no permissions), send warning
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Message contains inappropriate words!"
            )

def main():
    """Main function to start the bot"""
    # Get token from environment variable
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set! Please set the environment variable.")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add message handler (all text messages except commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    
    # Start the bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
