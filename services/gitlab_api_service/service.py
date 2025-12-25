import logging
from typing import List, Dict, Optional
from api.GitLab.users import get_all_users

# Set up logger
logger = logging.getLogger(__name__)


class GitLabApiService:
    def __init__(self, gitlab_url: str, access_token: str):
        """
        Initialize GitLab API service
        
        Args:
            gitlab_url (str): URL of your GitLab instance (without /api/v4)
            access_token (str): Personal Access Token with appropriate permissions
        """
        self.gitlab_url = gitlab_url.rstrip('/')
        self.access_token = access_token

    def get_all_users(self, params: Optional[Dict] = None) -> List[Dict]:
        """
        Get all GitLab users via API
        
        Args:
            params (dict, optional): Additional request parameters
        
        Returns:
            list: List of all users or empty list in case of error
        """
        return get_all_users(self.gitlab_url, self.access_token, params)