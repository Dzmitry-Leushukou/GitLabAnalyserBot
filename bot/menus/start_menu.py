from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_start_menu():
    """
    Create and return the start menu keyboard with the initial option.
    
    This function creates a simple keyboard with a single "Start" button
    that initiates the bot interaction for new users.
    
    Returns:
        ReplyKeyboardMarkup: The start menu keyboard markup with a single "Start" button
        
    Example:
        >>> keyboard = get_start_menu()
        >>> # Returns a keyboard with a "Start" button
    """
    # Create the start button that will initiate the bot interaction
    start_button = KeyboardButton("Start")
    
    # Organize buttons in a 2D array for the keyboard markup
    buttons = [[start_button]]
    
    # Return the keyboard markup with resizing enabled for better user experience
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)