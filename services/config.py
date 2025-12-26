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
            cls._instance.__page_size = os.getenv("PAGE_SIZE")

            if not cls._instance.__page_size:
                raise ValueError("PAGE_SIZE is not set")
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