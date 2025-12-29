from bot.config import Config
from bot.menus.main_menu import get_main_menu
from bot.menus.workers_menu import get_workers_menu
from bot.menus.worker_menu import get_worker_menu, get_user_detail_menu
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
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = Config()
            self._initialized = True
            self.current_users = {}
    
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
            case "All user tasks":
                await self.all_tasks(update, context)
            case "Estimate Time":
                await self.estimate_time(update, context)
            case "Back to workers":
                await self.back_to_workers_menu(update, context)
            case _:
                await update.message.reply_text(text="Invalid option")
    
    async def workers_message(self, update, context):
        logger.info("Workers message")
        
        if 'page' not in context.user_data:
            context.user_data['page'] = 1
        
        page = context.user_data['page']
        
        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        users = gitlab_service.get_users(page)
        
        # Create a mapping of user names to user IDs
        user_mapping = {}
        for user in users:
            name = user.get('name', user.get('username', 'Unknown'))
            user_mapping[name] = user['id']
        
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

    async def all_tasks(self, update, context):
        current_user = context.user_data.get('current_user', 'Unknown')
        current_user_id = context.user_data.get('current_user_id', None)
        
        if current_user == "Unknown" or not current_user_id:
            await update.message.reply_text(
                text="Cannot get user information. Please try again.",
                reply_markup=get_worker_menu()
            )
            return

        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        
        # Show initial message
        await update.message.reply_text(
            text=f"🔍 Searching for all tasks where {current_user} was assignee...\n"
                 f"This may take a while for large projects...",
            reply_markup=get_user_detail_menu()
        )
        
        # Get all tasks where user was assignee at any time
        progress_msg = await update.message.reply_text(
            text="Starting task search..."
        )
        
        try:
            # Use historical search method
            tasks = gitlab_service.get_user_tasks(current_user_id)
            
            if not tasks:
                await progress_msg.edit_text(
                    text=f"No tasks found where {current_user} was ever assignee."
                )
                await update.message.reply_text(
                    text="No tasks found for this user.",
                    reply_markup=get_user_detail_menu()
                )
                return
            
            await progress_msg.edit_text(
                text=f"✅ Found {len(tasks)} tasks\n"
                     f"Now processing history for each task..."
            )
            
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            await progress_msg.edit_text(
                text=f"❌ Error searching for tasks: {str(e)}"
            )
            return
        
        # Process each task to get history
        task_details = []
        processed_count = 0
        errors_count = 0
        
        for task in tasks:
            project_id = task.get('project_id')
            issue_iid = task.get('iid')
            
            try:
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
                # Create minimal task info
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
            
            # Update progress
            if processed_count % 5 == 0 or processed_count == len(tasks):
                try:
                    await progress_msg.edit_text(
                        text=f"🔄 Processing tasks...\n"
                             f"Progress: {processed_count}/{len(tasks)}\n"
                             f"Errors: {errors_count}"
                    )
                except Exception:
                    pass
        
        # Generate report
        await progress_msg.edit_text(
            text=f"✅ Processing complete!\n"
                 f"Generating report for {len(task_details)} tasks..."
        )
        
        # Create text report
        text_output = io.StringIO()
        text_output.write(f"USER TASKS REPORT\n")
        text_output.write(f"User: {current_user}\n")
        text_output.write(f"User ID: {current_user_id}\n")
        text_output.write(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        text_output.write(f"Total tasks found: {len(task_details)}\n")
        
        if errors_count > 0:
            text_output.write(f"Processing errors: {errors_count}\n")
        
        text_output.write("="*60 + "\n\n")
        
        # Add task details
        for i, task in enumerate(task_details, 1):
            text_output.write(f"TASK #{task['iid']}\n")
            text_output.write(f"  Project ID: {task['project_id']}\n")
            text_output.write(f"  Title: {task['title'][:100]}{'...' if len(task['title']) > 100 else ''}\n")
            text_output.write(f"  State: {task['state'].upper()}\n")
            
            # Format dates
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
            
            # Current labels
            labels = task['labels']
            text_output.write(f"  Current labels: {', '.join(labels) if labels else 'None'}\n")
            
            # Current assignee
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
                
                label_events = [e for e in history['history'] if e.get('type') == 'label']
                assignee_events = [e for e in history['history'] if e.get('type') == 'assignee']
                
                text_output.write(f"    - Label changes: {len(label_events)} events\n")
                text_output.write(f"    - Assignee changes: {len(assignee_events)} events\n")
                
                # Show recent events
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
                text_output.write(f"  HISTORY: Not available\n")
            
            text_output.write("\n" + "="*50 + "\n\n")
        
        # Add summary
        text_output.write("\n" + "="*60 + "\n")
        text_output.write("SUMMARY\n")
        
        total_events = sum(t['history_data']['total_events'] for t in task_details if t.get('history_data'))
        total_label_events = sum(t['history_data'].get('label_events', 0) for t in task_details if t.get('history_data'))
        total_assignee_events = sum(t['history_data'].get('assignee_events', 0) for t in task_details if t.get('history_data'))
        
        open_tasks = len([t for t in task_details if t.get('state') == 'opened'])
        closed_tasks = len([t for t in task_details if t.get('state') == 'closed'])
        
        text_output.write(f"Total history events: {total_events}\n")
        text_output.write(f"  - Label changes: {total_label_events}\n")
        text_output.write(f"  - Assignee changes: {total_assignee_events}\n")
        text_output.write(f"Task status: {open_tasks} open, {closed_tasks} closed\n")
        
        # Send text report
        text_content = text_output.getvalue()
        text_output.close()
        
        # Check file size
        if len(text_content.encode('utf-8')) > 45 * 1024 * 1024:
            await update.message.reply_text(
                text="⚠️ Report is too large. Generating summary only...",
                reply_markup=get_user_detail_menu()
            )
            
            await update.message.reply_text(
                text=f"📊 Summary for {current_user}\n\n"
                     f"Total tasks: {len(task_details)}\n"
                     f"Open: {open_tasks}, Closed: {closed_tasks}\n"
                     f"History events: {total_events}\n"
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
        
        # Create and send JSON file
        try:
            json_output = {
                'user': {
                    'username': current_user,
                    'user_id': current_user_id
                },
                'report_date': datetime.now().isoformat(),
                'summary': {
                    'total_tasks': len(task_details),
                    'open_tasks': open_tasks,
                    'closed_tasks': closed_tasks,
                    'total_history_events': total_events,
                    'label_events': total_label_events,
                    'assignee_events': total_assignee_events,
                    'processing_errors': errors_count
                },
                'tasks': []
            }
            
            for task in task_details:
                json_task = {
                    'id': task.get('id'),
                    'iid': task.get('iid'),
                    'project_id': task.get('project_id'),
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'state': task.get('state'),
                    'created_at': task.get('created_at'),
                    'updated_at': task.get('updated_at'),
                    'labels': task.get('labels'),
                    'assignee': task.get('assignee'),
                    'author': task.get('author')
                }
                
                if task.get('history_data'):
                    history = task['history_data']
                    json_task['history_summary'] = {
                        'total_events': history.get('total_events', 0),
                        'label_events': history.get('label_events', 0),
                        'assignee_events': history.get('assignee_events', 0)
                    }
                    
                    # Include all history events in JSON
                    json_task['history_events'] = history.get('history', [])
                
                json_output['tasks'].append(json_task)
            
            # Create JSON file
            json_bytes = io.BytesIO(json.dumps(json_output, indent=2, ensure_ascii=False).encode('utf-8'))
            json_filename = f"tasks_{current_user}_{timestamp}.json"
            
            await update.message.reply_document(
                document=InputFile(json_bytes, filename=json_filename),
                caption="📊 Structured data (JSON format)",
                reply_markup=get_user_detail_menu()
            )
            
        except Exception as e:
            logger.error(f"Error creating JSON file: {e}")
            await update.message.reply_text(
                text="⚠️ Could not create JSON file due to size constraints",
                reply_markup=get_user_detail_menu()
            )
        
        # Final summary message
        await update.message.reply_text(
            text=f"✅ Report generation complete!\n\n"
                 f"User: {current_user}\n"
                 f"Total tasks: {len(task_details)}\n"
                 f"Files generated:\n"
                 f"• {text_filename} (Text report)\n"
                 f"• {json_filename} (JSON data)\n\n"
                 f"Open: {open_tasks} | Closed: {closed_tasks}\n"
                 f"History events: {total_events}",
            reply_markup=get_user_detail_menu()
        )
        
        # Clean up progress message
        try:
            await progress_msg.delete()
        except Exception:
            pass

    async def estimate_time(self, update, context):
        current_user = context.user_data.get('current_user', 'Unknown')
        current_user_id = context.user_data.get('current_user_id', None)
        
        if current_user == "Unknown" or not current_user_id:
            await update.message.reply_text(
                text="Cannot get user information. Please try again.",
                reply_markup=get_user_detail_menu()
            )
            return

        from services.GitLabService import GitLabService
        gitlab_service = GitLabService()
        
        # Show initial message
        await update.message.reply_text(
            text=f"🔍 Searching for all tasks where {current_user} was assignee...\n"
                 f"This may take a while for large projects...",
            reply_markup=get_user_detail_menu()
        )
        
        # Get all tasks where user was assignee at any time
        progress_msg = await update.message.reply_text(
            text="Starting task search..."
        )
        
        try:
            # Use historical search method
            tasks = gitlab_service.get_user_tasks(current_user_id)
            
            if not tasks:
                await progress_msg.edit_text(
                    text=f"No tasks found where {current_user} was ever assignee."
                )
                await update.message.reply_text(
                    text="No tasks found for this user.",
                    reply_markup=get_user_detail_menu()
                )
                return
            
            await progress_msg.edit_text(
                text=f"✅ Found {len(tasks)} tasks\n"
                     f"Now processing estimate times for each task..."
            )
            
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            await progress_msg.edit_text(
                text=f"❌ Error searching for tasks: {str(e)}"
            )
            return
        
        # Process each task to get estimate time
        task_details = []
        processed_count = 0
        errors_count = 0
        
        for task in tasks:
            project_id = task.get('project_id')
            issue_iid = task.get('iid')
            
            try:
                # Get the task details with estimate time
                estimated_time = gitlab_service.get_task_estimate_time(project_id, issue_iid)
                
                task_info = {
                    'id': task.get('id'),
                    'iid': task.get('iid'),
                    'project_id': project_id,
                    'title': task.get('title', ''),
                    'state': task.get('state', ''),
                    'estimated_time': estimated_time,
                    'created_at': task.get('created_at', ''),
                    'updated_at': task.get('updated_at', ''),
                    'labels': task.get('labels', []),
                    'assignee': task.get('assignee', {}),
                    'author': task.get('author', {})
                }
                task_details.append(task_info)
                
            except Exception as e:
                logger.error(f"Error processing task {task.get('id')}: {e}")
                errors_count += 1
                # Create minimal task info
                task_info = {
                    'id': task.get('id'),
                    'iid': task.get('iid'),
                    'project_id': project_id,
                    'title': task.get('title', ''),
                    'state': task.get('state', ''),
                    'estimated_time': 'N/A',
                    'created_at': task.get('created_at', ''),
                    'updated_at': task.get('updated_at', ''),
                    'labels': task.get('labels', []),
                    'assignee': task.get('assignee', {}),
                    'author': task.get('author', {})
                }
                task_details.append(task_info)
            
            processed_count += 1
            
            # Update progress
            if processed_count % 5 == 0 or processed_count == len(tasks):
                try:
                    await progress_msg.edit_text(
                        text=f"🔄 Processing tasks...\n"
                             f"Progress: {processed_count}/{len(tasks)}\n"
                             f"Errors: {errors_count}"
                    )
                except Exception:
                    pass
        
        # Create JSON report
        await progress_msg.edit_text(
            text=f"✅ Processing complete!\n"
                 f"Generating estimate time report for {len(task_details)} tasks..."
        )
        
        # Create JSON report
        import json
        import io
        
        # Format the task details for JSON
        json_output = {
            'user': {
                'username': current_user,
                'user_id': current_user_id
            },
            'report_date': datetime.now().isoformat(),
            'summary': {
                'total_tasks': len(task_details),
                'processing_errors': errors_count
            },
            'tasks': []
        }
        
        for task in task_details:
            # Format estimated time
            estimated_time_seconds = task.get('estimated_time', 0)
            if estimated_time_seconds != 'N/A':
                # Convert seconds to human readable format (days, hours, minutes)
                if estimated_time_seconds == 0:
                    formatted_time = '0 seconds'
                else:
                    days = estimated_time_seconds // 86400
                    hours = (estimated_time_seconds % 86400) // 3600
                    minutes = (estimated_time_seconds % 3600) // 60
                    seconds = estimated_time_seconds % 60
                    
                    formatted_parts = []
                    if days > 0:
                        formatted_parts.append(f"{days}d")
                    if hours > 0:
                        formatted_parts.append(f"{hours}h")
                    if minutes > 0:
                        formatted_parts.append(f"{minutes}m")
                    if seconds > 0 or not formatted_parts:
                        formatted_parts.append(f"{seconds}s")
                    
                    formatted_time = " ".join(formatted_parts)
            else:
                formatted_time = 'N/A'
            
            task_data = {
                'Task ID': task['iid'],
                'Task Title': task['title'],
                'Project ID': task['project_id'],
                'State': task['state'].upper(),
                'Estimated Time (formatted)': formatted_time,
                'Labels': task.get('labels', [])
            }
            
            json_output['tasks'].append(task_data)
        
        # Convert to JSON string and then to bytes
        json_content = json.dumps(json_output, indent=2, ensure_ascii=False)
        json_bytes = io.BytesIO(json_content.encode('utf-8'))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"estimate_time_{current_user}_{timestamp}.json"
        
        await update.message.reply_document(
            document=InputFile(json_bytes, filename=json_filename),
            caption=f"⏱️ Estimate time report for {current_user} ({len(task_details)} tasks)",
            reply_markup=get_user_detail_menu()
        )
        
        # Final summary message
        await update.message.reply_text(
            text=f"✅ Estimate time report generation complete!\n\n"
                 f"User: {current_user}\n"
                 f"Total tasks: {len(task_details)}\n"
                 f"File: {json_filename}\n\n"
                 f"Processing errors: {errors_count}",
            reply_markup=get_user_detail_menu()
        )
        
        # Clean up progress message
        try:
            await progress_msg.delete()
        except Exception:
            pass

    async def back_to_workers_menu(self, update, context):
        logger.info("Back to workers menu")
        page = context.user_data.get('page', 1)
        await update.message.reply_text(
            text="Select a user:",
            reply_markup=get_worker_menu(page)
        )
