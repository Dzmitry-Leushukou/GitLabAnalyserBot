from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    """
    Create and return the main menu keyboard with available options.
    
    Returns:
        ReplyKeyboardMarkup: The main menu keyboard markup
    """
    users_button = KeyboardButton("Workers")

    buttons = [[users_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

