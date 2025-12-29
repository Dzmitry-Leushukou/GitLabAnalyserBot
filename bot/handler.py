from bot.config import Config
from bot.menus.main_menu import get_main_menu
from bot.menus.workers_menu import get_workers_menu
from bot.menus.worker_menu import get_worker_menu, get_user_detail_menu
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
            self.current_users = {}  # Store current users for each user session
    
    @staticmethod
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
            case "Main menu":
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
            case "Worker":
                await self.worker_message(update, context)
            case username if username in context.user_data.get('user_mapping', {}):
                # Handle user selection - call get_user with the selected user ID
                user_id = context.user_data['user_mapping'][username]
                await self.select_user(update, context, user_id)
            case "Estimate time":
                await self.estimate_time(update,context)
            case _:
                await update.message.reply_text(
                    text="Invalid option"
                )
        
    async def workers_message(self, update, context):
        logger.info("Workers message")
        
        if 'page' not in context.user_data:
            context.user_data['page'] = 1
        
        page = context.user_data['page']
        
        # Store the current users for this session
        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        users = gitlab_service.get_users(page)
        
        # Create a mapping of user names to user IDs for this session
        user_mapping = {}
        for user in users:
            name = user.get('name', user.get('username', 'Unknown'))
            user_mapping[name] = user['id']
        
        # Store the user mapping in context
        context.user_data['user_mapping'] = user_mapping
        
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_workers_menu(page)
        )
    
    async def back_to_main_menu_message(self, update, context):
        logger.info("Back to Main menu message")
        await update.message.reply_text(
            text="Choose option:",
            reply_markup=get_main_menu()
        )

    async def worker_message(self, update, context):
        logger.info("Worker message")
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_worker_menu()
        )

    async def select_user(self, update, context, user_id):
        logger.info(f"Selected user with ID: {user_id}")
        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        user_data = gitlab_service.get_user(user_id)
        
        # Store the current user in context
        context.user_data['current_user'] = user_data.get('username', 'Unknown')
        
        # Format and send user information
        user_info = f"User Info:\n"
        user_info += f"Name: {user_data.get('name', 'N/A')}\n"
        user_info += f"Username: {user_data.get('username', 'N/A')}\n"
        if user_data.get('avatar_url'):
            user_info += f"Avatar URL: {user_data.get('avatar_url', 'N/A')}\n"
        
        # Получаем страницу из контекста пользователя, если она есть, иначе используем 1
        page = context.user_data.get('page', 1)
        await update.message.reply_text(
            text=user_info,
            reply_markup=get_user_detail_menu()
        )

    async def estimate_time(self, update,context):
        current_user = context.user_data.get('current_user', 'Unknown')
        if current_user=="Unknown":
            await update.message.reply_text(
            text="Can`t get info about user. Try again",
            reply_markup=get_worker_menu()
            )
        
        