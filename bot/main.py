from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
from bot.config import Config
from bot.handler import Handler
from services import GitLabService

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

gitlab_service = GitLabService()
handler = Handler(gitlab_service)

def main():
    config = Config()
    app = Application.builder().token(config.telegram_token).build()
    
    # Register handlers
    register_handlers(app)
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logging.info("Bot interrupted by user")
    except Exception as e:
        logging.error(f"Error: {e}")

def register_handlers(app):
    register_command_handlers(app)
    register_message_handlers(app)
    app.add_error_handler(handler.error_handler)

def register_command_handlers(app):
    app.add_handler(CommandHandler('start', handler.start))

def register_message_handlers(app):
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_message))


if __name__ == '__main__':
    main()