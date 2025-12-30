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
            'active': True
        }
        
        url = f"{self.config.gitlab_url}/api/v4/users"
        
        try:
            async with self._session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching users: {e}")
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
    
    