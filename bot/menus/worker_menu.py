from telegram import ReplyKeyboardMarkup, KeyboardButton
from services.GitLabService import GitLabService

def get_worker_menu(page=1):
    gitlab_service = GitLabService()
    users = gitlab_service.get_users(page)
    
    if not users:
        back_button = KeyboardButton("Back")
        buttons = [[back_button]]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    buttons = []
    for user in users:
        # Create a button for each user with their name
        user_button = KeyboardButton(f"{user.get('name', user.get('username', 'Unknown'))}")
        estimated_time_button = KeyboardButton("Estimated Time")
        buttons.append([user_button, estimated_time_button])
    
    controls_row = []
    if page > 1:
        prev_button = KeyboardButton("Previous")
        controls_row.append(prev_button)
    
    next_users = gitlab_service.get_users(page + 1)
    if next_users:
        next_button = KeyboardButton("Next")
        controls_row.append(next_button)
    
    back_button = KeyboardButton("Main menu")
    controls_row.append(back_button)
    buttons.append(controls_row)
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_user_detail_menu():
    """Menu that appears after selecting a user"""
    back_button = KeyboardButton("Back")
    estimate_time_button = KeyboardButton("Estimate time")
    buttons = [[estimate_time_button],[back_button]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)