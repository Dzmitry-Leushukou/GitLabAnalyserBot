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

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Convert seconds to human-readable format (days, hours, minutes, seconds).
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Human-readable string (e.g., "2d 5h 30m 15s")
        """
        if not seconds or seconds <= 0:
            return "0s"
        
        # Convert to integer seconds for cleaner output
        total_seconds = int(round(seconds))
        
        # Calculate time components
        days = total_seconds // (24 * 3600)
        hours = (total_seconds % (24 * 3600)) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Build the formatted string
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:  # Always show at least seconds if no other parts
            parts.append(f"{seconds}s")
        
        return " ".join(parts)

    @staticmethod
    def format_duration_short(seconds: float) -> str:
        """
        Convert seconds to short human-readable format (prioritizing largest units).
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Short human-readable string (e.g., "2.5h", "45m", "1d 3h")
        """
        if not seconds or seconds <= 0:
            return "0s"
        
        total_seconds = int(round(seconds))
        
        # Calculate time components
        days = total_seconds // (24 * 3600)
        hours = (total_seconds % (24 * 3600)) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # For short format, prioritize showing 1-2 most significant units
        if days > 0:
            # Show days and possibly hours
            if hours > 0:
                return f"{days}d {hours}h"
            return f"{days}d"
        elif hours > 0:
            # Show hours and possibly minutes
            remaining_minutes = minutes + (seconds / 60)
            if remaining_minutes >= 30:
                return f"{hours + 0.5:.1f}h"  # Show half hours
            elif minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours}h"
        elif minutes > 0:
            # Show minutes and possibly seconds
            if seconds > 0:
                return f"{minutes}m {seconds}s"
            return f"{minutes}m"
        else:
            return f"{seconds}s"

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
                    percent_int = int(round(percent))
                    filled = int(min(bars, percent_int // 10))
                    empty = bars - filled
                    progress_bar = "█" * filled + "░" * empty
                    
                    status_text = f"{text}\n\n{progress_bar} {percent_int}%"
                    await status_msg.edit_text(status_text)
            except Exception as e:
                logger.error(f"Error updating status: {e}")
        
        try:
            logger.info(f"Getting user metrics for {current_user}")
            # Get all tasks with progress updates
            tasks = await self.gitlab_service.get_user_metrics(
                current_user_id, current_user, progress_callback=update_status
            )

            if not tasks:
                await status_msg.edit_text(
                    text=f"❌ No tasks assigned to {current_user}"
                )
                return
            
            # Calculate summary metrics from already calculated task metrics
            total_cicle_time = 0
            total_review_time = 0
            total_qa_time = 0
            tasks_with_metrics = 0
            
            # Create JSON report   
            await update_status("📊 Generating report...", 0)
            json_output = {
                'user': {
                    'username': current_user,
                    'user_id': current_user_id
                },
                'report_date': datetime.now().isoformat(),
                'summary': {
                    'total_tasks_found': len(tasks),
                    'total_cicle_time_seconds': 0,
                    'total_review_time_seconds': 0,
                    'total_qa_time_seconds': 0,
                    'total_cicle_time_hours': 0,
                    'total_review_time_hours': 0,
                    'total_qa_time_hours': 0,
                    'tasks_with_metrics': 0
                }
            }
            
            # Prepare data for JSON
            json_output['tasks'] = []

            for index, task in enumerate(tasks):
                # Extract base task data
                task_data = {
                    'project_id': task.get('project_id'),
                    'task_id': task.get('iid'),
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'state': task.get('state', '').upper(),
                    'created_at': task.get('created_at'),
                    'updated_at': task.get('updated_at'),
                    'closed_at': task.get('closed_at') or "",
                    'web_url': task.get('web_url'),
                    'labels': task.get('labels', []),
                    'merged_history': task.get('merged_history', [])
                }
                
                # Add already calculated metrics from GitLabService
                if 'cicle_time' in task:
                    cicle_time = task.get('cicle_time', 0)
                    review_time = task.get('review_time', 0)
                    qa_time = task.get('qa_time', 0)
                    
                    task_data['metrics'] = {
                        'cicle_time': cicle_time,
                        'cicle_history': task.get('cicle_history', []),
                        'review_time': review_time,
                        'review_history': task.get('review_history', []),
                        'qa_time': qa_time,
                        'qa_history': task.get('qa_history', [])
                    }
                    
                    # Add human-readable formatted time
                    task_data['metrics_human_readable'] = {
                        'cicle_time': self.format_duration(cicle_time),
                        'cicle_time_short': self.format_duration_short(cicle_time),
                        'review_time': self.format_duration(review_time),
                        'review_time_short': self.format_duration_short(review_time),
                        'qa_time': self.format_duration(qa_time),
                        'qa_time_short': self.format_duration_short(qa_time)
                    }
                    
                    # Add formatted time in hours for readability
                    task_data['metrics_formatted'] = {
                        'cicle_time_hours': round(cicle_time / 3600, 2),
                        'review_time_hours': round(review_time / 3600, 2),
                        'qa_time_hours': round(qa_time / 3600, 2)
                    }
                    
                    # Update summary totals
                    total_cicle_time += cicle_time
                    total_review_time += review_time
                    total_qa_time += qa_time
                    tasks_with_metrics += 1
                
                if 'error' in task:
                    task_data['error'] = task['error']
                
                json_output['tasks'].append(task_data)
                
                # Update progress every 5 tasks
                if index % 5 == 0:
                    progress = ((index + 1) / len(tasks)) * 100
                    await update_status("📊 Generating report with metrics...", progress)
            
            # Update summary with calculated totals
            json_output['summary'].update({
                'total_cicle_time_seconds': total_cicle_time,
                'total_review_time_seconds': total_review_time,
                'total_qa_time_seconds': total_qa_time,
                'total_cicle_time_hours': round(total_cicle_time / 3600, 2),
                'total_review_time_hours': round(total_review_time / 3600, 2),
                'total_qa_time_hours': round(total_qa_time / 3600, 2),
                'tasks_with_metrics': tasks_with_metrics,
                'total_time_human_readable': {
                    'cicle_time': self.format_duration(total_cicle_time),
                    'review_time': self.format_duration(total_review_time),
                    'qa_time': self.format_duration(total_qa_time),
                    'total_combined': self.format_duration(total_cicle_time + total_review_time + total_qa_time)
                }
            })
            
            # Generate file
            await update_status("📊 Finalizing report...", 95)
            json_content = json.dumps(json_output, indent=2, ensure_ascii=False)
            json_bytes = io.BytesIO(json_content.encode('utf-8'))
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filename = f"{current_user}_metrics_{timestamp}.json"
            
            await update_status("📊 Report generated!", 100)

            total_combined = total_cicle_time + total_review_time + total_qa_time
            caption = (
                f"✅ Report ready!\n\n"
                f"👤 User: {current_user}\n"
                f"📈 Total tasks analyzed: {len(tasks)}\n"
                f"⏱️ Tasks with metrics: {tasks_with_metrics}\n\n"
                f"⏰ Time in work: {self.format_duration(total_cicle_time)} "
                f"({round(total_cicle_time / 3600, 2)} hours)\n"
                f"👁️ Time in review: {self.format_duration(total_review_time)} "
                f"({round(total_review_time / 3600, 2)} hours)\n"
                f"🧪 Time in QA: {self.format_duration(total_qa_time)} "
                f"({round(total_qa_time / 3600, 2)} hours)\n\n"
                f"📊 Total combined time: {self.format_duration(total_combined)} "
                f"({round(total_combined / 3600, 2)} hours)\n\n"
                f"📁 File: {json_filename}"
            )

            await update.message.reply_document(
                document=InputFile(json_bytes, filename=json_filename),
                caption=caption,
                reply_markup=get_user_detail_menu()
            )

            await status_msg.delete()
            return
            
        except Exception as e:
            logger.error(f"Error in user_metrics: {e}", exc_info=True)
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
    