from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

# Define states for pagination
class PaginationStates(StatesGroup):
    viewing_users = State()

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
async def command_start_handler(message: Message):
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
async def command_workers_handler(message: Message, state: FSMContext, gitlab_service=None):
    """
    This handler receives messages with `/workers` command or button click
    """
    # gitlab_service is passed from middleware
    
    if gitlab_service:
        try:
            users = gitlab_service.get_all_users()
            if users:
                # Pagination variables
                page_size = 8  # Number of users per page
                total_pages = (len(users) + page_size - 1) // page_size # Ceiling division
                current_page = 1
                
                # Store pagination state
                await state.update_data(
                    users=users,
                    current_page=current_page,
                    total_pages=total_pages,
                    page_size=page_size
                )
                await state.set_state(PaginationStates.viewing_users)
                
                # Create keyboard with user buttons for current page
                start_index = (current_page - 1) * page_size
                end_index = min(start_index + page_size, len(users))
                page_users = users[start_index:end_index]
                
                keyboard = []
                row = []
                for i, user in enumerate(page_users):
                    # Create button with user name
                    user_button = KeyboardButton(text=f"👤 {user.get('name', 'Unknown')}")
                    row.append(user_button)
                    
                    # Add row to keyboard every 2 buttons
                    if len(row) == 2:
                        keyboard.append(row)
                        row = []
                
                # Add remaining buttons if any
                if row:
                    keyboard.append(row)
                
                # Add pagination navigation buttons
                pagination_row = []
                if current_page > 1:
                    pagination_row.append(KeyboardButton(text="⬅️ Previous"))
                if current_page < total_pages:
                    pagination_row.append(KeyboardButton(text="Next ➡️"))
                
                if pagination_row:
                    keyboard.append(pagination_row)
                
                # Add back button
                keyboard.append([KeyboardButton(text="🔙 Back")])
                
                users_keyboard = ReplyKeyboardMarkup(
                    keyboard=keyboard,
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                
                await message.answer(
                    f"👥 <b>Workers Information</b>\n\n"
                    f"Page {current_page} of {total_pages}\n"
                    f"Total workers: {len(users)}",
                    reply_markup=users_keyboard
                )
            else:
                await message.answer("👥 <b>Workers Information</b>\n\nNo workers found.")
        except Exception as e:
            await message.answer(f"👥 <b>Workers Information</b>\n\nError fetching workers: {str(e)}")
    else:
        await message.answer("👥 <b>Workers Information</b>\n\nGitLab API service not configured.")

@router.message(F.text == "ℹ️ Help")
@router.message(Command("help"))
async def command_help_handler(message: Message):
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
async def command_refresh_handler(message: Message):
    """
    This handler refreshes the menu
    """
    await message.answer("🔄 <b>Menu Refreshed</b>\n\n"
                         "Use the buttons below to navigate:",
                         reply_markup=main_menu)

# Handle user selection from the user buttons
@router.message(F.text.startswith("👤 "), PaginationStates.viewing_users)
async def handle_user_selection(message: Message, state: FSMContext, gitlab_service=None):
    """
    Handle when a user clicks on a user button
    """
    selected_user_name = message.text[2:]  # Remove "👤 " prefix
    
    # Find the user details from the stored users in state
    data = await state.get_data()
    users = data.get('users', [])
    
    selected_user = next((user for user in users if user.get('name') == selected_user_name), None)
    
    if selected_user:
        user_info = f"👤 <b>{selected_user.get('name', 'Unknown')}</b>\n\n"
        
        user_info += f"<b>Basic Information:</b>\n"
        user_info += f"• Username: @{selected_user.get('username', 'N/A')}\n"
        user_info += f"• ID: {selected_user.get('id', 'N/A')}\n"
        user_info += f"• State: {selected_user.get('state', 'N/A')}\n"
        
        if selected_user.get('email'):
            user_info += f"• Email: {selected_user.get('email')}\n"
        
        if selected_user.get('job_title'):
            user_info += f"• Job Title: {selected_user.get('job_title')}\n"
        
        if selected_user.get('bio'):
            user_info += f"• Bio: {selected_user.get('bio')}\n\n"
        else:
            user_info += "\n"
        
        # Contact information
        contact_info_added = False
        if selected_user.get('skype'):
            user_info += f"• Skype: {selected_user.get('skype')}\n"
            contact_info_added = True
        
        if selected_user.get('linkedin'):
            user_info += f"• LinkedIn: {selected_user.get('linkedin')}\n"
            contact_info_added = True
        
        if selected_user.get('twitter'):
            user_info += f"• Twitter: {selected_user.get('twitter')}\n"
            contact_info_added = True
        
        if selected_user.get('website_url'):
            user_info += f"• Website URL: {selected_user.get('website_url')}\n"
            contact_info_added = True
        
        if contact_info_added:
            user_info += "\n"
        
        # Account information
        user_info += f"<b>Account Information:</b>\n"
        
        if selected_user.get('created_at'):
            user_info += f"• Created at: {selected_user.get('created_at')}\n"
        
        if selected_user.get('last_sign_in_at'):
            user_info += f"• Last sign in: {selected_user.get('last_sign_in_at')}\n"
        
        if selected_user.get('confirmed_at'):
            user_info += f"• Confirmed at: {selected_user.get('confirmed_at')}\n"
        
        if selected_user.get('last_activity_on'):
            user_info += f"• Last activity: {selected_user.get('last_activity_on')}\n"
        
        user_info += "\n"
        
        # Profile information
        profile_info_added = False
        if selected_user.get('organization'):
            user_info += f"• Organization: {selected_user.get('organization')}\n"
            profile_info_added = True
        
        if selected_user.get('location'):
            user_info += f"• Location: {selected_user.get('location')}\n"
            profile_info_added = True
        
        if selected_user.get('theme_id'):
            user_info += f"• Theme ID: {selected_user.get('theme_id')}\n"
            profile_info_added = True
        
        if selected_user.get('color_scheme_id'):
            user_info += f"• Color scheme: {selected_user.get('color_scheme_id')}\n"
            profile_info_added = True
        
        if selected_user.get('locale'):
            user_info += f"• Locale: {selected_user.get('locale')}\n"
            profile_info_added = True
        
        if selected_user.get('timezone'):
            user_info += f"• Timezone: {selected_user.get('timezone')}\n"
            profile_info_added = True
        
        if profile_info_added:
            user_info += "\n"
        
        # Permissions and settings
        user_info += f"<b>Permissions & Settings:</b>\n"
        
        if 'can_create_group' in selected_user:
            user_info += f"• Can create group: {selected_user.get('can_create_group')}\n"
        
        if 'can_create_project' in selected_user:
            user_info += f"• Can create project: {selected_user.get('can_create_project')}\n"
        
        if 'two_factor_enabled' in selected_user:
            user_info += f"• Two-factor authentication: {selected_user.get('two_factor_enabled')}\n"
        
        if 'external' in selected_user:
            user_info += f"• External: {selected_user.get('external')}\n"
        
        if 'private_profile' in selected_user:
            user_info += f"• Private profile: {selected_user.get('private_profile')}\n"
        
        # Add more fields if they exist
        if 'note' in selected_user and selected_user['note']:
            user_info += f"• Note: {selected_user['note']}\n"
        
        if 'avatar_url' in selected_user and selected_user['avatar_url']:
            user_info += f"• Avatar URL: {selected_user['avatar_url']}\n"
        
        await message.answer(user_info, reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔙 Back")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        ))
    else:
        await message.answer("User not found.", reply_markup=main_menu)
        await state.clear()

# Handle pagination buttons
@router.message(F.text == "⬅️ Previous", PaginationStates.viewing_users)
async def handle_previous_page(message: Message, state: FSMContext, gitlab_service=None):
    """
    Handle previous page button
    """
    data = await state.get_data()
    users = data.get('users', [])
    current_page = data.get('current_page', 1)
    total_pages = data.get('total_pages', 1)
    page_size = data.get('page_size', 8)
    
    new_page = current_page - 1
    if new_page < 1:
        new_page = 1
    
    # Update state with new page
    await state.update_data(current_page=new_page)
    
    # Create keyboard with user buttons for current page
    start_index = (new_page - 1) * page_size
    end_index = min(start_index + page_size, len(users))
    page_users = users[start_index:end_index]
    
    keyboard = []
    row = []
    for i, user in enumerate(page_users):
        # Create button with user name
        user_button = KeyboardButton(text=f"👤 {user.get('name', 'Unknown')}")
        row.append(user_button)
        
        # Add row to keyboard every 2 buttons
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Add remaining buttons if any
    if row:
        keyboard.append(row)
    
    # Add pagination navigation buttons
    pagination_row = []
    if new_page > 1:
        pagination_row.append(KeyboardButton(text="⬅️ Previous"))
    if new_page < total_pages:
        pagination_row.append(KeyboardButton(text="Next ➡️"))
    
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Add back button
    keyboard.append([KeyboardButton(text="🔙 Back")])
    
    users_keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"👥 <b>Workers Information</b>\n\n"
        f"Page {new_page} of {total_pages}\n"
        f"Total workers: {len(users)}",
        reply_markup=users_keyboard
    )


@router.message(F.text == "Next ➡️", PaginationStates.viewing_users)
async def handle_next_page(message: Message, state: FSMContext, gitlab_service=None):
    """
    Handle next page button
    """
    data = await state.get_data()
    users = data.get('users', [])
    current_page = data.get('current_page', 1)
    total_pages = data.get('total_pages', 1)
    page_size = data.get('page_size', 8)
    
    new_page = current_page + 1
    if new_page > total_pages:
        new_page = total_pages
    
    # Update state with new page
    await state.update_data(current_page=new_page)
    
    # Create keyboard with user buttons for current page
    start_index = (new_page - 1) * page_size
    end_index = min(start_index + page_size, len(users))
    page_users = users[start_index:end_index]
    
    keyboard = []
    row = []
    for i, user in enumerate(page_users):
        # Create button with user name
        user_button = KeyboardButton(text=f"👤 {user.get('name', 'Unknown')}")
        row.append(user_button)
        
        # Add row to keyboard every 2 buttons
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Add remaining buttons if any
    if row:
        keyboard.append(row)
    
    # Add pagination navigation buttons
    pagination_row = []
    if new_page > 1:
        pagination_row.append(KeyboardButton(text="⬅️ Previous"))
    if new_page < total_pages:
        pagination_row.append(KeyboardButton(text="Next ➡️"))
    
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Add back button
    keyboard.append([KeyboardButton(text="🔙 Back")])
    
    users_keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"👥 <b>Workers Information</b>\n\n"
        f"Page {new_page} of {total_pages}\n"
        f"Total workers: {len(users)}",
        reply_markup=users_keyboard
    )


# Handle back button
@router.message(F.text == "🔙 Back")
async def handle_back_button(message: Message, state: FSMContext):
    """
    Handle back button to return to main menu
    """
    # Clear pagination state
    await state.clear()
    await message.answer("🔙 Back to main menu", reply_markup=main_menu)

