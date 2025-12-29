from services.config import Config
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime

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
    
    def get_users(self, page:int):
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

    def get_user(self, user_id:int):
        response = requests.get(
            self.config.gitlab_url + '/api/v4/users/' + str(user_id),
            headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
        )
        return response.json()

    def get_user_tasks(self, user_id):
        """
        Gets all tasks where the user was an assignee.
        """
        projects = self.get_all_repos()
        all_tasks = []
        for project in projects:
            # Find tasks where the user was an assignee
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project}/issues",
                params={
                    'assignee_id': user_id,
                    'state': 'all'  # Get all tasks (open and closed)
                },
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            tasks = response.json()
            all_tasks.extend(tasks)
        return all_tasks

    def get_label_history(self, project_id, issue_iid):
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
            
            # Process and format events
            events_by_date = []
            for event in label_events:
                # Convert event time
                created_at = event.get('created_at')
                
                # Determine action type
                action = event.get('action')
                if action == "add":
                    action_text = "added"
                elif action == "remove":
                    action_text = "removed"
                else:
                    action_text = action
                
                # Get user information
                user_name = "Unknown user"
                if event.get('user'):
                    user_name = event['user'].get('name', 'Unknown user')
                
                event_info = {
                    'timestamp': created_at,
                    'label': event.get('label', {}).get('name', 'Unknown label'),
                    'action': action_text,
                    'user': user_name,
                    'raw_action': action,
                    'type': 'label'
                }
                events_by_date.append(event_info)
            
            return events_by_date
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting label history: {e}")
            return []
    
    def get_assignee_history(self, project_id, issue_iid):
        """
        Gets the assignee change history from system notes.
        Returns list of assignee events sorted by timestamp.
        """
        try:
            # First get all notes for the issue
            page = 1
            all_notes = []
            
            while True:
                response = requests.get(
                    f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
                    params={
                        'page': page,
                        'per_page': 100
                    },
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
                # Check if it's a system note about assignee
                if note.get('system') and self._is_assignee_note(note.get('body', '')):
                    body = note.get('body', '')
                    created_at = note.get('created_at')
                    
                    # Parse assignee change information
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
        """
        Check if a system note is about assignee changes.
        """
        note_lower = note_body.lower()
        assignee_keywords = [
            'assigned', 'unassigned', 'reassigned',
            'назначил', 'назначение', 'назначен'
        ]
        
        return any(keyword in note_lower for keyword in assignee_keywords)
    
    def _parse_assignee_note(self, note_body: str) -> tuple:
        """
        Parse assignee note to extract event type and assignee info.
        Returns (event_type, assignee_info)
        """
        note_lower = note_body.lower()
        
        if 'unassigned' in note_lower or 'убрал назначение' in note_lower:
            return 'unassigned', None
        elif 'reassigned' in note_lower:
            return 'reassigned', self._extract_username_from_note(note_body)
        elif 'assigned' in note_lower or 'назначил' in note_lower:
            return 'assigned', self._extract_username_from_note(note_body)
        
        return 'unknown', None
    
    def _extract_username_from_note(self, note_body: str) -> Optional[str]:
        """
        Extract username from note body.
        Looks for @username patterns or mentions.
        """
        import re
        
        # Try to find @username pattern
        username_match = re.search(r'@([\w\.\-]+)', note_body)
        if username_match:
            return username_match.group(1)
        
        # Try to find "to User Name" pattern
        assigned_match = re.search(r'(?:to|на)\s+([^@\n]+)', note_body, re.IGNORECASE)
        if assigned_match:
            return assigned_match.group(1).strip()
        
        return None
    
    def get_combined_history(self, project_id, issue_iid):
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
                    # Convert ISO format string to datetime
                    event['timestamp_dt'] = datetime.fromisoformat(
                        event['timestamp'].replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    # If conversion fails, use a far future date for sorting
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
    
    def _get_issue_info(self, project_id, issue_iid):
        """
        Get basic issue information.
        """
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
    
    def get_issue_events(self, project_id, issue_iid):
        """
        Alternative method: Get issue events (might contain assignee changes).
        Note: This API endpoint might not be available on all GitLab instances.
        """
        try:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project_id}/issues/{issue_iid}/events",
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            
            if response.status_code == 200:
                events = response.json()
                # Filter for assignee-related events
                assignee_events = [
                    event for event in events 
                    if event.get('action') in ['assigned', 'unassigned']
                ]
                return assignee_events
            else:
                logger.warning(f"Events API not available (status {response.status_code})")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting issue events: {e}")
            return []
    
    def get_full_task_history(self, project_id, issue_iid, include_comments=False):
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
                        params={
                            'page': page,
                            'per_page': 100
                        },
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

    def get_all_repos(self):
        projects = []
        page = 1
        per_page = 100
        logger.info("Start getting all repos")

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
                logger.info(f"No project on {page}. The end of parsing")
                break

            # Extract only project IDs to reduce memory usage
            page_project_ids = [project['id'] for project in page_projects]
            projects.extend(page_project_ids)

            logger.info(f"Projects from page {page} was got")
            page+=1

        return projects