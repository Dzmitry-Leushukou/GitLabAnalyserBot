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

    def get_all_tasks(self):
        projects = self.get_all_repos()
        all_tasks = []
        for project in projects:
            response = requests.get(
                f"{self.config.gitlab_url}/api/v4/projects/{project}/issues",
                params={'type': 'task'},
                headers={'Authorization': 'Bearer ' + self.config.gitlab_token}
            )
            response.raise_for_status()
            tasks = response.json()
            all_tasks.extend(tasks)
        return all_tasks
        


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