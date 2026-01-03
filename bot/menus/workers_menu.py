from telegram import ReplyKeyboardMarkup, KeyboardButton

async def get_workers_menu(gitlab_service, page=1):
    """
    Create and return the workers menu keyboard with paginated user list.
    
    Args:
        gitlab_service: The GitLab service instance to fetch users
        page: The page number for pagination (default: 1)
        
    Returns:
        ReplyKeyboardMarkup: The workers menu keyboard markup
    """
    users = await gitlab_service.get_users(page)
    
    if not users:
        back_button = KeyboardButton("Main menu")
        buttons = [[back_button]]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    buttons = []
    for user in users:
        # Create a button for each user with their name
        user_button = KeyboardButton(f"{user.get('name', user.get('username', 'Unknown'))}")
        buttons.append([user_button])
    
    controls_row = []
    if page > 1:
        prev_button = KeyboardButton("Previous")
        controls_row.append(prev_button)
    
    next_users = await gitlab_service.get_users(page + 1)
    if next_users:
        next_button = KeyboardButton("Next")
        controls_row.append(next_button)
    
    back_button = KeyboardButton("Main menu")
    controls_row.append(back_button)
    buttons.append(controls_row)
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)