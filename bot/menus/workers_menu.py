from telegram import ReplyKeyboardMarkup, KeyboardButton

async def get_workers_menu(gitlab_service, page=1):
    """
    Create and return the workers menu keyboard with paginated user list.
    
    This function generates a keyboard with GitLab users for the current page,
    along with navigation controls for pagination and returning to the main menu.
    
    Args:
        gitlab_service: The GitLab service instance to fetch users
        page: The page number for pagination (default: 1)
        
    Returns:
        ReplyKeyboardMarkup: The workers menu keyboard markup with user buttons and navigation controls
        
    Example:
        >>> keyboard = await get_workers_menu(gitlab_service, 1)
        >>> # Returns a keyboard with users from page 1 and navigation controls
    """
    # Fetch users for the current page
    users = await gitlab_service.get_users(page)
    
    # If no users found, return a menu with just the back button
    if not users:
        back_button = KeyboardButton("Main menu")
        buttons = [[back_button]]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    # Create buttons for each user
    buttons = []
    for user in users:
        # Create a button for each user with their name, falling back to username if name is not available
        user_button = KeyboardButton(f"{user.get('name', user.get('username', 'Unknown'))}")
        buttons.append([user_button])
    
    # Create navigation controls row
    controls_row = []
    
    # Add previous button if not on the first page
    if page > 1:
        prev_button = KeyboardButton("Previous")
        controls_row.append(prev_button)
    
    # Check if there are more users on the next page
    next_users = await gitlab_service.get_users(page + 1)
    if next_users:
        next_button = KeyboardButton("Next")
        controls_row.append(next_button)
    
    # Add back to main menu button
    back_button = KeyboardButton("Main menu")
    controls_row.append(back_button)
    
    # Add the controls row to the buttons array
    buttons.append(controls_row)
    
    # Return the keyboard markup with resizing enabled for better user experience
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)