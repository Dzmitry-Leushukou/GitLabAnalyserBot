from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    users_button = KeyboardButton("Workers")

    buttons = [[users_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

