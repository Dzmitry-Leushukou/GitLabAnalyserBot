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
            case "All user tasks":
                await self.all_tasks(update,context)
            case "Back to workers":
                # Handle back button from user detail menu
                await self.back_to_workers_menu(update, context)
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
        
        # Store the current user and user ID in context
        context.user_data['current_user'] = user_data.get('username', 'Unknown')
        context.user_data['current_user_id'] = user_id
        
        # Format and send user information
        user_info = f"User Info:\n"
        user_info += f"Name: {user_data.get('name', 'N/A')}\n"
        user_info += f"Username: {user_data.get('username', 'N/A')}\n"
        if user_data.get('avatar_url'):
            user_info += f"Avatar URL: {user_data.get('avatar_url', 'N/A')}\n"
        
        # Get page from user context, if exists, otherwise use 1
        page = context.user_data.get('page', 1)
        await update.message.reply_text(
            text=user_info,
            reply_markup=get_user_detail_menu()
        )
    async def all_tasks(self, update, context):
        current_user = context.user_data.get('current_user', 'Unknown')
        current_user_id = context.user_data.get('current_user_id', None)
        
        if current_user == "Unknown" or not current_user_id:
            await update.message.reply_text(
                text="Can't get info about user. Try again",
                reply_markup=get_worker_menu()
            )
            return

        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        
        # Get user tasks by saved ID
        tasks = gitlab_service.get_user_tasks(current_user_id)
        
        if not tasks:
            await update.message.reply_text(
                text="No tasks found for this user",
                reply_markup=get_user_detail_menu()
            )
            return
        
        # Form task information with label history
        task_details = []
        for task in tasks:
            project_id = task.get('project_id')
            issue_iid = task.get('iid')
            
            # Get label history for task
            label_history = gitlab_service.get_label_history(project_id, issue_iid)
            
            task_info = {
                'id': task.get('id'),
                'iid': task.get('iid'),
                'project_id': project_id,
                'title': task.get('title', ''),
                'description': task.get('description', ''),
                'state': task.get('state', ''),
                'created_at': task.get('created_at', ''),
                'updated_at': task.get('updated_at', ''),
                'labels': task.get('labels', []),
                'assignee': task.get('assignee', {}),
                'author': task.get('author', {}),
                'label_history': label_history
            }
            task_details.append(task_info)
        
        # Create result file
        import io
        from telegram import InputFile
        
        # Form text file with task information
        output = io.StringIO()
        output.write(f"User tasks: {current_user}\n")
        output.write(f"Total tasks: {len(task_details)}\n")
        output.write("="*50 + "\n\n")
        
        for i, task in enumerate(task_details, 1):
            output.write(f"{i}. Task #{task['iid']} (ID: {task['id']})\n")
            output.write(f"   Project ID: {task['project_id']}\n")
            output.write(f"   Title: {task['title']}\n")
            output.write(f"   State: {task['state']}\n")
            output.write(f"   Created at: {task['created_at']}\n")
            output.write(f"   Updated at: {task['updated_at']}\n")
            output.write(f"   Labels: {', '.join(task['labels']) if task['labels'] else 'no labels'}\n")
            
            if task['author']:
                output.write(f"   Author: {task['author'].get('name', task['author'].get('username', 'Unknown'))}\n")
            
            if task['assignee']:
                output.write(f"   Assignee: {task['assignee'].get('name', task['assignee'].get('username', 'Unknown'))}\n")
            
            if task['label_history']:
                output.write(f"   Label change history:\n")
                for event in task['label_history']:
                    output.write(f"     - {event['timestamp']}: label '{event['label']}' {event['action']} by {event['user']}\n")
            else:
                output.write(f"   Label change history: not available\n")
            
            output.write("\n" + "-"*30 + "\n\n")
        
        # Send file to user
        output_content = output.getvalue()
        output_bytes = io.BytesIO(output_content.encode('utf-8'))
        output_bytes.name = f"user_tasks_{current_user}.txt"
        
        await update.message.reply_document(
            document=InputFile(output_bytes, filename=f"user_tasks_{current_user}.txt"),
            caption=f"User tasks {current_user} (total: {len(task_details)})"
        )
        
        output.close()
        
        
    async def back_to_workers_menu(self, update, context):
        logger.info("Back to workers menu")
        # Get the current page from user context, default to 1 if not set
        page = context.user_data.get('page', 1)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_worker_menu(page)
        )
        
        