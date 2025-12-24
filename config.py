from dataclasses import dataclass
from environs import Env


@dataclass
class BotConfig:
    token: str
    admin_ids: list[int]


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
            token=env.str("BOT_TOKEN"),
            admin_ids=list(map(int, env.list("ADMIN_IDS")))
        ),
        gitlab=GitLabConfig(
            url=env.str("GITLAB_URL", ""),
            token=env.str("GITLAB_TOKEN", "")
        )
    )