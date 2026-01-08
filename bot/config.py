import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            cls._instance.__telegram_token = os.getenv("TELEGRAM_TOKEN")
            if not cls._instance.__telegram_token:
                raise ValueError("TELEGRAM_TOKEN is not set")
        
            cls._instance.__default_project_id=os.getenv("DEFAULT_PROJECT_ID")
            if not cls._instance.__default_project_id:
                raise ValueError("DEFAULT_PROJECT_ID is not set")
        return cls._instance

    @property
    def telegram_token(self):
        return self.__telegram_token 
    @property
    def default_project_id(self):
        return self.__default_project_id