from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_user_detail_menu():
    """
    Create and return the user detail menu keyboard with available options.
    
    Returns:
        ReplyKeyboardMarkup: The user detail menu keyboard markup
    """
    back_button = KeyboardButton("Back to workers")
    metrics_button = KeyboardButton("Metrics")
    buttons = [ [metrics_button], [back_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)