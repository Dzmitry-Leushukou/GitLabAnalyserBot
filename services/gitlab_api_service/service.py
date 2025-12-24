import requests
import time
import logging
from typing import List, Dict, Optional

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


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
        self.base_url = f"{self.gitlab_url}/api/v4"
        self.headers = {
            "PRIVATE-TOKEN": self.access_token,
            "Content-Type": "application/json"
        }

    def get_all_users(self, params: Optional[Dict] = None) -> List[Dict]:
        """
        Get all GitLab users via API
        
        Args:
            params (dict, optional): Additional request parameters
        
        Returns:
            list: List of all users or empty list in case of error
        """
        
        api_url = f"{self.base_url}/users"
        
        if params is None:
            params = {
                'per_page': 100,  
                'active': True 
            }
        
        all_users = []
        page = 1
        
        logger.info(f"🔍 Starting to fetch users from {api_url}")
        
        try:
            while True:
                current_params = params.copy()
                current_params['page'] = page
                
                logger.info(f"📄 Requesting page {page}...")
                
                response = requests.get(
                    api_url, 
                    headers=self.headers, 
                    params=current_params,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ API Error: {response.status_code}")
                    logger.error(f"Response: {response.text[:200]}")
                    break
                
                users = response.json()
                
                if not users:
                    logger.info("✅ No more users")
                    break
                
                all_users.extend(users)
                logger.info(f"✅ Added {len(users)} users, total: {len(all_users)}")
                
                total_pages = response.headers.get('X-Total-Pages')
                if total_pages:
                    total_pages = int(total_pages)
                    logger.info(f"📊 Page {page} of {total_pages}")
                    if page >= total_pages:
                        break
                
                page += 1
                
                time.sleep(0.1)
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error. Check URL and network.")
            return []
        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout. Server is not responding.")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return []
        
        logger.info(f"\n🎉 Total users received: {len(all_users)}")
        return all_users