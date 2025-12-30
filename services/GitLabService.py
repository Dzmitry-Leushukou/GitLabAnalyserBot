from services.config import Config
import logging
import aiohttp
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

class GitLabService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = Config()
            self._session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is initialized."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'Authorization': f'Bearer {self.config.gitlab_token}'}
            )
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_users(self, page: int) -> List[Dict]:
        """Get users list with pagination asynchronously."""
        await self._ensure_session()
        
        params = {
            'page': page,
            'per_page': self.config.page_size,
            'active': 'true'  # Convert boolean to string
        }
        
        url = f"{self.config.gitlab_url}/api/v4/users"
        
        try:
            async with self._session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching users: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching users: {e}")
            return []
    
    async def get_user(self, user_id: int) -> Dict:
        """Get user details by ID asynchronously."""
        await self._ensure_session()
        
        url = f"{self.config.gitlab_url}/api/v4/users/{user_id}"
        
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching user {user_id}: {e}")
            return {}
        
    async def get_all_historical_user_assignments(self, user_id: int, username:str, progress_callback=None) -> List[Dict]:
        """Get all tasks where the user is an assignee or participant."""
        try:
            await self._ensure_session()
            
            if progress_callback:
                await progress_callback("Fetching all tasks...", None)
            
            # Step 1: Get all tasks
            logger.info(f"Fetching all tasks for user {user_id}")
            tasks = await self.get_all_tasks(progress_callback=progress_callback)
            logger.info(f"Fetched {len(tasks)} tasks")

            # Step 2: Filter tasks by user_id in participants
            logger.info(f"Filtering tasks by user {user_id}")
            user_tasks = []
            
            for index, task in enumerate(tasks):
                try:
                    participants = await self.get_task_participants(
                        task.get('project_id'), 
                        task.get('iid')
                    )
                    
                    # Check if user_id is in participants
                    user_is_participant = any(
                        participant.get('id') == user_id 
                        for participant in participants
                    )
                                     
                    if user_is_participant:
                        user_tasks.append(task)
                    
                 
                    if progress_callback and tasks:  # Prevent division by zero
                        progress = min(99, int(((index + 1) / len(tasks)) * 100))
                        await progress_callback(
                            f"🔍Filtering tasks...\n"
                            f"✅{len(user_tasks)} matches\n"
                            f"▶️Progress: {index + 1}/{len(tasks)}",
                            progress  
                        )
                            
                except Exception as e:
                    logger.warning(f"Error processing task {task.get('id')}: {e}")
                    continue
            
            if progress_callback:
                await progress_callback(
                    f"✅ Found {len(user_tasks)} tasks for user {user_id}",
                    100
                )
            
            logger.info(f"Returning {len(user_tasks)} tasks for user {user_id}")
            # Step 3: Filter user tasks to assigned tasks

            logger.info(f"Checking filtered tasks for user {user_id}")
            if progress_callback:
                await progress_callback("Checking filtered tasks...", None)
            assigned_tasks = []

            for index, task in enumerate(user_tasks):  # Use enumerate() to get index
                if task.get('assignee_id') == user_id:
                    assigned_tasks.append(task)
                else:
                    task_assignee = await self.check_task_assignee(username, task.get('project_id'), task.get('iid'))
                    if task_assignee:
                        assigned_tasks.append(task)

                if progress_callback and user_tasks:  # Prevent division by zero
                    progress = min(99, int(((index + 1) / len(user_tasks)) * 100))
                    await progress_callback(
                        f"❓Checking filtered tasks...\n"
                        f"✅{len(assigned_tasks)} matches\n"
                        f"▶️Progress: {index + 1}/{len(user_tasks)}",
                        progress  
                    )

                    
            if progress_callback:
                await progress_callback(
                    f"🎉 Loading completed!\n📊 Total user tasks: {len(assigned_tasks)}", 
                    100
                )


            logger.info(f"Returning {len(assigned_tasks)} assigned tasks for user {user_id}")
            return assigned_tasks

        except Exception as e:
            error_msg = f"❌ Unexpected error in get_all_historical_user_assignments: {e}"
            if progress_callback:
                await progress_callback(error_msg, -1)
            logger.error(error_msg)
            return []

    async def get_all_tasks(self, progress_callback=None) -> List[Dict]:
        """Get all tasks/issues from GitLab with progress updates."""
        await self._ensure_session()
        
        url = f"{self.config.gitlab_url}/api/v4/issues"
        params = {
            'state': 'all',
            'scope': 'all',
            'per_page': 100
        }
        
        all_tasks = []
        page = 1
        
        try:
            if progress_callback:
                await progress_callback("🔄 Starting task loading...", None)
            
            while True:
                params['page'] = page
                
                if progress_callback:
                    await progress_callback(f"📥 Loading page {page}...", None)
                
                async with self._session.get(url, params=params) as response:
                    response.raise_for_status()
                    
                    tasks = await response.json()
                    if not tasks:
                        break
                        
                    all_tasks.extend(tasks)
                    
                    # Try to get total pages from headers
                    if progress_callback:
                        status = f"✅ Loaded {len(all_tasks)} tasks"
                        
                        total_pages = response.headers.get('x-total-pages')
                        total_items = response.headers.get('x-total')
                        
                        if total_pages and total_items:
                            try:
                                total_pages = int(total_pages)
                                total_items = int(total_items)
                                percent = min(95, int((page / total_pages) * 95))
                                await progress_callback(
                                    f"{status}\n📄 Page {page}/{total_pages}",
                                    percent
                                )
                            except (ValueError, ZeroDivisionError):
                                await progress_callback(
                                    f"{status}\n📄 Page {page}",
                                    None
                                )
                        else:
                            await progress_callback(
                                f"{status}\n📄 Page {page}",
                                None
                            )
                    
                    # Check for next page
                    if 'next' not in response.links:
                        break
                        
                    page += 1
            
            if progress_callback:
                await progress_callback(
                    f"🎉 Loading completed!\n📊 Total tasks: {len(all_tasks)}", 
                    100
                )
            
            return all_tasks
            
        except aiohttp.ClientError as e:
            error_msg = f"❌ Network error: {e}"
            if progress_callback:
                await progress_callback(error_msg, -1)
            logger.error(f"Error fetching tasks: {e}")
            return []
        except Exception as e:
            error_msg = f"❌ Unexpected error: {e}"
            if progress_callback:
                await progress_callback(error_msg, -1)
            logger.error(f"Unexpected error fetching tasks: {e}")
            return []
        
    async def get_task_participants(self, project_id: int, task_iid: int) -> list:
        """Get all participants for a specific issue/task from GitLab."""
        await self._ensure_session()
        
        # Note: GitLab API uses project_id (numeric) and issue_iid (internal ID)
        url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{task_iid}/participants"
        
        try:        
            async with self._session.get(url) as response:
                if response.status == 404:
                    # Task might not exist or user doesn't have permission
                    logger.warning(f"Participants not found for project {project_id}, task {task_iid}")
                    return []
                
                response.raise_for_status()
                
                participants = await response.json()
                return participants
                
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching participants for project {project_id}, task {task_iid}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching participants for project {project_id}, task {task_iid}: {e}")
            return []
        
    async def get_task_notes(self, project_id: int, task_iid: int, params: Optional[dict] = None) -> list:
        """Get all notes for a specific issue/task from GitLab."""
        await self._ensure_session()
        
        # Note: GitLab API uses project_id (numeric) and issue_iid (internal ID)
        url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{task_iid}/notes"
        if params is None:
            params = {}
        try:        
            async with self._session.get(url,params=params) as response:
                if response.status == 404:
                    # Task might not exist or user doesn't have permission
                    logger.warning(f"Notes not found for project {project_id}, task {task_iid}")
                    return []
                
                response.raise_for_status()
                
                notes = await response.json()
                return notes
                
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching notes for project {project_id}, task {task_iid}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching notes for project {project_id}, task {task_iid}: {e}")
            return []

    async def check_task_assignee(self,username:str, project_id: int, task_iid: int) -> bool:
        """Check if the current user is the assignee of a task."""
        await self._ensure_session()
        
        notes = await self.get_task_notes(project_id, task_iid, params={'activity_filter': 'only_activity'})
        for note in notes:
            if note.get('system') and note.get('body'):
                body = note['body'].lower()
                
                if any(pattern in body for pattern in [
                    f'assigned to @{username}',
                    f'assigned @{username}',
                    f'назначил @{username}',
                    f'назначил на @{username}',
                    f'reassigned to @{username}'
                ]):
                    return True
                    
                import re
                assign_match = re.search(
                    r'(assigned to|назначил|reassigned to)[\s:]+@?([a-zA-Z0-9_.-]+)',
                    body
                )
                if assign_match and assign_match.group(2) == username:
                    return True
        
        return False