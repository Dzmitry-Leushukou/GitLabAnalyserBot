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
        Gets ALL tasks where the user was EVER an assignee.
        Includes both current assignments and historical assignments.
        """
        # Get user info first
        user_info = self.get_user(user_id)
        if not user_info:
            logger.error(f"User {user_id} not found")
            return []
        
        username = user_info.get('username')
        logger.info(f"Searching for ALL tasks where user {username} was EVER assignee...")
        
        # Get current tasks where user is assignee
        current_tasks = self._get_current_assignee_tasks(user_id)
        logger.info(f"Found {len(current_tasks)} current tasks")
        
        # Get ALL accessible projects
        all_projects = self.get_all_repos()
        logger.info(f"Will search in {len(all_projects)} total projects")
        
        # Search for historical assignments in ALL projects
        historical_tasks = []
        processed_projects = 0
        
        for project_id in all_projects:
            try:
                project_tasks = self._search_assignee_in_project_history(project_id, user_id, username)
                if project_tasks:
                    historical_tasks.extend(project_tasks)
                    logger.info(f"Project {project_id}: found {len(project_tasks)} historical tasks")
                    
            except Exception as e:
                logger.error(f"Error searching project {project_id}: {e}")
                continue
            
            processed_projects += 1
            
            logger.info(f"Processed {processed_projects}/{len(all_projects)} projects")
        
        # Combine and deduplicate
        all_tasks = current_tasks + historical_tasks
        unique_tasks = self._deduplicate_tasks(all_tasks)
        
        logger.info(f"Total unique tasks found: {len(unique_tasks)} (Current: {len(current_tasks)}, Historical: {len(historical_tasks)})")
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
                    
            except Exception as e:
                logger.error(f"Error getting current tasks page {page}: {e}")
                break
        
        return tasks
    
    def _search_assignee_in_project_history(self, project_id: int, user_id: int, username: str) -> List[Dict]:
        """
        Search for tasks in a project where user was EVER assignee.
        Checks system notes for historical assignments.
        """
        try:
            # First check if project has issues enabled
            project_info = self._get_project_info(project_id)
            if not project_info.get('issues_enabled', True):
                logger.debug(f"Project {project_id} has issues disabled, skipping")
                return []
            
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
                    task_iid = task.get('iid')
                    
                    # Check if user was EVER assignee by checking system notes
                    if self._check_user_was_assignee(project_id, task_iid, user_id, username):
                        # Check if already found
                        if not any(t.get('iid') == task_iid and t.get('project_id') == project_id for t in found_tasks):
                            found_tasks.append(task)
                
                logger.info(f"Found {len(found_tasks)} tasks in project {project_id}. Current page: {page}")
                page += 1
                    
        except Exception as e:
            logger.error(f"Error searching project {project_id}: {e}")
        
        return found_tasks
    
    def _get_project_info(self, project_id: int) -> Dict:
        """Get basic project information."""
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}
    
    def _check_user_was_assignee(self, project_id: int, issue_iid: int, user_id: int, username: str) -> bool:
        """
        Check if user was EVER assignee for this issue.
        Examines system notes for assignment history.
        """
        try:
            # First check current assignee
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            
            if response.status_code == 200:
                issue = response.json()
                current_assignee = issue.get('assignee')
                if current_assignee and current_assignee.get('id') == user_id:
                    return True
            
            # Check system notes for historical assignments
            page = 1
            while True:
                response = requests.get(
                    f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
                    params={'per_page': 100, 'page': page},
                    headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
                )
                
                if response.status_code != 200:
                    break
                
                notes = response.json()
                if not notes:
                    break
                
                for note in notes:
                    if note.get('system'):
                        body = note.get('body', '').lower()
                        
                        # Check for assignee patterns with username
                        patterns = [
                            f'assigned to @{username}',
                            f'reassigned to @{username}',
                            f'unassigned @{username}',
                            f'assigned to {username}',
                            f'reassigned to {username}',
                            f'unassigned {username}',
                            f'assigned to @{username.lower()}',
                            f'reassigned to @{username.lower()}'
                        ]
                        
                        for pattern in patterns:
                            if pattern in body:
                                return True
                        
                        # Check for patterns like "Some User assigned to @username"
                        if 'assigned to' in body and f'@{username}' in body:
                            return True
                        if 'reassigned to' in body and f'@{username}' in body:
                            return True
                
                page += 1
                    
        except Exception as e:
            logger.error(f"Error checking assignee history for issue {issue_iid}: {e}")
        
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

    def get_task_estimate_time(self, project_id: int, issue_iid: int) -> int:
        """
        Gets the estimate time for a specific task.
        Returns the time in seconds.
        """
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            
            issue = response.json()
            
            # GitLab has time tracking functionality with time estimates
            # The estimate is stored in 'time_stats' field
            time_stats = issue.get('time_stats', {})
            if time_stats:
                # 'time_estimate' is in seconds
                estimate_time = time_stats.get('time_estimate', 0)
                return estimate_time if estimate_time is not None else 0
            else:
                # If time_stats is not available, try to get it from the issue directly
                # In some cases, GitLab might store it differently
                return 0
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting estimate time for issue {issue_iid}: {e}")
            return 0

    def get_cycle_time(self, project_id: int, issue_iid: int, assignee_id: int = None) -> Dict:
        """
        Calculates the cycle time for a specific task.
        Cycle time is the time the task spent with the 'doing' label AND when the specified user was assignee.
        If assignee_id is not provided, calculates for the current assignee.
        Returns a dictionary with cycle time information and assignee details.
        """
        def safe_timestamp_to_datetime(timestamp):
            if isinstance(timestamp, str):
                try:
                    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    # If timestamp conversion fails, return a default datetime
                    return datetime.min
            elif isinstance(timestamp, datetime):
                return timestamp
            else:
                return datetime.min
        
        try:
            # Get combined history to track 'doing' label changes and assignee changes
            combined_history = self.get_combined_history(project_id, issue_iid)
            history_events = combined_history.get('history', [])
            
            # Get issue creation time
            issue_info = self._get_issue_info(project_id, issue_iid)
            if not issue_info:
                return {
                    'cycle_time_seconds': 0,
                    'cycle_time_formatted': '0 seconds',
                    'intervals': [],
                    'assignees_during_cycle': [],
                    'target_assignee_id': assignee_id
                }
            
            created_at = issue_info.get('created_at')
            created_datetime = safe_timestamp_to_datetime(created_at)
            
            # Track 'doing' label intervals
            doing_intervals = []
            assignees_during_cycle = []
            current_doing_start = None
            current_assignee_id = None
            target_assignee_id = assignee_id
            
            # If assignee_id not provided, try to get current assignee's ID
            if target_assignee_id is None and issue_info.get('current_assignee'):
                target_assignee_id = issue_info['current_assignee'].get('id')
            
            # Get initial assignee from the issue info
            if issue_info.get('current_assignee') and issue_info['current_assignee'].get('id'):
                current_assignee_id = issue_info['current_assignee']['id']
            
            # Sort events by timestamp to process in chronological order
            sorted_events = sorted(history_events, key=lambda x: safe_timestamp_to_datetime(x['timestamp']))
            
            for event in sorted_events:
                event_time = safe_timestamp_to_datetime(event['timestamp'])
                
                # Handle label events
                if event['type'] == 'label':
                    label_name = event['label'].lower()
                    
                    # If 'doing' label was added and we're not already in a doing interval
                    if label_name == 'doing' and event['raw_action'] == 'add':
                        if current_doing_start is None:
                            # Only start interval if target assignee is currently assigned
                            if current_assignee_id == target_assignee_id:
                                current_doing_start = event_time
                    # If 'doing' label was removed and we're in a doing interval
                    elif label_name == 'doing' and event['raw_action'] == 'remove':
                        if current_doing_start is not None:
                            # Close the current doing interval
                            doing_intervals.append({
                                'start': current_doing_start.isoformat(),
                                'end': event_time.isoformat(),
                                'duration': (event_time - current_doing_start).total_seconds(),
                                'assignee_id': current_assignee_id
                            })
                            if current_assignee_id:
                                assignees_during_cycle.append({
                                    'assignee_id': current_assignee_id,
                                    'interval_start': current_doing_start.isoformat(),
                                    'interval_end': event_time.isoformat()
                                })
                            current_doing_start = None
                
                # Handle assignee events
                elif event['type'] == 'assignee':
                    action = event['action']
                    assignee_info = event.get('assignee')
                    
                    if action == 'assigned' or action == 'reassigned':
                        # Extract assignee ID by checking the author of the event or looking up the user
                        assignee_username = assignee_info.get('name') if isinstance(assignee_info, dict) else assignee_info
                        if assignee_username:
                            # Look up user ID by username from the event author or by searching
                            assignee_user = self._find_user_by_name(assignee_username)
                            if assignee_user:
                                new_assignee_id = assignee_user.get('id')
                                # Check if this assignment affects our target interval
                                was_in_doing = current_doing_start is not None
                                
                                current_assignee_id = new_assignee_id
                                
                                # If we were in a doing interval and the assignee changed to someone else, close the interval
                                if was_in_doing and current_assignee_id != target_assignee_id:
                                    doing_intervals.append({
                                        'start': current_doing_start.isoformat(),
                                        'end': event_time.isoformat(),
                                        'duration': (event_time - current_doing_start).total_seconds(),
                                        'assignee_id': current_assignee_id
                                    })
                                    if current_assignee_id:
                                        assignees_during_cycle.append({
                                            'assignee_id': current_assignee_id,
                                            'interval_start': current_doing_start.isoformat(),
                                            'interval_end': event_time.isoformat()
                                        })
                                    current_doing_start = None
                                # If we weren't in a doing interval and assignee changed to target, check if in doing state
                                elif not was_in_doing and current_assignee_id == target_assignee_id:
                                    # Check if currently in 'doing' state
                                    if self._is_issue_in_doing_state(project_id, issue_iid, event_time):
                                        current_doing_start = event_time
                                        
                    elif action == 'unassigned':
                        # Check if this affects our target interval
                        was_in_doing = current_doing_start is not None
                        
                        current_assignee_id = None
                        
                        # If we were in a doing interval and assignee was unassigned, close the interval
                        if was_in_doing and target_assignee_id is not None:
                            doing_intervals.append({
                                'start': current_doing_start.isoformat(),
                                'end': event_time.isoformat(),
                                'duration': (event_time - current_doing_start).total_seconds(),
                                'assignee_id': None
                            })
                            assignees_during_cycle.append({
                                'assignee_id': None,
                                'interval_start': current_doing_start.isoformat(),
                                'interval_end': event_time.isoformat()
                            })
                            current_doing_start = None
            
            # If still in a doing interval at the end of history, close it with the last event time
            if current_doing_start is not None:
                last_event_timestamp = sorted_events[-1]['timestamp'] if sorted_events else created_datetime
                last_event_time = safe_timestamp_to_datetime(last_event_timestamp)
                
                doing_intervals.append({
                    'start': current_doing_start.isoformat(),
                    'end': last_event_time.isoformat(),
                    'duration': (last_event_time - current_doing_start).total_seconds(),
                    'assignee_id': current_assignee_id
                })
                if current_assignee_id:
                    assignees_during_cycle.append({
                        'assignee_id': current_assignee_id,
                        'interval_start': current_doing_start.isoformat(),
                        'interval_end': last_event_time.isoformat()
                    })
            
            # Calculate total cycle time
            total_cycle_time = sum(interval['duration'] for interval in doing_intervals)
            
            # Format total cycle time
            if total_cycle_time <= 0:
                formatted_time = '0 seconds'
            else:
                days = int(total_cycle_time // 86400)
                hours = int((total_cycle_time % 86400) // 3600)
                minutes = int((total_cycle_time % 3600) // 60)
                seconds = int(total_cycle_time % 60)
                
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
            
            return {
                'cycle_time_seconds': int(total_cycle_time),
                'cycle_time_formatted': formatted_time,
                'intervals': doing_intervals,
                'assignees_during_cycle': assignees_during_cycle,
                'issue_info': issue_info,
                'target_assignee_id': target_assignee_id
            }
                
        except Exception as e:
            logger.error(f"Error calculating cycle time for issue {issue_iid}: {e}")
            return {
                'cycle_time_seconds': 0,
                'cycle_time_formatted': '0 seconds',
                'intervals': [],
                'assignees_during_cycle': [],
                'target_assignee_id': assignee_id,
                'error': str(e)
            }
    
    def _find_user_by_name(self, username: str) -> Optional[Dict]:
        """
        Find user by username by searching through the API.
        """
        try:
            # First try to get user by username
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/users",
                params={'username': username},
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            users = response.json()
            
            if users:
                return users[0]  # Return first match
            
            # If not found by username, try searching by name
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/users",
                params={'search': username},
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            users = response.json()
            
            if users:
                return users[0]  # Return first match
            
        except Exception as e:
            logger.error(f"Error finding user by name {username}: {e}")
        
        return None
    
    def _is_issue_in_doing_state(self, project_id: int, issue_iid: int, at_time: datetime) -> bool:
        """
        Check if the issue was in 'doing' state at a specific time.
        This requires checking the label history up to that point in time.
        """
        try:
            # Get label history
            label_events = self.get_label_history(project_id, issue_iid)
            
            # Filter events up to the specified time
            relevant_events = []
            for event in label_events:
                event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                if event_time <= at_time:
                    relevant_events.append(event)
            
            # Sort by timestamp
            relevant_events.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')))
            
            # Track the state of the 'doing' label
            doing_active = False
            for event in relevant_events:
                if event['label'].lower() == 'doing':
                    if event['raw_action'] == 'add':
                        doing_active = True
                    elif event['raw_action'] == 'remove':
                        doing_active = False
            
            return doing_active
            
        except Exception as e:
            logger.error(f"Error checking if issue {issue_iid} was in doing state: {e}")
            return False