from aiogram import Router

router = Router()

# Import handlers here
from . import base_handlers

router.include_router(base_handlers.router)