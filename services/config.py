import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            cls._instance.__gitlab_url = os.getenv("GITLAB_URL")
            cls._instance.__gitlab_token = os.getenv("GITLAB_TOKEN")
            page_size_env = os.getenv("PAGE_SIZE")
            progress_step_env = os.getenv("PROGRESS_STEP")
            
            if not page_size_env or not progress_step_env:
                raise ValueError("PAGE_SIZE or PROGRESS_STEP is not set")
            
            try:
                cls._instance.__page_size = int(page_size_env)
                cls._instance.__progress_step = int(progress_step_env)
            except ValueError:
                raise ValueError("PAGE_SIZE and PROGRESS_STEP must be valid integers")

            if not cls._instance.__gitlab_url:
                raise ValueError("GITLAB_URL is not set")
            if not cls._instance.__gitlab_token:
                raise ValueError("GITLAB_TOKEN is not set")
        
        return cls._instance

    @property
    def gitlab_url(self):
        return self.__gitlab_url

    @property
    def gitlab_token(self):
        return self.__gitlab_token
    
    @property
    def page_size(self):
        return self.__page_size
    
    @property
    def progress_step(self):
        return self.__progress_step