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
from services.LLMService import LLMService
from services.WhisperService import get_whisper_service
import aiohttp
import tempfile
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

class Handler:
    """
    Main handler class for processing Telegram bot messages and commands.
    
    This class handles all user interactions with the bot, including:
    - Processing commands like /start
    - Handling text messages for task creation
    - Processing voice messages through transcription
    - Managing user navigation through different menus
    - Calculating and displaying user metrics
    
    The class implements a singleton pattern to ensure only one instance exists.
    
    Example:
        >>> handler = Handler(gitlab_service)
        >>> # Use the handler to process updates
    """
    _instance = None
    
    def __new__(cls, gitlab_service=None):
        """
        Singleton implementation to ensure only one instance of Handler exists.
        
        Args:
            gitlab_service: Optional GitLab service instance to inject
            
        Returns:
            Handler: The single instance of the Handler class
            
        Example:
            >>> handler = Handler()
            >>> # This will always return the same instance
            >>> handler2 = Handler()
            >>> assert handler is handler2
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, gitlab_service=None):
        """
        Initialize the Handler instance with configuration and services.
        
        Args:
            gitlab_service: Optional GitLab service instance to inject
            
        Note:
            This method is part of the singleton pattern implementation and
            should not be called directly. Use the class constructor instead.
        """
        if not self._initialized:
            self.config = Config()
            self._initialized = True
            self.current_users = {}
            self.gitlab_service = gitlab_service
            self.llm_service = LLMService()
            self.whisper_service = get_whisper_service()  # Initialize WhisperService
    
    @staticmethod
    async def error_handler(update, context):
        """
        Handle errors that occur during bot operation.
        
        This method logs errors that occur during bot operation, providing
        debugging information for troubleshooting.
        
        Args:
            update: The update object that caused the error
            context: The context object containing error information
            
        Example:
            This method is automatically called by the Telegram bot framework
            when an unhandled exception occurs during message processing.
        """
        logger.error(f"Update {update} caused error {context.error}", exc_info=True)

    async def start(self, update, context):
        """
        Handle the /start command from users.
        
        This method responds to the /start command by sending a welcome message
        and presenting the start menu to the user.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user sends "/start" command to the bot, this method is triggered
            and sends a welcome message with the start menu.
        """
        logger.info("Start command")
        await update.message.reply_text(
            text="Welcome! Press the Start button to begin:",
            reply_markup=get_start_menu()
        )

    async def handle_message(self, update, context):
        """
        Handle incoming text messages from users and route them to appropriate functions.
        
        This method processes different types of text messages and routes them to
        the appropriate handler functions based on the message content.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            - If a user sends "Start", it shows the start menu
            - If a user sends "Workers", it shows the list of GitLab users
            - If a user sends a username, it shows user details
            - If a user sends other text, it tries to create a task
        """
        # First check if there is a voice message
        if update.message.voice:
            await self.handle_voice(update, context)
            return
        
        # Если нет голосового, обрабатываем текст
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
                await self.create_task(update, context, text)

    async def handle_voice(self, update, context):
        """
        Handle incoming voice messages from users.
        
        This method processes voice messages by transcribing them using the
        Whisper service and then treating the transcribed text as a command
        or task creation request.
        
        Args:
            update: The update object containing the voice message
            context: The context object for the handler
            
        Example:
            When a user sends a voice message saying "Create a login page task for John",
            this method transcribes the message and processes it as a task creation request.
        """
        logger.info("Received voice message")
        
        # Prepare status message
        status_msg = await update.message.reply_text(
            text="🎙️ Processing voice message..."
        )
        
        try:
            # Получаем голосовое сообщение
            voice = update.message.voice
            file_id = voice.file_id
            
            # Получаем файл из Telegram
            voice_file = await context.bot.get_file(file_id)
            
            # Download voice message to memory
            voice_bytes = io.BytesIO()
            await voice_file.download_to_memory(voice_bytes)
            
            # Check WhisperService availability
            if not await self.whisper_service.is_available():
                await status_msg.edit_text(
                    text="❌ Speech recognition service is not available. "
                         "Please check OpenAI API key configuration."
                )
                return
            
            # Transcribe voice message
            await status_msg.edit_text(
                text="🎤 Transcribing voice message..."
            )
            
            transcription_result = await self.whisper_service.transcribe_telegram_voice(
                voice_bytes.getvalue(),
                language="ru"
            )
            
            if not transcription_result.get('success', False):
                await status_msg.edit_text(
                    text="❌ Could not transcribe the voice message. Please try again."
                )
                return
            
            transcribed_text = transcription_result.get('text', '').strip()
            
            if not transcribed_text:
                await status_msg.edit_text(
                    text="❌ No speech detected in the voice message."
                )
                return
            
            # Show user what we recognized
            await status_msg.edit_text(
                text=f"✅ **Voice message transcribed:**\n\n{transcribed_text}\n\n"
                     f"Processing as command..."
            )
            
            # Now process the recognized text
            # We can simply call create_task directly or handle_message
            # Let's call create_task to create a task
            await self.create_task(update, context, transcribed_text)
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {e}")
            await status_msg.edit_text(
                text="❌ Error downloading voice message. Please try again."
            )
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            await status_msg.edit_text(
                text=f"❌ {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error processing voice message: {e}", exc_info=True)
            
            error_message = "❌ An error occurred while processing the voice message."
            
            # Более детальные ошибки
            if "authentication" in str(e).lower():
                error_message = "❌ OpenAI API authentication failed. Please check API key."
            elif "quota" in str(e).lower() or "limit" in str(e).lower():
                error_message = "❌ OpenAI API quota exceeded. Please check your account."
            
            await status_msg.edit_text(text=error_message)
    
    async def workers_message(self, update, context):
        """
        Handle the workers message request, displaying paginated list of GitLab users.
        
        This method retrieves and displays a paginated list of GitLab users, creating
        a mapping of user names to IDs for later reference.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user selects "Workers" from the main menu, this method
            retrieves the first page of users from GitLab and displays them.
        """
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
        """
        Handle returning to the main menu.
        
        This method returns the user to the main menu with available options.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user selects "Main menu" from any submenu, this method
            displays the main menu options to the user.
        """
        logger.info("Back to Main menu message")
        await update.message.reply_text(
            text="Choose option:",
            reply_markup=get_main_menu()
        )

    async def worker_message(self, update, context):
        """
        Handle the worker message request, displaying list of GitLab users.
        
        This method retrieves and displays the first page of GitLab users.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user selects "Workers" from the main menu, this method
            retrieves and displays the first page of users from GitLab.
        """
        logger.info("Worker message")
        reply_markup = await get_workers_menu(self.gitlab_service)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=reply_markup
        )

    async def select_user(self, update, context, user_id):
        """
        Handle user selection, displaying detailed information about the selected user.
        
        This method retrieves and displays detailed information about a selected GitLab user,
        including their name, username, email, status, avatar URL, and creation date.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            user_id: The ID of the selected user
            
        Example:
            When a user taps on a username from the workers list, this method
            retrieves the user's information from GitLab and displays it.
        """
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
            
        Example:
            >>> print(Handler.format_duration(7845))
            "2h 10m 45s"
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
            
        Example:
            >>> print(Handler.format_duration_short(7845))
            "2.2h"
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
        """
        Handle user metrics request, calculating and displaying detailed metrics for the selected user.
        
        This method retrieves all tasks assigned to a user and calculates metrics
        such as time spent in different development stages (work, review, QA).
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user selects "Metrics" from the user detail menu, this method
            retrieves all tasks for the selected user and generates a comprehensive
            report with time metrics.
        """
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
        """
        Handle returning to the workers menu with pagination.
        
        This method returns the user to the workers menu, maintaining the current
        page number in the pagination.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            
        Example:
            When a user selects "Back to workers" from the user detail menu,
            this method displays the workers list at the same page they were on previously.
        """
        logger.info("Back to workers menu")
        page = context.user_data.get('page', 1)
        reply_markup = await get_workers_menu(self.gitlab_service, page)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=reply_markup
        )
    
    async def create_task(self, update, context, text):
        """
        Handle creating a task.
        
        This method processes a user's text message and creates a GitLab task
        based on the content using AI-powered analysis.
        
        Args:
            update: The update object containing the message
            context: The context object for the handler
            text: The message text from user
            
        Example:
            When a user sends a message like "Create a login page for John Doe",
            this method uses AI to parse the request and create a corresponding
            GitLab task with appropriate assignment and labels.
        """
        logger.info(f"Creating task from message: {text}")
        
        status_msg = None
        
        try:
            # Send initial status message
            status_msg = await update.message.reply_text(
                text="🔍 Analyzing task..."
            )
            
            # Step 1: Get users from GitLab
            await status_msg.edit_text(
                text="🔍 Getting user list..."
            )
            
            users = await self.gitlab_service.get_all_users()
            if not users:
                await status_msg.edit_text(
                    text="❌ Failed to get user list from GitLab"
                )
                return
                
            user_names = [user['name'] for user in users]
            user_name_to_id = {user['name']: user['id'] for user in users}
            
            # Step 2: Analyze with LLM
            await status_msg.edit_text(
                text="🤖 Analyzing task with AI..."
            )
            
            structured_data = await self.llm_service.process_task_assignment(
                workers=user_names,
                user_message=text
            )
            
            # Step 3: Prepare task data
            await status_msg.edit_text(
                text="⚙️ Preparing data for task creation..."
            )
            
            # Get assignee_id
            assignee_id = None
            assignee_name = structured_data.get('assignee_name')
            
            if assignee_name:
                assignee_id = user_name_to_id.get(assignee_name)
                if not assignee_id:
                    logger.warning(f"User '{assignee_name}' not found. Available: {list(user_name_to_id.keys())}")
            
            # Convert project_id
            project_id_str = structured_data.get('project_id', str(self.config.default_project_id))
            try:
                project_id = int(project_id_str)
            except ValueError:
                logger.warning(f"Invalid project_id '{project_id_str}', using default {self.config.default_project_id}")
                project_id = self.config.default_project_id
            
            # Step 4: Get labels from GitLab
            await status_msg.edit_text(
                text="🔍 Getting labels..."
            )
            
            project_labels = await self.gitlab_service.get_labels_from_project_id(project_id)
            if not project_labels:
                await status_msg.edit_text(
                    text="❌ Failed to get labels from GitLab"
                )
                return
            
            await status_msg.edit_text(
                text="🤖 Setting labels with AI..."
            )
            
            # Get labels using LLM
            labels = []
            try:
                # Формируем метки как словарь для лучшего понимания LLM
                labels_info = []
                for label in project_labels:
                    if 'name' in label:
                        label_info = {
                            'name': label['name'],
                            'description': label.get('description', '')
                        }
                        labels_info.append(label_info)
                
                labels_result = await self.llm_service.set_labels(
                    labels=labels_info,  # Теперь передаем словари вместо строк
                    user_message=text
                )
                labels = labels_result.get('labels', [])
            except ValueError as e:
                logger.warning(f"Invalid labels response: {e}")
                labels = []
                
            # Step 6: Create task in GitLab
            await status_msg.edit_text(
                text="🚀 Creating task in GitLab..."
            )
            
            task = await self.gitlab_service.create_new_task(
                project_id=project_id,
                task_name=structured_data.get('title', 'New task'),
                task_description=structured_data.get('description', ''),
                assignee_id=assignee_id,
                labels=labels
            )
   
            # Step 7: Send success message
            task_url = task.get('web_url', '#')
            task_iid = task.get('iid', '?')
            task_title = task.get('title', 'New task')
            
            success_text = (
                f"✅ *Task created successfully!*\n\n"
                f"*Task:* #{task_iid} {task_title}\n"
                f"*Project:* {project_id}\n"
            )
            
            if assignee_name:
                if assignee_id:
                    success_text += f"*Assignee:* {assignee_name}\n"
                else:
                    success_text += f"*Assignee:* {assignee_name} (not assigned)\n"
            
            if labels:
                success_text += f"*Labels:* {', '.join(labels)}\n"

            success_text += f"\n[🔗 Open task]({task_url})"
            
            await status_msg.edit_text(
                text=success_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            logger.info(f"Task created successfully: {task.get('web_url')}")
            
        except Exception as e:
            logger.error(f"Error creating task: {e}", exc_info=True)
            
            if status_msg:
                error_message = "❌ *Task creation error*\n\n"
                
                if isinstance(e, json.JSONDecodeError):
                    error_message += "AI could not properly analyze the task. Try to formulate differently."
                elif isinstance(e, aiohttp.ClientError):
                    error_message += "Connection problem with services. Try again later."
                else:
                    error_message += f"An error occurred: {str(e)}"
                
                await status_msg.edit_text(
                    text=error_message,
                    parse_mode='Markdown'
                )