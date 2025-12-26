from services.config import Config
import logging
import requests
from typing import List, Dict, Optional


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

