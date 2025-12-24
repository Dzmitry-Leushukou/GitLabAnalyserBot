from dataclasses import dataclass
from environs import Env


@dataclass
class GitLabConfig:
    url: str
    token: str


def load_gitlab_config(env_path: str = ".env") -> GitLabConfig:
    """
    Load GitLab configuration from environment variables
    
    Args:
        env_path (str): Path to the environment file
        
    Returns:
        GitLabConfig: Configuration object with GitLab settings
    """
    env = Env()
    env.read_env(env_path)
    
    return GitLabConfig(
        url=env.str("GITLAB_URL", ""),
        token=env.str("GITLAB_TOKEN", "")
    )