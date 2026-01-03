from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_start_menu():
    """
    Create and return the start menu keyboard with the initial option.
    
    Returns:
        ReplyKeyboardMarkup: The start menu keyboard markup
    """
    start_button = KeyboardButton("Start")
    
    buttons = [[start_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)