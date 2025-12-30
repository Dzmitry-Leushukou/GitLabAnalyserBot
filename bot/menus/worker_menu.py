from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_user_detail_menu():
    """Menu that appears after selecting a user"""
    back_button = KeyboardButton("Back to workers")
    estimate_time_button = KeyboardButton("Estimate Time")
    cycle_time_button = KeyboardButton("Cycle Time")
    buttons = [ [estimate_time_button], [cycle_time_button], [back_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)