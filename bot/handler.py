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
        
        # Show initial progress message (without menu)
        progress_msg = await update.message.reply_text(
            text=f"🔄 Collecting task history...\n"
                f"Found {len(tasks)} tasks\n"
                f"Processing: 0/{len(tasks)}"
        )
        
        # Form task information with combined history
        task_details = []
        processed_count = 0
        errors_count = 0
        
        for task in tasks:
            project_id = task.get('project_id')
            issue_iid = task.get('iid')
            
            try:
                # Get combined history (labels + assignee)
                history_data = gitlab_service.get_combined_history(project_id, issue_iid)
                
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
                    'history_data': history_data
                }
                task_details.append(task_info)
                
            except Exception as e:
                logger.error(f"Error processing task {task.get('id')}: {e}")
                errors_count += 1
                # Create minimal task info even if history fails
                task_info = {
                    'id': task.get('id'),
                    'iid': task.get('iid'),
                    'project_id': project_id,
                    'title': task.get('title', ''),
                    'state': task.get('state', ''),
                    'created_at': task.get('created_at', ''),
                    'updated_at': task.get('updated_at', ''),
                    'labels': task.get('labels', []),
                    'assignee': task.get('assignee', {}),
                    'author': task.get('author', {}),
                    'history_data': None
                }
                task_details.append(task_info)
            
            processed_count += 1
            
            # Update progress every 5 tasks (delete old message and send new one)
            if processed_count % 5 == 0 or processed_count == len(tasks):
                try:
                    # Delete old progress message
                    await progress_msg.delete()
                    
                    # Send new progress message
                    progress_msg = await update.message.reply_text(
                        text=f"🔄 Processing tasks...\n"
                            f"Progress: {processed_count}/{len(tasks)}\n"
                            f"Errors: {errors_count}"
                    )
                except Exception:
                    # If can't delete, just send new message
                    progress_msg = await update.message.reply_text(
                        text=f"🔄 Processing tasks...\n"
                            f"Progress: {processed_count}/{len(tasks)}\n"
                            f"Errors: {errors_count}"
                    )
        
        # Final progress update
        try:
            await progress_msg.edit_text(
                text=f"✅ Processing complete!\n"
                    f"Processed: {len(tasks)} tasks\n"
                    f"Errors: {errors_count}\n"
                    f"Generating report..."
            )
        except Exception:
            # If can't edit, send new message
            await update.message.reply_text(
                text=f"✅ Processing complete!\n"
                    f"Processed: {len(tasks)} tasks\n"
                    f"Errors: {errors_count}\n"
                    f"Generating report..."
            )
        
        # Create result files
        import io
        import json
        from datetime import datetime
        from telegram import InputFile
        
        # 1. TEXT FILE: Detailed task information
        text_output = io.StringIO()
        text_output.write(f"USER TASKS REPORT\n")
        text_output.write(f"User: {current_user}\n")
        text_output.write(f"User ID: {current_user_id}\n")
        text_output.write(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        text_output.write(f"Total tasks: {len(task_details)}\n")
        if errors_count > 0:
            text_output.write(f"⚠️ Errors during processing: {errors_count}\n")
        text_output.write("="*60 + "\n\n")
        
        for i, task in enumerate(task_details, 1):
            text_output.write(f"TASK #{task['iid']} (ID: {task['id']})\n")
            text_output.write(f"  Project ID: {task['project_id']}\n")
            text_output.write(f"  Title: {task['title'][:100]}{'...' if len(task['title']) > 100 else ''}\n")
            text_output.write(f"  State: {task['state'].upper()}\n")
            
            # Format dates safely
            try:
                created = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                text_output.write(f"  Created: {created.strftime('%Y-%m-%d %H:%M')}\n")
            except (ValueError, AttributeError):
                text_output.write(f"  Created: {task['created_at']}\n")
            
            try:
                updated = datetime.fromisoformat(task['updated_at'].replace('Z', '+00:00'))
                text_output.write(f"  Updated: {updated.strftime('%Y-%m-%d %H:%M')}\n")
            except (ValueError, AttributeError):
                text_output.write(f"  Updated: {task['updated_at']}\n")
            
            # Labels
            labels = task['labels']
            text_output.write(f"  Current labels: {', '.join(labels) if labels else 'No labels'}\n")
            
            # Assignee
            assignee = task['assignee']
            if assignee:
                assignee_name = assignee.get('name', assignee.get('username', 'Unknown'))
                text_output.write(f"  Current assignee: {assignee_name}\n")
            else:
                text_output.write(f"  Current assignee: Not assigned\n")
            
            # History
            history = task['history_data']
            if history and history.get('history'):
                text_output.write(f"  HISTORY ({history.get('total_events', 0)} events):\n")
                
                # Group events by type for summary
                label_events = [e for e in history['history'] if e.get('type') == 'label']
                assignee_events = [e for e in history['history'] if e.get('type') == 'assignee']
                
                text_output.write(f"    - Label changes: {len(label_events)} events\n")
                text_output.write(f"    - Assignee changes: {len(assignee_events)} events\n")
                
                # Show last 3 events (or all if less than 3)
                show_events = min(3, len(history['history']))
                if show_events > 0:
                    text_output.write(f"\n    Recent changes:\n")
                    for event in history['history'][-show_events:]:
                        try:
                            event_time = datetime.fromisoformat(event.get('timestamp', '').replace('Z', '+00:00'))
                            time_str = event_time.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, AttributeError):
                            time_str = event.get('timestamp', 'Unknown time')
                        
                        if event.get('type') == 'label':
                            text_output.write(f"      {time_str} [LABEL] '{event.get('label', 'Unknown')}' {event.get('action', 'changed')}\n")
                        elif event.get('type') == 'assignee':
                            action = event.get('action', 'changed')
                            if action == 'assigned' and event.get('assignee'):
                                text_output.write(f"      {time_str} [ASSIGNEE] Assigned to {event['assignee']}\n")
                            elif action == 'unassigned':
                                text_output.write(f"      {time_str} [ASSIGNEE] Unassigned\n")
                            elif action == 'reassigned' and event.get('assignee'):
                                text_output.write(f"      {time_str} [ASSIGNEE] Reassigned to {event['assignee']}\n")
                            else:
                                text_output.write(f"      {time_str} [ASSIGNEE] {event.get('info', 'Assignee changed')}\n")
            else:
                text_output.write(f"  HISTORY: No change history available\n")
            
            text_output.write("\n" + "="*50 + "\n\n")
        
        # Add summary statistics
        text_output.write("\n" + "="*60 + "\n")
        text_output.write("SUMMARY STATISTICS\n")
        
        total_events = sum(t['history_data']['total_events'] for t in task_details if t.get('history_data'))
        total_label_events = sum(t['history_data'].get('label_events', 0) for t in task_details if t.get('history_data'))
        total_assignee_events = sum(t['history_data'].get('assignee_events', 0) for t in task_details if t.get('history_data'))
        
        text_output.write(f"Total history events: {total_events}\n")
        text_output.write(f"- Label changes: {total_label_events}\n")
        text_output.write(f"- Assignee changes: {total_assignee_events}\n")
        
        open_tasks = len([t for t in task_details if t.get('state') == 'opened'])
        closed_tasks = len([t for t in task_details if t.get('state') == 'closed'])
        text_output.write(f"Task states: {open_tasks} open, {closed_tasks} closed\n")
        
        # Check file size limit (Telegram limit is 50MB for documents)
        text_content = text_output.getvalue()
        text_output.close()
        
        if len(text_content.encode('utf-8')) > 45 * 1024 * 1024:  # 45MB safety margin
            # Split file if too large
            await update.message.reply_text(
                text="⚠️ Report is too large for a single file. Generating summary only...",
                reply_markup=get_user_detail_menu()
            )
            
            # Send summary instead
            await update.message.reply_text(
                text=f"📊 Task Summary for {current_user}\n\n"
                    f"Total tasks: {len(task_details)}\n"
                    f"Open: {open_tasks}, Closed: {closed_tasks}\n"
                    f"History events: {total_events}\n"
                    f"• Label changes: {total_label_events}\n"
                    f"• Assignee changes: {total_assignee_events}\n"
                    f"Processing errors: {errors_count}",
                reply_markup=get_user_detail_menu()
            )
            return
        
        # Send text file
        text_bytes = io.BytesIO(text_content.encode('utf-8'))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        text_filename = f"tasks_{current_user}_{timestamp}.txt"
        
        await update.message.reply_document(
            document=InputFile(text_bytes, filename=text_filename),
            caption=f"📋 Task report for {current_user} ({len(task_details)} tasks)",
            reply_markup=get_user_detail_menu()
        )
        
        # Optional: Send JSON file if requested
        if len(tasks) <= 50:  # Only for reasonable number of tasks
            try:
                json_output = {
                    'user': current_user,
                    'user_id': current_user_id,
                    'report_date': datetime.now().isoformat(),
                    'total_tasks': len(task_details),
                    'errors_count': errors_count,
                    'tasks': []
                }
                
                for task in task_details:
                    json_task = {
                        'id': task.get('id'),
                        'iid': task.get('iid'),
                        'project_id': task.get('project_id'),
                        'title': task.get('title'),
                        'state': task.get('state'),
                        'created_at': task.get('created_at'),
                        'updated_at': task.get('updated_at'),
                        'labels': task.get('labels'),
                        'assignee': task.get('assignee'),
                        'author': task.get('author'),
                    }
                    
                    if task.get('history_data'):
                        json_task['history_summary'] = {
                            'total_events': task['history_data'].get('total_events', 0),
                            'label_events': task['history_data'].get('label_events', 0),
                            'assignee_events': task['history_data'].get('assignee_events', 0)
                        }
                        # Include only first 20 history events to keep file size reasonable
                        json_task['history_events'] = task['history_data'].get('history', [])[:20]
                    
                    json_output['tasks'].append(json_task)
                
                json_bytes = io.BytesIO(json.dumps(json_output, indent=2, ensure_ascii=False).encode('utf-8'))
                json_filename = f"tasks_{current_user}_{timestamp}.json"
                
                await update.message.reply_document(
                    document=InputFile(json_bytes, filename=json_filename),
                    caption="📊 Structured data (JSON)",
                    reply_markup=get_user_detail_menu()
                )
            except Exception as e:
                logger.error(f"Error creating JSON file: {e}")
                await update.message.reply_text(
                    text="⚠️ Could not create JSON file due to size constraints",
                    reply_markup=get_user_detail_menu()
                )
        
        # Final message
        await update.message.reply_text(
            text=f"✅ Report generation complete!\n\n"
                f"User: {current_user}\n"
                f"Tasks processed: {len(tasks)}\n"
                f"Files sent: Text report{' + JSON data' if len(tasks) <= 50 else ''}",
            reply_markup=get_user_detail_menu()
        )

    async def back_to_workers_menu(self, update, context):
        logger.info("Back to workers menu")
        # Get the current page from user context, default to 1 if not set
        page = context.user_data.get('page', 1)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_worker_menu(page)
        )
        
        