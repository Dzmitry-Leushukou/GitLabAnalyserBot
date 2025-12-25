import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def get_all_users(
    gitlab_url: str, 
    access_token: str, 
    params: Optional[Dict] = None,
    get_full_info: bool = False
) -> List[Dict]:
    """
    Get GitLab users
    
    Args:
        gitlab_url: GitLab URL without /api/v4
        access_token: Personal Access Token
        params: Additional API params
        get_full_info: If True, tries to get email and full profile
    """
    
    base_url = f"{gitlab_url.rstrip('/')}/api/v4"
    
    # Для полной информации используем другой запрос
    if get_full_info:
        all_users = []
        
        # Сначала получаем базовый список
        basic_users = get_all_users(gitlab_url, access_token, params, False)
        
        # Затем для каждого пользователя запрашиваем детальную инфу
        for user in basic_users:
            user_id = user.get('id')
            if user_id:
                detailed_user = get_single_user(gitlab_url, access_token, user_id)
                if detailed_user:
                    all_users.append(detailed_user)
                else:
                    all_users.append(user)
            else:
                all_users.append(user)
                
        return all_users
    
    # Базовый запрос (как было)
    api_url = f"{base_url}/users"
    
    headers = {
        "PRIVATE-TOKEN": access_token,
        "Content-Type": "application/json"
    }
    
    if params is None:
        params = {
            'per_page': 100,
            'active': True
        }
    
    all_users = []
    page = 1
    
    try:
        while True:
            current_params = params.copy()
            current_params['page'] = page
            
            response = requests.get(
                api_url, 
                headers=headers, 
                params=current_params,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"API Error {response.status_code}")
                break
            
            users = response.json()
            
            if not users:
                break
            
            all_users.extend(users)
            
            # Проверяем, есть ли еще страницы
            next_page = response.headers.get('X-Next-Page')
            if not next_page:
                break
                
            page = int(next_page)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return []
    
    
    return all_users


def get_single_user(
    gitlab_url: str, 
    access_token: str, 
    user_id: int
) -> Optional[Dict]:
    """Get detailed info for specific user"""
    
    base_url = f"{gitlab_url.rstrip('/')}/api/v4"
    api_url = f"{base_url}/users/{user_id}"
    
    headers = {
        "PRIVATE-TOKEN": access_token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Can't get user {user_id}: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    
    return None


def search_users(
    gitlab_url: str,
    access_token: str,
    search: str,
    max_results: int = 50
) -> List[Dict]:
    """Search users by username, email or name"""
    
    base_url = f"{gitlab_url.rstrip('/')}/api/v4"
    api_url = f"{base_url}/users"
    
    headers = {
        "PRIVATE-TOKEN": access_token,
        "Content-Type": "application/json"
    }
    
    params = {
        'search': search,
        'per_page': min(max_results, 100),
        'active': True
    }
    
    try:
        response = requests.get(
            api_url,
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Search error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    
    return []