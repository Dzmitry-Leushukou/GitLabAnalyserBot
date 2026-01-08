from services.config import Config
import logging
import aiohttp
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

class GitLabService:
    """
    Service for interacting with GitLab API to retrieve user information, tasks, and metrics.
    
    This service handles communication with GitLab API to fetch user data, tasks, and calculate
    metrics based on label changes and assignments. It implements singleton pattern to ensure
    only one instance exists throughout the application.
    
    Attributes:
        _session (Optional[aiohttp.ClientSession]): HTTP session for API requests
        config (Config): Configuration instance with GitLab URL and token
        
    Example:
        >>> async with GitLabService() as service:
        ...     users = await service.get_users(1)
        ...     print(f"Retrieved {len(users)} users")
    """
    _instance = None
    
    def __new__(cls):
        """
        Create or return the singleton instance of the GitLabService class.
        
        This method ensures that only one instance of the GitLabService class exists
        throughout the application lifecycle.
        
        Returns:
            GitLabService: The single instance of the GitLabService class
            
        Example:
            >>> service1 = GitLabService()
            >>> service2 = GitLabService()
            >>> assert service1 is service2  # Both refer to the same instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the GitLabService instance with configuration and session.
        
        Note:
            This method is part of the singleton pattern implementation and
            should not be called directly. Use the class constructor instead.
        """
        if not self._initialized:
            self.config = Config()
            self._session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
    
    async def __aenter__(self):
        """
        Context manager entry method.
        
        This method allows the GitLabService to be used in an async context manager.
        
        Returns:
            GitLabService: The current instance
            
        Example:
            >>> async with GitLabService() as service:
            ...     users = await service.get_users(1)
        """
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit method that closes the session.
        
        This method ensures proper cleanup when exiting the context manager.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        await self.close()
    
    async def _ensure_session(self) -> None:
        """
        Ensure aiohttp session is initialized and authenticated.
        
        Creates a new session if none exists or if the current session is closed.
        The session includes authorization header with the GitLab token.
        
        Note:
            This is an internal method used to ensure the HTTP session is ready
            for API requests. It should not be called directly.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'Authorization': f'Bearer {self.config.gitlab_token}'}
            )
    
    async def close(self) -> None:
        """
        Close the aiohttp session and clean up resources.
        
        This method ensures proper cleanup of the HTTP session to prevent
        resource leaks. It should be called when the service is no longer needed.
        
        Usage:
            >>> async with GitLabService() as service:
            ...     # Use the service
            ...     pass
            # Session is automatically closed
            
        Or manually:
            >>> service = GitLabService()
            >>> # Use the service
            >>> await service.close()
        """
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_users(self, page: int) -> List[Dict]:
        """
        Get users list with pagination asynchronously.
        
        This method retrieves a paginated list of GitLab users, filtering for active users only.
        
        Args:
            page: The page number to retrieve (starting from 1)
            
        Returns:
            List of user dictionaries, or empty list if an error occurs
            
        Example:
            >>> async with GitLabService() as service:
            ...     users = await service.get_users(1)
            ...     print(f"Found {len(users)} users on page 1")
            
        Note:
            - Each page returns a maximum of `config.page_size` users
            - Only active users are returned (inactive users are filtered out)
            - Returns empty list if no users found or an error occurs
        """
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
        """
        Get user details by ID asynchronously.
        
        This method retrieves detailed information about a specific GitLab user.
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            Dictionary containing user details, or empty dict if an error occurs
            
        Example:
            >>> async with GitLabService() as service:
            ...     user = await service.get_user(123)
            ...     print(f"User name: {user.get('name')}")
            
        Note:
            - Returns empty dictionary if user not found or an error occurs
            - Includes user metadata like name, username, email, avatar URL, etc.
        """
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
        """
        Get all tasks where the user is an assignee or participant.
        
        This method retrieves all tasks associated with a user, either as assignee
        or as a participant who has been involved in the task.
        
        Args:
            user_id: The unique identifier of the user
            username: The username of the user
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of task dictionaries where the user is involved
            
        Example:
            >>> async with GitLabService() as service:
            ...     tasks = await service.get_all_historical_user_assignments(123, "john_doe")
            ...     print(f"Found {len(tasks)} tasks for user")
            
        Note:
            - This is a computationally intensive operation for large projects
            - Progress is reported through the callback function if provided
            - Filters tasks where the user is either an assignee or participant
        """
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
                    # Check if required fields exist before accessing them
                    project_id = task.get('project_id')
                    task_iid = task.get('iid')
                    
                    if project_id is None or task_iid is None:
                        logger.warning(f"Missing project_id or iid for task {task.get('id', 'unknown')}")
                        continue
                        
                    participants = await self.get_task_participants(
                        project_id,
                        task_iid
                    )
                    
                    # Check if user_id is in participants
                    user_is_participant = any(
                        participant.get('id') == user_id
                        for participant in participants
                    )
                                    
                    if user_is_participant:
                        user_tasks.append(task)
                    
                  
                    if progress_callback and tasks and index%self.config.progress_step==0:  # Prevent division by zero
                        progress = min(99, int(((index + 1) / len(tasks)) * 100))
                        await progress_callback(
                            f"🔍Filtering tasks...\n"
                            f"✅{len(user_tasks)} matches\n"
                            f"▶️Progress: {index + 1}/{len(tasks)}",
                            progress
                        )
                            
                except Exception as e:
                    task_id = task.get('id', 'unknown')
                    logger.warning(f"Error processing task {task_id}: {e}")
                    continue
            
            if progress_callback:
                await progress_callback(
                    f"✅ Found {len(user_tasks)} tasks for user {user_id}",
                    100
                )
            
            logger.info(f"Returning {len(user_tasks)} tasks for user {user_id}")
            # Step 3: Filter user tasks to assigned tasks

            logger.info(f"Checking filtered tasks for user {user_id}")
            assigned_tasks = []

            for index, task in enumerate(user_tasks):  # Use enumerate() to get index
                if task.get('assignee_id') == user_id:
                    assigned_tasks.append(task)
                else:
                    project_id = task.get('project_id')
                    task_iid = task.get('iid')
                    
                    if project_id is None or task_iid is None:
                        logger.warning(f"Missing project_id or iid for task {task.get('id', 'unknown')}")
                        continue
                        
                    task_assignee = await self.check_task_assignee(username, project_id, task_iid)
                    if task_assignee:
                        assigned_tasks.append(task)

                if progress_callback and user_tasks and index%self.config.progress_step==0:  # Prevent division by zero
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
        """
        Get all tasks/issues from GitLab with progress updates.
        
        This method retrieves all issues from GitLab with pagination, providing
        progress updates through the callback function if provided.
        
        Args:
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of all task dictionaries from GitLab
            
        Example:
            >>> async with GitLabService() as service:
            ...     tasks = await service.get_all_tasks()
            ...     print(f"Retrieved {len(tasks)} tasks from GitLab")
            
        Note:
            - This is a potentially time-consuming operation for large projects
            - Pagination is handled automatically
            - Progress is reported through the callback function if provided
            - Retrieves all states (open, closed, etc.) of issues
        """
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
                                percent = page/total_pages * 100
                                await progress_callback(
                                    f"{status}\n📄 Page {page}/{total_pages}",
                                    percent
                                )
                            except (ValueError, ZeroDivisionError):
                                await progress_callback(
                                    f"{status}\n📄 Page {page}",None
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
        """
        Get ALL participants for a specific issue/task from GitLab with pagination.
        
        This method retrieves all participants who have been involved in a specific
        issue or task, using pagination to ensure all participants are retrieved.
        
        Args:
            project_id: The ID of the GitLab project
            task_iid: The internal ID of the task within the project
            
        Returns:
            List of participant dictionaries
            
        Example:
            >>> async with GitLabService() as service:
            ...     participants = await service.get_task_participants(123, 456)
            ...     print(f"Task has {len(participants)} participants")
        """
        await self._ensure_session()
        all_participants = []
        page = 1
        per_page = 100

        while True:
            url = (
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/"
                f"issues/{task_iid}/participants"
                f"?page={page}&per_page={per_page}"
            )
            
            try:
                async with self._session.get(url) as response:
                    if response.status == 404:
                        logger.warning(f"Task or participants not found for project {project_id}, task {task_iid}")
                        break
                    
                    response.raise_for_status()
                    
                    participants = await response.json()
                    if not participants:
                        break
                        
                    all_participants.extend(participants)
                    page += 1
                    
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching participants page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error on page {page}: {e}")
                break
        
        logger.info(f"Retrieved {len(all_participants)} participants for task {task_iid}")
        return all_participants
        
    async def get_task_notes(self, project_id: int, task_iid: int, params: Optional[dict] = None) -> list:
        """
        Get ALL notes for a specific issue/task from GitLab.
        
        This method retrieves all notes (comments, system messages, etc.) for a specific
        issue or task, using pagination to ensure all notes are retrieved.
        
        Args:
            project_id: The ID of the GitLab project
            task_iid: The internal ID of the task within the project
            params: Optional parameters to filter the notes
            
        Returns:
            List of note dictionaries
            
        Example:
            >>> async with GitLabService() as service:
            ...     notes = await service.get_task_notes(123, 456)
            ...     print(f"Retrieved {len(notes)} notes for task")
        """
        await self._ensure_session()
        
        all_notes = []
        page = 1
        
        request_params = params.copy() if params else {}
        
        while True:
            request_params.update({"page": page, "per_page": 100})
            
            url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{task_iid}/notes"
            
            try:
                async with self._session.get(url, params=request_params) as response:
                    if response.status == 404:
                        logger.warning(f"Notes not found for project {project_id}, task {task_iid}")
                        break
                    
                    response.raise_for_status()
                    
                    notes = await response.json()
                    if not notes:
                        break
                    
                    all_notes.extend(notes)
                    
                    if len(notes) < 100:
                        break
                        
                    page += 1
                    
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching notes for project {project_id}, task {task_iid}, page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching notes for project {project_id}, task {task_iid}, page {page}: {e}")
                break
        
        logger.info(f"Retrieved {len(all_notes)} notes for project {project_id}, task {task_iid}")
        return all_notes

    async def check_task_assignee(self,username:str, project_id: int, task_iid: int) -> bool:
        """
        Check if the current user is the assignee of a task.
        
        This method examines the task notes to determine if the specified user
        has been assigned to the task through system messages or assignment changes.
        
        Args:
            username: The username to check
            project_id: The ID of the GitLab project
            task_iid: The internal ID of the task within the project
            
        Returns:
            Boolean indicating if the user is assigned to the task
            
        Example:
            >>> is_assignee = await check_task_assignee("john_doe", 123, 456)
            >>> if is_assignee:
            ...     print("User is assigned to this task")
        """
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
    
    async def get_user_metrics(self, user_id: int, username:str, progress_callback=None) -> List[Dict]:
        """
        Get metrics for all tasks assigned to a user.
        
        This method retrieves all tasks assigned to a user and calculates metrics
        for each task, including time spent in different stages.
        
        Args:
            user_id: The unique identifier of the user
            username: The username of the user
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of task dictionaries with calculated metrics
            
        Example:
            >>> async with GitLabService() as service:
            ...     metrics = await service.get_user_metrics(123, "john_doe")
            ...     print(f"Calculated metrics for {len(metrics)} tasks")
        """
        tasks = await self.get_all_historical_user_assignments(user_id, username, progress_callback)
        tasks_with_metrics = []

        for index,task in enumerate(tasks):
            task_metrics = await self.get_task_metrics(task,username)
            tasks_with_metrics.append(task_metrics)
            if progress_callback and index % self.config.progress_step == 0:
               await progress_callback("Fetching tasks metrics...",((index+1)/(len(tasks)))*100)

        if progress_callback:
            await progress_callback("Fetching tasks metrics...",100)
        return tasks_with_metrics
    
    async def get_resource_label_events(self, project_id: int, task_iid: int, params: Optional[dict] = None) -> list:
        """
        Get ALL resource label events for a specific issue/task from GitLab.
        
        This method retrieves all label change events (additions/removals) for a specific
        issue or task, using pagination to ensure all events are retrieved.
        
        Args:
            project_id: The ID of the GitLab project
            task_iid: The internal ID of the task within the project
            params: Optional parameters to filter the events
            
        Returns:
            List of label event dictionaries
            
        Example:
            >>> async with GitLabService() as service:
            ...     events = await service.get_resource_label_events(123, 456)
            ...     print(f"Found {len(events)} label events for task")
        """
        await self._ensure_session()
        
        all_events = []
        page = 1
        
        request_params = params.copy() if params else {}
        
        while True:
            request_params.update({"page": page, "per_page": 100})
            
            url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{task_iid}/resource_label_events"
            
            try:
                async with self._session.get(url, params=request_params) as response:
                    if response.status == 404:
                        logger.warning(f"Resource label events not found for project {project_id}, task {task_iid}")
                        break
                    
                    response.raise_for_status()
                    
                    events = await response.json()
                    if not events:
                        break
                    
                    all_events.extend(events)
                    
                    if len(events) < 100:
                        break
                        
                    page += 1
                    
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching resource label events for project {project_id}, task {task_iid}, page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching resource label events for project {project_id}, task {task_iid}, page {page}: {e}")
                break
        
        logger.info(f"Retrieved {len(all_events)} resource label events for project {project_id}, task {task_iid}")
        return all_events
    
    async def get_task_metrics(self, task: Dict,username:str) -> Dict:
        """
        Get metrics for a specific task by collecting relevant history and calculating metrics.
        
        This method retrieves the history and label events for a task and calculates
        metrics for the specified user.
        
        Args:
            task: The task dictionary containing task details
            username: The username for which to calculate metrics
            
        Returns:
            Dict: A dictionary containing the task metrics
            
        Example:
            >>> task = {"project_id": 123, "iid": 456, "title": "Sample task"}
            >>> metrics = await get_task_metrics(task, "john")
        """
        task_metrics = {}
        task_metrics['task_id'] = task.get('id')
        task_metrics['task_iid'] = task.get('iid')
        task_metrics['project_id'] = task.get('project_id')
        task_metrics['title'] = task.get('title')
        task_metrics['description'] = task.get('description')
        task_metrics['created_at'] = task.get('created_at')
        task_metrics['updated_at'] = task.get('updated_at')
        task_metrics['closed_at'] = task.get('closed_at') or ""

        history=await self.get_task_notes(task.get('project_id'), task.get('iid'),params={'activity_filter': 'only_activity'})
        labels_history=await self.get_resource_label_events(task.get('project_id'), task.get('iid'))

        #task_metrics['history']=history
        #task_metrics['labels_history']=labels_history
        task_metrics=await self.calculate_metrics(history,labels_history,username,task_metrics)
        return task_metrics
    
    async def calculate_metrics(self, history: List[Dict], labels_history: List[Dict], username: str, task_metrics: Dict) -> Dict:
        """
        Calculate task metrics for a specific user based on activity history and label changes.
        
        This method analyzes the history of a task to calculate time spent in different
        development stages (work, review, QA) for a specific user, considering task state.
        
        Args:
            history: List of system events (comments, assignments, etc.)
            labels_history: List of label change events
            username: Target username for metric calculation
            task_metrics: Dictionary to store calculated metrics
        
        Returns:
            Updated task_metrics dictionary with calculated metrics
        """
        # Merge and sort both event lists by creation time
        sorted_history = sorted(history, key=lambda x: x['created_at'])
        sorted_labels_history = sorted(labels_history, key=lambda x: x['created_at'])
        
        sh_index = 0
        lh_index = 0
        merged_history = []
        
        # Merge sorted lists while preserving chronological order
        while sh_index < len(sorted_history) and lh_index < len(sorted_labels_history):
            if sorted_history[sh_index]['created_at'] < sorted_labels_history[lh_index]['created_at']:
                merged_history.append(sorted_history[sh_index])
                sh_index += 1
            else:
                merged_history.append(sorted_labels_history[lh_index])
                lh_index += 1
        
        # Add remaining events from either list
        while sh_index < len(sorted_history):
            merged_history.append(sorted_history[sh_index])
            sh_index += 1
        
        while lh_index < len(sorted_labels_history):
            merged_history.append(sorted_labels_history[lh_index])
            lh_index += 1
        
        task_metrics['merged_history'] = merged_history
        
        # Get task state information
        task_created_at = datetime.fromisoformat(task_metrics['created_at'].replace('Z', '+00:00'))
        task_closed_at = None
        if task_metrics.get('closed_at'):
            task_closed_at = datetime.fromisoformat(task_metrics['closed_at'].replace('Z', '+00:00'))
        
        # Initialize tracking variables
        cur_assignee = None
        cur_label = None
        label_start_time = None
        current_time = datetime.now(timezone.utc)
        
        # Track state changes from history
        state_changes = []
        
        # Find state changes in history (close/reopen events)
        for event in merged_history:
            if event.get('system') and event.get('body'):
                body = event['body'].lower()
                event_time = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                
                # Check for close events
                if 'closed' in body or 'закрыт' in body or 'closed issue' in body:
                    # Make sure it's not about merging or other actions
                    if not any(word in body for word in ['merged', 'мердж', 'accept', 'принят']):
                        state_changes.append(('closed', event_time))
                
                # Check for reopen events
                elif 'reopened' in body or 'повторно открыт' in body or 'reopened issue' in body:
                    state_changes.append(('opened', event_time))
        
        # Sort state changes chronologically
        state_changes.sort(key=lambda x: x[1])
        
        # Create list of open/closed periods
        state_periods = []
        current_state = 'opened'
        last_state_change = task_created_at
        
        for state, change_time in state_changes:
            state_periods.append((current_state, last_state_change, change_time))
            current_state = state
            last_state_change = change_time
        
        # Add final period
        end_time = task_closed_at if task_closed_at else current_time
        state_periods.append((current_state, last_state_change, end_time))
        
        # Create a list of assignment periods for the target user
        assignment_periods = []
        assignment_start = None
        
        # Extract all assignment periods for the target user
        for event in merged_history:
            event_time = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
            
            # Check for assignment events
            if event.get('system') and event.get('body'):
                body = event['body'].lower()
                
                # Check if this event assigns the target user
                assign_patterns = [
                    f'assigned to @{username}',
                    f'assigned @{username}',
                    f'назначил @{username}',
                    f'назначил на @{username}',
                    f'reassigned to @{username}'
                ]
                
                is_assigned = False
                is_unassigned = False
                
                # Check assignment patterns
                for pattern in assign_patterns:
                    if pattern in body:
                        is_assigned = True
                        break
                
                # Check unassignment
                if f'unassigned @{username}' in body:
                    is_unassigned = True
                
                # Use regex for more robust pattern matching
                if not is_assigned and not is_unassigned:
                    assign_match = re.search(
                        r'(assigned to|назначил|reassigned to)[\s:]+@?([a-zA-Z0-9_.-]+)',
                        body
                    )
                    if assign_match and assign_match.group(2) == username:
                        is_assigned = True
                
                # Handle assignment start
                if is_assigned and assignment_start is None:
                    assignment_start = event_time
                
                # Handle assignment end
                elif is_unassigned and assignment_start is not None:
                    assignment_periods.append((assignment_start, event_time))
                    assignment_start = None
        
        # If assignment is still active at the end
        if assignment_start is not None:
            assignment_periods.append((assignment_start, end_time))
        
        # Helper function to check if a time point is within an open period
        def get_active_state_period(check_time):
            """Return the state period that contains the check_time."""
            for state, period_start, period_end in state_periods:
                if period_start <= check_time <= period_end:
                    return (state, period_start, period_end)
            return None
        
        # Helper function to get the next state change after a given time
        def get_next_state_change(check_time):
            """Return the next state change time after check_time."""
            for _, period_start, period_end in state_periods:
                if period_start > check_time:
                    return period_start
            return end_time
        
        # Helper function to check if time is in any assignment period
        def is_in_assignment_period(check_time):
            """Check if time is within any assignment period."""
            for period_start, period_end in assignment_periods:
                if period_start <= check_time <= period_end:
                    return True
            return False
        
        # Helper function to get current assignment period end
        def get_assignment_period_end(check_time):
            """Get the end of assignment period containing check_time."""
            for period_start, period_end in assignment_periods:
                if period_start <= check_time <= period_end:
                    return period_end
            return None
        
        # Now calculate time for each label only during assignment AND open periods
        cicle_time = 0
        cicle_history = []
        review_time = 0
        review_history = []
        qa_time = 0
        qa_history = []
        
        for event in merged_history:
            event_time = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
            
            # Check if this event happens during any assignment period
            in_assignment_period = is_in_assignment_period(event_time)
            
            # Get current state period
            state_period = get_active_state_period(event_time)
            if not state_period:
                continue
                
            current_state, state_start, state_end = state_period
            
            # Only process if in assignment period AND task is open
            if not in_assignment_period or current_state != 'opened':
                # If we were tracking a label, but now we're not in assignment or task is closed,
                # we need to close the current label period
                if cur_label and label_start_time:
                    # Find the earliest end: assignment end, state change to closed, or current time
                    possible_ends = []
                    
                    # Check assignment end
                    assignment_end = get_assignment_period_end(label_start_time)
                    if assignment_end:
                        possible_ends.append(assignment_end)
                    
                    # Check state change to closed
                    if current_state == 'closed':
                        possible_ends.append(state_start)  # When it changed to closed
                    
                    # Add event time as potential end
                    possible_ends.append(event_time)
                    
                    # Use the earliest end
                    if possible_ends:
                        end_time_for_label = min(possible_ends)
                        
                        if end_time_for_label > label_start_time:
                            duration = (end_time_for_label - label_start_time).total_seconds()
                            
                            # Add to appropriate history and time accumulator
                            if cur_label == 'doing':
                                cicle_time += duration
                                cicle_history.append({
                                    'start': label_start_time.isoformat(),
                                    'end': end_time_for_label.isoformat(),
                                    'duration': duration,
                                    'event': {'type': 'interrupted', 'reason': 'not_assigned_or_closed'}
                                })
                            elif cur_label == 'review':
                                review_time += duration
                                review_history.append({
                                    'start': label_start_time.isoformat(),
                                    'end': end_time_for_label.isoformat(),
                                    'duration': duration,
                                    'event': {'type': 'interrupted', 'reason': 'not_assigned_or_closed'}
                                })
                            elif cur_label == 'qa':
                                qa_time += duration
                                qa_history.append({
                                    'start': label_start_time.isoformat(),
                                    'end': end_time_for_label.isoformat(),
                                    'duration': duration,
                                    'event': {'type': 'interrupted', 'reason': 'not_assigned_or_closed'}
                                })
                    
                    cur_label = None
                    label_start_time = None
                
                continue
            
            # Track label changes
            if 'action' in event and 'label' in event:
                label_name = event['label']['name']
                action = event['action']
                
                # Only track specific labels
                if label_name not in ['doing', 'review', 'qa']:
                    continue
                
                # Handle label removal or change
                if cur_label and label_start_time:
                    # Calculate duration for the previous label
                    # Ensure we don't count time when task was closed
                    actual_end_time = event_time
                    
                    # Check if task was closed during this label period
                    state_period_at_start = get_active_state_period(label_start_time)
                    if state_period_at_start and state_period_at_start[0] == 'opened':
                        # Task was open when label started, check if it closed before event_time
                        closed_periods = [(s, start, end) for s, start, end in state_periods 
                                        if s == 'closed' and start > label_start_time and start < event_time]
                        
                        if closed_periods:
                            # Task was closed during this period, only count time until closure
                            first_closed_time = min([start for _, start, _ in closed_periods])
                            actual_end_time = min(actual_end_time, first_closed_time)
                    
                    if actual_end_time > label_start_time:
                        duration = (actual_end_time - label_start_time).total_seconds()
                        
                        # Add to appropriate history and time accumulator
                        if cur_label == 'doing':
                            cicle_time += duration
                            cicle_history.append({
                                'start': label_start_time.isoformat(),
                                'end': actual_end_time.isoformat(),
                                'duration': duration,
                                'event': event
                            })
                        elif cur_label == 'review':
                            review_time += duration
                            review_history.append({
                                'start': label_start_time.isoformat(),
                                'end': actual_end_time.isoformat(),
                                'duration': duration,
                                'event': event
                            })
                        elif cur_label == 'qa':
                            qa_time += duration
                            qa_history.append({
                                'start': label_start_time.isoformat(),
                                'end': actual_end_time.isoformat(),
                                'duration': duration,
                                'event': event
                            })
                
                # Update current label based on action
                if action == 'add' and current_state == 'opened':
                    cur_label = label_name
                    label_start_time = event_time
                elif action == 'remove' and label_name == cur_label:
                    cur_label = None
                    label_start_time = None
        
        # Handle case where label is still active at the end
        if cur_label and label_start_time:
            # Determine the actual end time considering task state and assignment
            possible_ends = []
            
            # Check assignment end
            assignment_end = get_assignment_period_end(label_start_time)
            if assignment_end:
                possible_ends.append(assignment_end)
            
            # Check if/when task becomes closed after label start
            for state, period_start, period_end in state_periods:
                if period_start > label_start_time and state == 'closed':
                    possible_ends.append(period_start)
                    break
            
            # Add the final end time (task closed time or current time)
            possible_ends.append(end_time)
            
            # Use the earliest end
            actual_end_time = min(possible_ends) if possible_ends else end_time
            
            # Ensure we only count time when task was open
            if actual_end_time > label_start_time:
                # Check for closed periods within this label period
                closed_periods = [(s, start, end) for s, start, end in state_periods 
                                if s == 'closed' and start > label_start_time and start < actual_end_time]
                
                if closed_periods:
                    # Only count time until first closure
                    first_closed_time = min([start for _, start, _ in closed_periods])
                    actual_end_time = min(actual_end_time, first_closed_time)
                
                if actual_end_time > label_start_time:
                    duration = (actual_end_time - label_start_time).total_seconds()
                    
                    if cur_label == 'doing':
                        cicle_time += duration
                        cicle_history.append({
                            'start': label_start_time.isoformat(),
                            'end': actual_end_time.isoformat(),
                            'duration': duration,
                            'event': {'type': 'ended', 'label': cur_label}
                        })
                    elif cur_label == 'review':
                        review_time += duration
                        review_history.append({
                            'start': label_start_time.isoformat(),
                            'end': actual_end_time.isoformat(),
                            'duration': duration,
                            'event': {'type': 'ended', 'label': cur_label}
                        })
                    elif cur_label == 'qa':
                        qa_time += duration
                        qa_history.append({
                            'start': label_start_time.isoformat(),
                            'end': actual_end_time.isoformat(),
                            'duration': duration,
                            'event': {'type': 'ended', 'label': cur_label}
                        })
        
        # Update task metrics with calculated values
        task_metrics['cicle_time'] = cicle_time
        task_metrics['cicle_history'] = cicle_history
        task_metrics['review_time'] = review_time
        task_metrics['review_history'] = review_history
        task_metrics['qa_time'] = qa_time
        task_metrics['qa_history'] = qa_history
        
        # Add debug information
        task_metrics['state_periods'] = [
            (state, start.isoformat(), end.isoformat()) 
            for state, start, end in state_periods
        ]
        
        task_metrics['assignment_periods'] = [
            (start.isoformat(), end.isoformat()) 
            for start, end in assignment_periods
        ]
        
        # Calculate total open time during assignments
        total_open_assignment_time = 0
        for assign_start, assign_end in assignment_periods:
            for state, state_start, state_end in state_periods:
                if state == 'opened':
                    # Calculate overlap
                    overlap_start = max(assign_start, state_start)
                    overlap_end = min(assign_end, state_end)
                    if overlap_start < overlap_end:
                        total_open_assignment_time += (overlap_end - overlap_start).total_seconds()
        
        task_metrics['total_open_assignment_time'] = total_open_assignment_time
        
        return task_metrics
    async def get_all_users(self)-> List[Dict]:
        """
        Get all users from GitLab by iterating through all pages.
        
        This method retrieves all users by paginating through all available pages
        until no more users are returned.
        
        Returns:
            List of all user dictionaries from GitLab
            
        Example:
            >>> async with GitLabService() as service:
            ...     all_users = await service.get_all_users()
            ...     print(f"Retrieved {len(all_users)} users from GitLab")
        """
        try:
            users = []
            page=0
            while True:
                response = await self.get_users(page)
                if response != []:
                    users.extend(response)
                    page += 1
                else:
                    break

            return users
        except Exception as e:
            raise e
        
    async def create_new_task(self, project_id: int, task_name: str, task_description: str, assignee_id: int, labels: List[str]) -> Dict:
        """
        Create a new task (issue) in GitLab project asynchronously.
        
        This method creates a new issue in the specified GitLab project with the provided details.
        
        Args:
            project_id: The ID of the GitLab project where the task will be created
            task_name: The title of the task
            task_description: The description of the task
            assignee_id: The ID of the user to assign the task to (can be None)
            labels: A list of label names to apply to the task
            
        Returns:
            A dictionary containing the created task details
            
        Example:
            >>> async with GitLabService() as service:
            ...     task = await service.create_new_task(
            ...         project_id=123,
            ...         task_name="New feature",
            ...         task_description="Implement new feature",
            ...         assignee_id=456,
            ...         labels=["feature", "high-priority"]
            ...     )
            ...     print(f"Created task: {task['web_url']}")
        """
        await self._ensure_session()
        
        url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues"
        


        payload = {
            'title': task_name,
            'description': task_description,
        }


        # Only add optional fields if they're provided
        if assignee_id is not None:
            payload['assignee_id'] = assignee_id
        
        if labels:
            payload['labels'] = ','.join(labels)
    
        
        try:
            async with self._session.post(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error creating task: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error creating task: {e}")
            raise e
        
    async def get_user_id_by_name(self, user_name: str) -> Optional[int]:
        """
        Find GitLab user ID by name.
        
        This method searches for a GitLab user by their full name and returns their ID.
        
        Args:
            user_name: The full name of the user to search for
            
        Returns:
            The user ID if found, None otherwise
            
        Example:
            >>> async with GitLabService() as service:
            ...     user_id = await service.get_user_id_by_name("John Doe")
            ...     if user_id:
            ...         print(f"Found user with ID: {user_id}")
        """
        await self._ensure_session()
        
        # URL for user search
        url = f"{self.config.gitlab_url}/api/v4/users"
        
        # Encode name for search
        search_query = user_name.replace(" ", "+")
        url = f"{url}?search={search_query}"
        
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                users = await response.json()
                
                # Look for user by full name
                for user in users:
                    if user.get('name') == user_name:
                        return user['id']
                
                # If not found, return None
                return None
                
        except Exception as e:
            logger.error(f"Error searching for user {user_name}: {e}")
            return None
        
    async def get_labels_from_project_id(self, project_id: int) -> List[Dict]:
        """
        Get all labels from issue boards in a GitLab project with pagination support.
        
        This function retrieves all labels that are available across all issue boards
        in a specified GitLab project. Since labels in GitLab are project-level resources,
        they can be used on any issue board within the project.
        
        Args:
            project_id (int): The ID of the GitLab project
            
        Returns:
            List[Dict]: A list of label dictionaries containing label information.
                        Returns empty list if no labels are found or if an error occurs.
                        
        Notes:
            - Handles GitLab API pagination (returns all pages)
            - Labels are returned in order from GitLab API (typically alphabetical)
            
        Example:
            >>> async with GitLabService() as service:
            ...     labels = await service.get_labels_from_project_id(123)
            ...     print(f"Found {len(labels)} labels in project")
        """
        await self._ensure_session()
        
        # GitLab API endpoint for project labels
        url = f"{self.config.gitlab_url}/api/v4/projects/{project_id}/labels"
        
        all_labels = []
        page = 1
        per_page = 100  # GitLab maximum per page
        
        try:
            while True:
                # Add pagination parameters
                paginated_url = f"{url}?page={page}&per_page={per_page}"
                
                async with self._session.get(paginated_url) as response:
                    response.raise_for_status()
                    
                    # Get current page labels
                    labels = await response.json()
                    
                    if not labels:  # No more labels
                        break
                        
                    all_labels.extend(labels)
                    
                    # Check if there are more pages
                    # GitLab includes pagination headers
                    if 'X-Next-Page' in response.headers:
                        next_page = response.headers.get('X-Next-Page')
                        if next_page and next_page != '':
                            page = int(next_page)
                        else:
                            break
                    else:
                        # Fallback: if we got less than per_page items, likely last page
                        if len(labels) < per_page:
                            break
                        page += 1
                    
            logger.debug(f"Retrieved {len(all_labels)} labels from project {project_id}")
            return all_labels
            
        except aiohttp.ClientResponseError as e:
            logger.error(f"GitLab API error fetching labels for project {project_id}: {e}")
            if e.status == 404:
                logger.warning(f"Project {project_id} not found or access denied")
            elif e.status == 403:
                logger.warning(f"Insufficient permissions to access labels in project {project_id}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching labels for project {project_id}: {e}")
            return []
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching labels for project {project_id}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching labels for project {project_id}: {e}")
            return []