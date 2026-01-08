from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
from bot.config import Config
from bot.handler import Handler
from services import GitLabService

# Configure logging for the application
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize global services
gitlab_service = GitLabService()
handler = Handler(gitlab_service)


def main():
    """
    Main function to run the Telegram bot.
    
    This function initializes the bot application with the configured token,
    registers all necessary command and message handlers, and starts the
    polling mechanism to continuously listen for updates from Telegram.
    
    The function handles exceptions gracefully:
    - KeyboardInterrupt: Logs an info message when the bot is manually stopped
    - Other exceptions: Logs the error and exits
    
    Example:
        >>> if __name__ == '__main__':
        >>>     main()
    
    Raises:
        ValueError: If required environment variables are not set
        Exception: If there's an error running the bot
        
    Usage:
        Run this function to start the bot:
        ```bash
        python bot/main.py
        ```
    """
    config = Config()
    app = Application.builder().token(config.telegram_token).build()
    
    # Register handlers
    register_handlers(app)
    
    try:
        # Start polling for updates from Telegram
        app.run_polling()
    except KeyboardInterrupt:
        logging.info("Bot interrupted by user")
    except Exception as e:
        logging.error(f"Error: {e}")


def register_handlers(app):
    """
    Register all command and message handlers with the application.
    
    This function orchestrates the registration of all bot handlers including
    command handlers, message handlers, and error handlers.
    
    Args:
        app (Application): The Telegram bot application instance
        
    Example:
        >>> app = Application.builder().token("YOUR_TOKEN").build()
        >>> register_handlers(app)
        
    Note:
        This function registers three types of handlers:
        - Command handlers (like /start)
        - Message handlers (text and voice messages)
        - Error handlers (for handling exceptions)
    """
    register_command_handlers(app)
    register_message_handlers(app)
    app.add_error_handler(handler.error_handler)


def register_command_handlers(app):
    """
    Register command handlers with the application.
    
    Currently registers the /start command handler which initiates the bot
    interaction with the user.
    
    Args:
        app (Application): The Telegram bot application instance
        
    Example:
        >>> app = Application.builder().token("YOUR_TOKEN").build()
        >>> register_command_handlers(app)
        
    Registered Commands:
        /start: Initiates the bot interaction and shows the start menu
        
    Note:
        Currently only registers the /start command, but can be extended
        to register additional commands as needed.
    """
    app.add_handler(CommandHandler('start', handler.start))


def register_message_handlers(app):
    """
    Register message handlers with the application.
    
    Registers handlers for different types of messages:
    - Text messages (excluding commands)
    - Voice messages
    
    Args:
        app (Application): The Telegram bot application instance
        
    Example:
        >>> app = Application.builder().token("YOUR_TOKEN").build()
        >>> register_message_handlers(app)
        
    Message Types Handled:
        TEXT: Regular text messages excluding commands
        VOICE: Voice messages sent by users
        
    Note:
        The text message handler excludes commands to avoid conflicts with
        command handlers. Voice messages are handled separately.
    """
    # Handle text messages (excluding commands)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_message))
    # Handle voice messages
    app.add_handler(MessageHandler(filters.VOICE, handler.handle_voice))


if __name__ == '__main__':
    # Entry point for running the bot
    main()