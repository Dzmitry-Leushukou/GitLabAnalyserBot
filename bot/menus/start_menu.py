from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_start_menu():
    start_button = KeyboardButton("Start")
    
    buttons = [[start_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)