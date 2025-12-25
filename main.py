import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from config import load_config
from handlers import router
from services.gitlab_api_service.service import GitLabApiService


class GitLabServiceMiddleware(BaseMiddleware):
    def __init__(self, gitlab_service):
        self.gitlab_service = gitlab_service
        super().__init__()

    async def __call__(self, handler, event, data):
        data["gitlab_service"] = self.gitlab_service
        return await handler(event, data)


async def main():
    logging.basicConfig(level=logging.INFO)
    
    config = load_config()
    
    # Initialize GitLab API service
    gitlab_config = config.gitlab
    
    if gitlab_config.url and gitlab_config.token:
        gitlab_service = GitLabApiService(gitlab_config.url, gitlab_config.token)
        # You can now use gitlab_service in your handlers
        print("✅ GitLab API service initialized")
    else:
        print("⚠️  GitLab API service not configured")
        gitlab_service = None
    
    bot = Bot(token=config.bot.token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Add middleware to pass gitlab_service to handlers
    if gitlab_service:
        dp.message.middleware(GitLabServiceMiddleware(gitlab_service))
    
    dp.include_router(router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())