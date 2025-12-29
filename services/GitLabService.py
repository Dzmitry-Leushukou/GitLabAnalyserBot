from services.config import Config
import logging
import requests
from typing import List, Dict, Optional

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
                    'raw_action': action
                }
                events_by_date.append(event_info)
            
            # Sort events by time
            events_by_date.sort(key=lambda x: x['timestamp'])
            return events_by_date
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting label history: {e}")
            return []
        


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

    def get_assignee_history(self, project_id, issue_iid):
        """
        Gets the assignee change history for a specific task.
        """
        import gitlab
        from datetime import datetime
        
        try:
            # Connect to GitLab using the python-gitlab library
            if self.config.gitlab_url:
                gl = gitlab.Gitlab(url=self.config.gitlab_url, private_token=self.config.gitlab_token)
            else:
                gl = gitlab.Gitlab(private_token=self.config.gitlab_token)
            
            if self.config.gitlab_token and 'CI_JOB_TOKEN' not in self.config.gitlab_token:
                gl.auth()
            
            # Get the project and issue
            project = gl.projects.get(project_id)
            issue = project.issues.get(issue_iid)
            
            # Get all notes for the issue
            all_notes = issue.notes.list(all=True)
            
            assignee_history = []
            for note in all_notes:
                # Look for system notes about assignee changes
                if note.system and "assignee" in note.body.lower():
                    note_text = note.body.lower()
                    created_at = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
                    
                    # Determine action type
                    if "assigned to" in note_text or "назначил" in note_text:
                        action = "assigned"
                        user_info = note.body
                    elif "unassigned" in note_text or "убрал назначение" in note_text:
                        action = "unassigned"
                        user_info = "Unassigned"
                    elif "reassigned to" in note_text:
                        action = "reassigned"
                        user_info = note.body
                    else:
                        continue  # Skip other system notes
                    
                    # Get author information
                    author_name = "System"
                    if note.author:
                        author_name = note.author.get('name', 'Unknown author')
                    
                    event_info = {
                        'timestamp': created_at,
                        'action': action,
                        'info': note.body,  # Full text of system note
                        'author': author_name
                    }
                    assignee_history.append(event_info)
            
            # Sort events by time
            assignee_history.sort(key=lambda x: x['timestamp'])
            return assignee_history
            
        except Exception as e:
            logger.error(f"Error getting assignee history: {e}")
            return []

    def get_full_issue_history(self, project_id, issue_iid):
        """
        Gets the complete history of changes for a specific task (labels + assignees).
        """
        import gitlab
        from datetime import datetime
        
        try:
            # Connect to GitLab using the python-gitlab library
            if self.config.gitlab_url:
                gl = gitlab.Gitlab(url=self.config.gitlab_url, private_token=self.config.gitlab_token)
            else:
                gl = gitlab.Gitlab(private_token=self.config.gitlab_token)
            
            if self.config.gitlab_token and 'CI_JOB_TOKEN' not in self.config.gitlab_token:
                gl.auth()
            
            # Get the project and issue
            project = gl.projects.get(project_id)
            issue = project.issues.get(issue_iid)
            
            # Get all notes for the issue
            all_notes = issue.notes.list(all=True)
            
            # Process all system notes
            system_notes = []
            for note in all_notes:
                if note.system:
                    created_at = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
                    author_name = "System"
                    if note.author:
                        author_name = note.author.get('name', 'Unknown author')
                    
                    system_note = {
                        'timestamp': created_at,
                        'body': note.body,
                        'author': author_name
                    }
                    system_notes.append(system_note)
            
            # Sort by time
            system_notes.sort(key=lambda x: x['timestamp'])
            
            # Group by change type
            label_changes = []
            assignee_changes = []
            other_changes = []
            
            for note in system_notes:
                body_lower = note['body'].lower()
                
                if "label" in body_lower:
                    label_changes.append(note)
                elif "assign" in body_lower or "назнач" in body_lower:
                    assignee_changes.append(note)
                else:
                    other_changes.append(note)
            
            return {
                'label_changes': label_changes,
                'assignee_changes': assignee_changes,
                'other_changes': other_changes,
                'total_system_notes': len(system_notes)
            }
            
        except Exception as e:
            logger.error(f"Error getting full issue history: {e}")
            return {
                'label_changes': [],
                'assignee_changes': [],
                'other_changes': [],
                'total_system_notes': 0
            }
