from bot.config import Config
from bot.menus.main_menu import get_main_menu
from bot.menus.workers_menu import get_workers_menu
from bot.menus.start_menu import get_start_menu
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class Handler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = Config()
            self._initialized = True
    
    async def error_handler(update, context):
        logger = logging.getLogger(__name__)
        logger.error(f"Update {update} caused error {context.error}", exc_info=True)

    # Commands
    async def start(self, update, context):
        logger.info("Start command")
        await update.message.reply_text(
            text="Welcome! Press the Start button to begin:",
            reply_markup=get_start_menu()
        )

    # Message handlers instead of callback handlers
    async def handle_message(self, update, context):
        text = update.message.text
        
        match text:
            case "Start":
                await update.message.reply_text(
                    text="Choose option:",
                    reply_markup=get_main_menu()
                )
            case "Workers":
                if 'page' not in context.user_data:
                    context.user_data['page'] = 1
                await self.workers_message(update, context)
            case "Main Menu":
                await self.back_to_main_menu_message(update, context)
            case "Next":
                if 'page' not in context.user_data:
                    context.user_data['page'] = 1
                context.user_data['page'] += 1
                await self.workers_message(update, context)
            case "Previous":
                if 'page' not in context.user_data:
                    context.user_data['page'] = 1
                context.user_data['page'] = max(1, context.user_data['page'] - 1)
                await self.workers_message(update, context)
            case _:
                await update.message.reply_text(
                    text="Invalid option"
                )
        
    async def workers_message(self, update, context):
        logger.info("Workers message")
        
        if 'page' not in context.user_data:
            context.user_data['page'] = 1
        
        page = context.user_data['page']
        
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_workers_menu(page)
        )
    
    async def back_to_main_menu_message(self, update, context):
        logger.info("Back to main menu message")
        await update.message.reply_text(
            text="Choose option:",
            reply_markup=get_main_menu()
        )