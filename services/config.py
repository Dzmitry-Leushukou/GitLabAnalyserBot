import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Configuration class implementing Singleton pattern for managing service configuration.
    
    This class handles loading environment variables and provides access to
    service configuration parameters such as GitLab URL, token, and various API settings.
    It ensures only one instance of configuration exists throughout the application.
    
    Attributes:
        __gitlab_url (str): GitLab instance URL
        __gitlab_token (str): GitLab API token
        __page_size (int): Number of items per page for pagination
        __progress_step (int): Step interval for progress updates
        __llm_url (str): LLM service URL
        __create_task_llm_api_key (str): API key for creating tasks via LLM
        __get_labels_llm_api_key (str): API key for getting labels via LLM
        __whisper_api_key (str): Whisper API key for voice recognition
        __default_project_id (str): Default GitLab project ID for task creation
        
    Example:
        >>> config = Config()
        >>> gitlab_url = config.gitlab_url
        >>> token = config.gitlab_token
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
            ValueError: If required environment variables are not set or invalid
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            cls._instance.__gitlab_url = os.getenv("GITLAB_URL")
            cls._instance.__gitlab_token = os.getenv("GITLAB_TOKEN")
            page_size_env = os.getenv("PAGE_SIZE")
            progress_step_env = os.getenv("PROGRESS_STEP")
            cls._instance.__llm_url = os.getenv("LLM_URL")
            cls._instance.__create_task_llm_api_key = os.getenv("CREATE_TASK_LLM_API_KEY")
            cls._instance.__get_labels_llm_api_key = os.getenv("GET_LABELS_LLM_API_KEY")
            cls._instance.__whisper_api_key = os.getenv("WHISPER_API_KEY")
            cls._instance.__default_project_id = os.getenv("DEFAULT_PROJECT_ID")
            
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
        """
        Get the GitLab instance URL.
        
        Returns:
            str: The GitLab instance URL used for API calls
        """
        return self.__gitlab_url

    @property
    def gitlab_token(self):
        """
        Get the GitLab API token.
        
        Returns:
            str: The GitLab API token used for authentication with GitLab API
        """
        return self.__gitlab_token
    
    @property
    def page_size(self):
        """
        Get the page size for pagination.
        
        Returns:
            int: The number of items per page for pagination
        """
        return self.__page_size
    
    @property
    def progress_step(self):
        """
        Get the progress step interval.
        
        Returns:
            int: The interval for progress updates during processing
        """
        return self.__progress_step
    
    @property
    def llm_url(self):
        """
        Get the LLM service URL.
        
        Returns:
            str: The URL of the LLM service for AI-powered features
        """
        return self.__llm_url
    
    @property
    def create_task_llm_api_key(self):
        """
        Get the API key for creating tasks via LLM.
        
        Returns:
            str: The API key used for creating tasks through LLM service
        """
        return self.__create_task_llm_api_key
    
    @property
    def get_labels_llm_api_key(self):
        """
        Get the API key for getting labels via LLM.
        
        Returns:
            str: The API key used for retrieving labels through LLM service
        """
        return self.__get_labels_llm_api_key
    
    @property
    def whisper_api_key(self):
        """
        Get the Whisper API key for voice recognition.
        
        Returns:
            str: The API key used for Whisper voice recognition service
        """
        return self.__whisper_api_key
    
    @property
    def default_project_id(self):
        """
        Get the default GitLab project ID.
        
        Returns:
            str: The default GitLab project ID used for task creation when no specific project is specified
        """
        return self.__default_project_id