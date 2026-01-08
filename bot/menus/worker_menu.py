from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_user_detail_menu():
    """
    Create and return the user detail menu keyboard with available options.
    
    This function creates a menu with options to view user metrics or go back
    to the workers list after viewing a specific user's details.
    
    Returns:
        ReplyKeyboardMarkup: The user detail menu keyboard markup with "Metrics" and "Back to workers" buttons
        
    Example:
        >>> keyboard = get_user_detail_menu()
        >>> # Returns a keyboard with "Metrics" and "Back to workers" buttons
    """
    # Create the back button to return to the workers list
    back_button = KeyboardButton("Back to workers")
    
    # Create the metrics button to view detailed user metrics
    metrics_button = KeyboardButton("Metrics")
    
    # Organize buttons in a 2D array with metrics on top and back button below
    buttons = [ [metrics_button], [back_button]]
    
    # Return the keyboard markup with resizing enabled for better user experience
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)