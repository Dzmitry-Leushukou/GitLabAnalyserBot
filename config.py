from dataclasses import dataclass
from environs import Env


@dataclass
class BotConfig:
    token: str


@dataclass
class GitLabConfig:
    url: str
    token: str


@dataclass
class Config:
    bot: BotConfig
    gitlab: GitLabConfig


def load_config() -> Config:
    env = Env()
    env.read_env()
    
    return Config(
        bot=BotConfig(
            token=env.str("BOT_TOKEN")
        ),
        gitlab=GitLabConfig(
            url=env.str("GITLAB_URL", ""),
            token=env.str("GITLAB_TOKEN", "")
        )
    )