from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_user_detail_menu():
    """Menu that appears after selecting a user"""
    back_button = KeyboardButton("Back to workers")
    metrics_button = KeyboardButton("Metrics")
    buttons = [ [metrics_button], [back_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)