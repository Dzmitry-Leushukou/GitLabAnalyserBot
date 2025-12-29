from services.config import Config
import logging
import requests
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
            self._initialized = True
    
    def get_users(self, page: int) -> List[Dict]:
        """Get users list with pagination."""
        params = {
            'page': page,
            'per_page': self.config.page_size,
            'active': True
        }
        response = requests.get(
            self.config.gitlab_url + '/api/v4/users',
            params=params,
            headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
        )
        return response.json()

    def get_user(self, user_id: int) -> Dict:
        """Get user details by ID."""
        response = requests.get(
            self.config.gitlab_url + '/api/v4/users/' + str(user_id),
            headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
        )
        return response.json()

    def get_user_tasks(self, user_id: int) -> List[Dict]:
        """
        Gets all tasks where the user was an assignee at any time.
        Uses optimized search in recent projects.
        """
        # Get user info first
        user_info = self.get_user(user_id)
        if not user_info:
            logger.error(f"User {user_id} not found")
            return []
        
        username = user_info.get('username')
        logger.info(f"Searching for tasks where user {username} was assignee...")
        
        # Get current tasks where user is assignee
        current_tasks = self._get_current_assignee_tasks(user_id)
        logger.info(f"Found {len(current_tasks)} current tasks")
        
        # Get user's recent projects
        recent_projects = self._get_user_recent_projects(user_id, limit=30)
        logger.info(f"Will search in {len(recent_projects)} recent projects")
        
        # Search for historical assignments in recent projects
        historical_tasks = []
        processed_projects = 0
        
        for project_id in recent_projects:
            try:
                project_tasks = self._search_assignee_in_project(project_id, user_id, username)
                if project_tasks:
                    historical_tasks.extend(project_tasks)
                    logger.info(f"Project {project_id}: found {len(project_tasks)} historical tasks")
                    
            except Exception as e:
                logger.error(f"Error searching project {project_id}: {e}")
                continue
            
            processed_projects += 1
            
            # Progress update
            if processed_projects % 5 == 0:
                logger.info(f"Processed {processed_projects}/{len(recent_projects)} projects")
        
        # Combine and deduplicate
        all_tasks = current_tasks + historical_tasks
        unique_tasks = self._deduplicate_tasks(all_tasks)
        
        logger.info(f"Total unique tasks found: {len(unique_tasks)}")
        return unique_tasks
    
    def _get_current_assignee_tasks(self, user_id: int) -> List[Dict]:
        """Get tasks where user is currently assignee."""
        tasks = []
        page = 1
        
        while True:
            try:
                response = requests.get(
                    f"{self.config.gitlab_url}/api/v4/issues",
                    params={
                        'assignee_id': user_id,
                        'state': 'all',
                        'page': page,
                        'per_page': 100,
                        'scope': 'all'
                    },
                    headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
                )
                response.raise_for_status()
                
                page_tasks = response.json()
                if not page_tasks:
                    break
                
                tasks.extend(page_tasks)
                page += 1
                
                # Safety limit
                if page > 10:
                    break
                    
            except Exception as e:
                logger.error(f"Error getting current tasks page {page}: {e}")
                break
        
        return tasks
    
    def _get_user_recent_projects(self, user_id: int, limit: int = 30) -> List[int]:
        """Get projects where user recently participated."""
        try:
            # Try to get user events first
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/users/{user_id}/events",
                params={'per_page': 50, 'page': 1},
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            
            if response.status_code == 200:
                events = response.json()
                project_ids = set()
                
                for event in events:
                    project_id = event.get('project_id')
                    if project_id:
                        project_ids.add(project_id)
                    
                    if len(project_ids) >= limit:
                        break
                
                if project_ids:
                    return list(project_ids)
                    
        except Exception as e:
            logger.warning(f"Could not get user events: {e}")
        
        # Fallback: get some accessible projects
        all_projects = self.get_all_repos()
        return all_projects[:limit]
    
    def _search_assignee_in_project(self, project_id: int, user_id: int, username: str) -> List[Dict]:
        """Search for tasks in a project where user was assignee."""
        try:
            # Get project tasks
            page = 1
            found_tasks = []
            
            while True:
                response = requests.get(
                    f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues",
                    params={
                        'page': page,
                        'per_page': 50,
                        'state': 'all',
                        'scope': 'all'
                    },
                    headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
                )
                
                if response.status_code != 200:
                    break
                
                tasks = response.json()
                if not tasks:
                    break
                
                # Check each task for assignee history
                for task in tasks:
                    # Check current assignee
                    assignee = task.get('assignee')
                    if assignee and assignee.get('id') == user_id:
                        found_tasks.append(task)
                        continue
                    
                    # Check if user mentioned in description
                    description = task.get('description', '').lower()
                    if f'@{username}'.lower() in description:
                        found_tasks.append(task)
                        continue
                    
                    # Check system notes for assignee history
                    task_iid = task.get('iid')
                    if self._check_assignee_in_notes(project_id, task_iid, username):
                        found_tasks.append(task)
                
                page += 1
                if page > 3:  # Limit search depth
                    break
                    
        except Exception as e:
            logger.error(f"Error searching project {project_id}: {e}")
        
        return found_tasks
    
    def _check_assignee_in_notes(self, project_id: int, issue_iid: int, username: str) -> bool:
        """Check if user was mentioned as assignee in system notes."""
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
                params={'per_page': 20, 'page': 1},
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            
            if response.status_code != 200:
                return False
            
            notes = response.json()
            for note in notes:
                if note.get('system'):
                    body = note.get('body', '').lower()
                    # Check for assignee patterns
                    patterns = [
                        f'assigned to @{username}',
                        f'reassigned to @{username}',
                        f'unassigned @{username}',
                        f'assigned to {username}',
                    ]
                    
                    for pattern in patterns:
                        if pattern.lower() in body:
                            return True
                            
        except Exception:
            pass
        
        return False
    
    def _deduplicate_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Remove duplicate tasks."""
        seen = set()
        unique_tasks = []
        
        for task in tasks:
            key = (task.get('project_id'), task.get('iid'))
            if key not in seen:
                seen.add(key)
                unique_tasks.append(task)
        
        return unique_tasks
    
    def get_label_history(self, project_id: int, issue_iid: int) -> List[Dict]:
        """
        Gets the label change history for a specific task.
        Returns list of events sorted by timestamp.
        """
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/resource_label_events",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            label_events = response.json()
            
            events = []
            for event in label_events:
                action = event.get('action')
                if action == "add":
                    action_text = "added"
                elif action == "remove":
                    action_text = "removed"
                else:
                    action_text = action
                
                user_name = "Unknown user"
                if event.get('user'):
                    user_name = event['user'].get('name', 'Unknown user')
                
                event_info = {
                    'timestamp': event.get('created_at'),
                    'label': event.get('label', {}).get('name', 'Unknown label'),
                    'action': action_text,
                    'user': user_name,
                    'raw_action': action,
                    'type': 'label'
                }
                events.append(event_info)
            
            return events
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting label history: {e}")
            return []
    
    def get_assignee_history(self, project_id: int, issue_iid: int) -> List[Dict]:
        """
        Gets the assignee change history from system notes.
        Returns list of assignee events sorted by timestamp.
        """
        try:
            # Get all notes for the issue
            page = 1
            all_notes = []
            
            while True:
                response = requests.get(
                    f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
                    params={'page': page, 'per_page': 100},
                    headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
                )
                response.raise_for_status()
                
                notes = response.json()
                if not notes:
                    break
                    
                all_notes.extend(notes)
                page += 1
            
            # Filter and process system notes about assignee changes
            assignee_events = []
            
            for note in all_notes:
                if note.get('system') and self._is_assignee_note(note.get('body', '')):
                    body = note.get('body', '')
                    created_at = note.get('created_at')
                    
                    event_type, assignee_info = self._parse_assignee_note(body)
                    
                    assignee_events.append({
                        'timestamp': created_at,
                        'type': 'assignee',
                        'action': event_type,
                        'info': body,
                        'assignee': assignee_info,
                        'author': note.get('author', {}).get('name', 'Unknown user')
                    })
            
            return assignee_events
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting assignee history: {e}")
            return []
    
    def _is_assignee_note(self, note_body: str) -> bool:
        """Check if a system note is about assignee changes."""
        note_lower = note_body.lower()
        assignee_keywords = ['assigned', 'unassigned', 'reassigned']
        return any(keyword in note_lower for keyword in assignee_keywords)
    
    def _parse_assignee_note(self, note_body: str) -> Tuple[str, Optional[str]]:
        """Parse assignee note to extract event type and assignee info."""
        note_lower = note_body.lower()
        
        if 'unassigned' in note_lower:
            return 'unassigned', None
        elif 'reassigned' in note_lower:
            return 'reassigned', self._extract_username_from_note(note_body)
        elif 'assigned' in note_lower:
            return 'assigned', self._extract_username_from_note(note_body)
        
        return 'unknown', None
    
    def _extract_username_from_note(self, note_body: str) -> Optional[str]:
        """Extract username from note body."""
        # Try to find @username pattern
        username_match = re.search(r'@([\w\.\-]+)', note_body)
        if username_match:
            return username_match.group(1)
        
        # Try to find "to User Name" pattern
        assigned_match = re.search(r'to\s+([^@\n]+)', note_body, re.IGNORECASE)
        if assigned_match:
            return assigned_match.group(1).strip()
        
        return None
    
    def get_combined_history(self, project_id: int, issue_iid: int) -> Dict:
        """
        Gets combined history of labels and assignee changes.
        Returns sorted list of all events.
        """
        try:
            # Get both histories
            label_history = self.get_label_history(project_id, issue_iid)
            assignee_history = self.get_assignee_history(project_id, issue_iid)
            
            # Combine and sort by timestamp
            all_events = label_history + assignee_history
            
            # Convert timestamp strings to datetime for proper sorting
            for event in all_events:
                try:
                    event['timestamp_dt'] = datetime.fromisoformat(
                        event['timestamp'].replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    event['timestamp_dt'] = datetime.max
            
            # Sort by timestamp
            all_events.sort(key=lambda x: x['timestamp_dt'])
            
            # Remove temporary datetime field
            for event in all_events:
                if 'timestamp_dt' in event:
                    del event['timestamp_dt']
            
            # Get current task info for context
            current_task = self._get_issue_info(project_id, issue_iid)
            
            return {
                'task_info': current_task,
                'total_events': len(all_events),
                'label_events': len(label_history),
                'assignee_events': len(assignee_history),
                'history': all_events
            }
            
        except Exception as e:
            logger.error(f"Error getting combined history: {e}")
            return {
                'task_info': None,
                'total_events': 0,
                'label_events': 0,
                'assignee_events': 0,
                'history': []
            }
    
    def _get_issue_info(self, project_id: int, issue_iid: int) -> Optional[Dict]:
        """Get basic issue information."""
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            issue = response.json()
            
            return {
                'id': issue.get('id'),
                'iid': issue.get('iid'),
                'title': issue.get('title'),
                'state': issue.get('state'),
                'current_labels': issue.get('labels', []),
                'current_assignee': issue.get('assignee'),
                'created_at': issue.get('created_at'),
                'updated_at': issue.get('updated_at')
            }
        except Exception as e:
            logger.error(f"Error getting issue info: {e}")
            return None
    
    def get_full_task_history(self, project_id: int, issue_iid: int, include_comments: bool = False) -> Dict:
        """
        Comprehensive method to get complete task history.
        """
        # Get combined history
        combined = self.get_combined_history(project_id, issue_iid)
        
        # Optionally get regular comments
        if include_comments:
            try:
                page = 1
                all_comments = []
                
                while True:
                    response = requests.get(
                        f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
                        params={'page': page, 'per_page': 100},
                        headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
                    )
                    response.raise_for_status()
                    
                    comments = response.json()
                    if not comments:
                        break
                        
                    all_comments.extend(comments)
                    page += 1
                
                # Filter out system notes (already in history)
                regular_comments = [
                    comment for comment in all_comments
                    if not comment.get('system', False)
                ]
                
                combined['comments'] = {
                    'count': len(regular_comments),
                    'list': regular_comments[:10]  # Return first 10 comments
                }
                
            except Exception as e:
                logger.error(f"Error getting comments: {e}")
                combined['comments'] = {'count': 0, 'list': []}
        
        return combined

    def get_all_repos(self) -> List[int]:
        """Get all project IDs."""
        projects = []
        page = 1
        per_page = 100
        
        logger.info("Getting all projects...")
        
        while True:
            url = f"{self.config.gitlab_url}/api/v4/projects"
            params = {
                "per_page": per_page,
                "page": page,
                "simple": "true",
                "with_issues_enabled": "false",
                "with_merge_requests_enabled": "false"
            }
            
            response = requests.get(
                url,
                params=params,
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            
            page_projects = response.json()
            if not page_projects:
                logger.info(f"No projects on page {page}. Finished parsing.")
                break
            
            # Extract only project IDs
            page_project_ids = [project['id'] for project in page_projects]
            projects.extend(page_project_ids)
            
            logger.info(f"Got projects from page {page}")
            page += 1
        
        logger.info(f"Total projects found: {len(projects)}")
        return projects