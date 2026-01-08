import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Configuration class implementing Singleton pattern for managing bot configuration.
    
    This class handles loading environment variables and provides access to
    bot configuration parameters such as Telegram token and default project ID.
    It ensures only one instance of configuration exists throughout the application.
    
    Attributes:
        __telegram_token (str): Telegram bot API token
        __default_project_id (str): Default GitLab project ID for task creation
        
    Example:
        >>> config = Config()
        >>> token = config.telegram_token
        >>> project_id = config.default_project_id
    """
    _instance = None

    def __new__(cls):
        """
        Create or return the singleton instance of the Config class.
        
        This method ensures that only one instance of the Config class exists
        throughout the application lifecycle. It loads environment variables
        and validates required configuration parameters.
        
        Returns:
            Config: The singleton instance of the Config class
            
        Raises:
            ValueError: If required environment variables are not set
        """
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
        """
        Get the Telegram bot API token.
        
        Returns:
            str: The Telegram bot API token used for authentication with Telegram API
        """
        return self.__telegram_token
    
    @property
    def default_project_id(self):
        """
        Get the default GitLab project ID.
        
        Returns:
            str: The default GitLab project ID used for task creation when no specific project is specified
        """
        return self.__default_project_id