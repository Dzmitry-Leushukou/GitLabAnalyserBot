from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

router = Router()

# Create main menu keyboard
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Workers"),
        KeyboardButton(text="ℹ️ Help"), KeyboardButton(text="🔄 Refresh")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
    """
    This handler receives messages with `/start` command
    """
    await message.answer(
        f"Hello, {message.from_user.full_name}!\n\n"
        "Welcome to the GitLab Analytics Bot. Use the menu below to navigate:",
        reply_markup=main_menu
    )

@router.message(F.text == "👥 Workers")
@router.message(Command("workers"))
async def command_workers_handler(message: Message, gitlab_service=None):
    """
    This handler receives messages with `/workers` command or button click
    """
    # gitlab_service is passed from middleware
    
    if gitlab_service:
        try:
            users = gitlab_service.get_all_users()
            if users:
                response_text = f"👥 <b>Workers Information</b>\n\n"
                response_text += f"Total workers: {len(users)}\n\n"
                
                # Show first 10 users
                for i, user in enumerate(users[:10]):
                    response_text += f"{i+1}. {user.get('name', 'Unknown')} (@{user.get('username', 'unknown')})\n"
                
                if len(users) > 10:
                    response_text += f"\n... and {len(users) - 10} more users"
            else:
                response_text = "👥 <b>Workers Information</b>\n\nNo workers found."
        except Exception as e:
            response_text = f"👥 <b>Workers Information</b>\n\nError fetching workers: {str(e)}"
    else:
        response_text = "👥 <b>Workers Information</b>\n\nGitLab API service not configured."
    
    await message.answer(response_text)

@router.message(F.text == "ℹ️ Help")
@router.message(Command("help"))
async def command_help_handler(message: Message, state: FSMContext):
    """
    This handler receives messages with `/help` command or button click
    """
    await message.answer("ℹ️ <b>Help</b>\n\n"
                         "I'm a GitLab Analytics Telegram bot.\n\n"
                         "Available commands:\n"
                         "• /start - Start the bot\n"
                         "• /workers - Show workers information\n"
                         "• /help - Show this help message\n\n"
                         "You can also use the buttons below for quick access.")

@router.message(F.text == "🔄 Refresh")
async def command_refresh_handler(message: Message, state: FSMContext):
    """
    This handler refreshes the menu
    """
    await message.answer("🔄 <b>Menu Refreshed</b>\n\n"
                         "Use the buttons below to navigate:",
                         reply_markup=main_menu)

