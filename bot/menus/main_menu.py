from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    """
    Create and return the main menu keyboard with available options.
    
    This function creates the main menu for the bot with a "Workers" button
    that allows users to navigate to the list of GitLab users.
    
    Returns:
        ReplyKeyboardMarkup: The main menu keyboard markup with a "Workers" button
        
    Example:
        >>> keyboard = get_main_menu()
        >>> # Returns a keyboard with a "Workers" button
    """
    # Create the workers button that leads to the list of GitLab users
    users_button = KeyboardButton("Workers")

    # Organize buttons in a 2D array for the keyboard markup
    buttons = [[users_button]]
    
    # Return the keyboard markup with resizing enabled for better user experience
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

