from bot.config import Config
from bot.menus.main_menu import get_main_menu
from bot.menus.workers_menu import get_workers_menu
from bot.menus.worker_menu import get_user_detail_menu
from bot.menus.start_menu import get_start_menu
import logging
import io
import json
from datetime import datetime
from telegram import InputFile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

class Handler:
    _instance = None
    
    def __new__(cls, gitlab_service=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, gitlab_service=None):
        if not self._initialized:
            self.config = Config()
            self._initialized = True
            self.current_users = {}
            self.gitlab_service = gitlab_service
    
    @staticmethod
    async def error_handler(update, context):
        logger.error(f"Update {update} caused error {context.error}", exc_info=True)

    async def start(self, update, context):
        logger.info("Start command")
        await update.message.reply_text(
            text="Welcome! Press the Start button to begin:",
            reply_markup=get_start_menu()
        )

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
                user_id = context.user_data['user_mapping'][username]
                await self.select_user(update, context, user_id)
            case "Metrics":
                await self.user_metrics(update, context)
            case "Back to workers":
                await self.back_to_workers_menu(update, context)
            case _:
                await update.message.reply_text(text="Invalid option")
    
    async def workers_message(self, update, context):
        logger.info("Workers message")
        
        if 'page' not in context.user_data:
            context.user_data['page'] = 1
        
        page = context.user_data['page']
        
        users = await self.gitlab_service.get_users(page)
        
        # Create a mapping of user names to user IDs
        user_mapping = {}
        for user in users:
            name = user.get('name', user.get('username', 'Unknown'))
            user_mapping[name] = user['id']
        
        context.user_data['user_mapping'] = user_mapping
        
        reply_markup = await get_workers_menu(self.gitlab_service, page)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=reply_markup
        )
    
    async def back_to_main_menu_message(self, update, context):
        logger.info("Back to Main menu message")
        await update.message.reply_text(
            text="Choose option:",
            reply_markup=get_main_menu()
        )

    async def worker_message(self, update, context):
        logger.info("Worker message")
        reply_markup = await get_workers_menu(self.gitlab_service)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=reply_markup
        )

    async def select_user(self, update, context, user_id):
        logger.info(f"Selected user with ID: {user_id}")
        user_data = await self.gitlab_service.get_user(user_id)
        
        # Store the current user and user ID in context
        context.user_data['current_user'] = user_data.get('username', 'Unknown')
        context.user_data['current_user_id'] = user_id
        
        # Format and send user information
        user_info = f"User Information:\n"
        user_info += f"Name: {user_data.get('name', 'N/A')}\n"
        user_info += f"Username: {user_data.get('username', 'N/A')}\n"
        user_info += f"Email: {user_data.get('email', 'N/A')}\n"
        user_info += f"Status: {user_data.get('state', 'N/A')}\n"
        
        # Avatar URL information
        if user_data.get('avatar_url'):
            user_info += f"Avatar URL: {user_data.get('avatar_url', 'N/A')}\n"
        
        if user_data.get('created_at'):
            created = datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00'))
            user_info += f"Created: {created.strftime('%Y-%m-%d')}\n"
        
        await update.message.reply_text(
            text=user_info,
            reply_markup=get_user_detail_menu()
        )

    async def user_metrics(self, update, context):
        current_user = context.user_data.get('current_user', 'Unknown')
        current_user_id = context.user_data.get('current_user_id', None)
        
        if current_user == "Unknown" or not current_user_id:
            await update.message.reply_text(
                text="Cannot get user information. Please try again.",
                reply_markup=get_user_detail_menu()
            )
            return
        
        status_msg = await update.message.reply_text(
            text=f"🔍 Searching for tasks assigned to {current_user}...\n⏳ This may take some time..."
        )
        
        async def update_status(text: str, percent: int = None):
            """Callback for updating status in Telegram."""
            try:
                
                if percent is None:
                    await status_msg.edit_text(text)
                elif percent == -1:  # Error
                    await status_msg.edit_text(f"❌ {text}")
                elif percent >= 0:
                    # Create progress bar
                    bars = 10
                    filled = min(bars, percent // 10)
                    empty = bars - filled
                    progress_bar = "█" * filled + "░" * empty
                    
                    status_text = f"{text}\n\n{progress_bar} {percent}%"
                    await status_msg.edit_text(status_text)
            except Exception as e:
                logger.error(f"Error updating status: {e}")
        
        try:
            logger.info(f"Getting user metrics for {current_user}")
            # Get all tasks with progress updates
            tasks = await self.gitlab_service.get_all_historical_user_assignments(
                current_user_id, current_user, progress_callback=update_status
            )

            if not tasks:
                await status_msg.edit_text(
                    text=f"❌ No tasks assigned to {current_user}"
                )
                return
            
            logger.info(tasks)
            return
            # Get estimate time for each task
            task_details = []
            errors_count = 0
            
            for idx, task in enumerate(user_tasks, 1):
                project_id = task.get('project_id')
                issue_iid = task.get('iid')
                
                try:
                    # Update status every 5 tasks or for first/last
                    if idx % 5 == 0 or idx == 1 or idx == len(user_tasks):
                        await status_msg.edit_text(
                            text=f"⏱️ Processing tasks...\n"
                                f"📊 Progress: {idx}/{len(user_tasks)}\n"
                                f"❌ Errors: {errors_count}"
                        )
                    
                    estimated_time = await self.gitlab_service.get_task_estimate_time(
                        project_id, 
                        issue_iid
                    )
                    
                    task_info = {
                        'id': task.get('id'),
                        'iid': issue_iid,
                        'project_id': project_id,
                        'title': task.get('title', ''),
                        'state': task.get('state', ''),
                        'estimated_time': estimated_time,
                        'created_at': task.get('created_at', ''),
                        'updated_at': task.get('updated_at', ''),
                        'web_url': task.get('web_url', ''),
                        'labels': task.get('labels', []),
                        'assignee': assignee,
                    }
                    task_details.append(task_info)
                    
                except Exception as e:
                    logger.error(f"Error processing task {issue_iid}: {e}")
                    errors_count += 1
                    task_info = {
                        'id': task.get('id'),
                        'iid': issue_iid,
                        'project_id': project_id,
                        'title': task.get('title', ''),
                        'state': task.get('state', ''),
                        'estimated_time': 'N/A',
                        'error': str(e),
                        'web_url': task.get('web_url', ''),
                    }
                    task_details.append(task_info)
            
            # Create JSON report
            await status_msg.edit_text(
                text=f"📊 Generating report...\n"
                    f"✅ Processed tasks: {len(task_details)}\n"
                    f"❌ Errors: {errors_count}"
            )
            
            json_output = {
                'user': {
                    'username': current_user,
                    'user_id': current_user_id
                },
                'report_date': datetime.now().isoformat(),
                'summary': {
                    'total_tasks_found': len(user_tasks),
                    'successfully_processed': len(task_details) - errors_count,
                    'processing_errors': errors_count,
                    'tasks_with_estimates': sum(1 for t in task_details 
                                            if t.get('estimated_time') not in [0, 'N/A', None])
                },
                'tasks': []
            }
            
            # Prepare data for JSON
            for task in task_details:
                estimated = task.get('estimated_time', 0)
                
                # Format time
                if estimated in ['N/A', None] or isinstance(estimated, str):
                    formatted_time = 'N/A'
                    total_seconds = 0
                else:
                    total_seconds = estimated
                    if total_seconds == 0:
                        formatted_time = '0 seconds'
                    else:
                        days = total_seconds // 86400
                        hours = (total_seconds % 86400) // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        
                        parts = []
                        if days > 0:
                            parts.append(f"{days}d")
                        if hours > 0:
                            parts.append(f"{hours}h")
                        if minutes > 0:
                            parts.append(f"{minutes}m")
                        if seconds > 0 or not parts:
                            parts.append(f"{seconds}s")
                        
                        formatted_time = " ".join(parts)
                
                task_data = {
                    'task_id': task['iid'],
                    'title': task['title'],
                    'project_id': task['project_id'],
                    'state': task['state'].upper(),
                    'estimated_time_seconds': total_seconds,
                    'estimated_time_formatted': formatted_time,
                    'created_at': task.get('created_at'),
                    'updated_at': task.get('updated_at'),
                    'web_url': task.get('web_url'),
                    'labels': task.get('labels', []),
                    'has_error': 'error' in task
                }
                
                if 'error' in task:
                    task_data['error'] = task['error']
                
                json_output['tasks'].append(task_data)
            
            # Generate file
            json_content = json.dumps(json_output, indent=2, ensure_ascii=False)
            json_bytes = io.BytesIO(json_content.encode('utf-8'))
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filename = f"estimate_time_{current_user}_{timestamp}.json"
            
            # Send file
            await update.message.reply_document(
                document=InputFile(json_bytes, filename=json_filename),
                caption=f"⏱️ Time Estimate Report\n👤 {current_user}\n📊 {len(task_details)} tasks",
                reply_markup=get_user_detail_menu()
            )
            
            # Final message
            await status_msg.edit_text(
                text=f"✅ Report ready!\n\n"
                    f"👤 User: {current_user}\n"
                    f"📊 Total tasks: {len(task_details)}\n"
                    f"✅ Success: {len(task_details) - errors_count}\n"
                    f"❌ Errors: {errors_count}\n"
                    f"📁 File: {json_filename}"
            )
            
        except Exception as e:
            logger.error(f"Error in estimate_time: {e}")
            await status_msg.edit_text(
                text=f"❌ An error occurred:\n{str(e)[:200]}"
            )
    async def back_to_workers_menu(self, update, context):
        logger.info("Back to workers menu")
        page = context.user_data.get('page', 1)
        reply_markup = await get_workers_menu(self.gitlab_service, page)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=reply_markup
        )
    