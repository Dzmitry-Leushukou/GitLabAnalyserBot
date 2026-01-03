# GitLab Analytics Bot

A Telegram bot that integrates with GitLab API to provide user information and analytics from GitLab instances.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Bot Commands](#bot-commands)
- [Bot Features](#bot-features)
- [Bot Interface](#bot-interface)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Development](#development)
- [GitLab API Permissions](#gitlab-api-permissions)
- [Contributing](#contributing)

## Overview

This project is a Telegram bot that connects to a GitLab instance and allows users to browse GitLab users through a simple chat interface. The bot provides pagination functionality to navigate through users and displays user information in a clean, organized manner. Additionally, it can analyze task assignments, calculate time metrics for different development stages, and generate detailed reports about user activities in GitLab.

## Features

- **GitLab Integration**: Connects to GitLab API to fetch user information
- **Telegram Interface**: Simple chat-based interface for interacting with GitLab data
- **Pagination**: Navigate through users with Next/Previous controls
- **Responsive Menus**: Interactive keyboard menus for easy navigation
- **User Details**: Click on any user to view detailed information including name, username, and avatar
- **User Tasks**: Get all tasks where the user was an assignee with full information
- **Task History**: Access to comprehensive task history including label changes and assignee changes
- **Time Metrics**: Calculate time spent in different stages (work, review, QA) for tasks
- **Export Functionality**: Export user tasks with detailed information to JSON files
- **Configuration**: Environment-based configuration for easy setup
- **Progress Tracking**: Real-time progress updates during data fetching operations

## Prerequisites

- Python 3.8 or higher
- GitLab instance with API access
- Telegram Bot Token

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Dzmitry-Leushukou/GitLabAnalyserBot.git
cd GitLabAnalytics
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the `.env.example`:
```bash
cp .env.example .env
```

## Configuration

Edit the `.env` file with your specific configuration:

```env
# Bot Configuration
PAGE_SIZE=4
PROGRESS_STEP=10

# Telegram Configuration
TELEGRAM_TOKEN=your-telegram-bot-token

# GitLab Configuration
GITLAB_URL=your-gitlab-instance-url
GITLAB_TOKEN=your-gitlab-api-token
```

### Configuration Details

- `PAGE_SIZE`: Number of users to display per page (default: 4)
- `PROGRESS_STEP`: Interval for progress updates during task processing (default: 10)
- `TELEGRAM_TOKEN`: Your Telegram bot token (obtained from @BotFather)
- `GITLAB_URL`: URL of your GitLab instance (e.g., https://gitlab.com)
- `GITLAB_TOKEN`: GitLab personal access token with appropriate permissions

## Usage

1. Make sure your configuration is properly set in the `.env` file
2. Run the bot:
```bash
python bot/main.py
```

2. Start the bot in Telegram by sending `/start` command
3. Use the interactive menus to navigate through GitLab users
## Bot Commands

- `/start` - Initialize the bot and show the start menu

## Bot Features

After selecting a user, you can access additional functionality:
- **View User Tasks**: Get all tasks where the selected user was an assignee
- **Task History**: View comprehensive history of label changes and assignee changes for each task
- **Time Metrics**: Calculate and view time spent in different development stages (work, review, QA)
- **Export Data**: Export user tasks with detailed information and metrics to JSON files



## Bot Interface

The bot provides a menu-based interface:

1. **Start Menu**: Initial menu with a "Start" button
2. **Main menu**: Access to "Workers" (users) section
3. **Workers Menu**: Paginated list of GitLab users with navigation controls
### User Interaction
The bot allows users to interact with GitLab user data:
- **User Selection**: Tap on any user name to view detailed information
- **User Details**: Displays name, username, and avatar URL for selected users
- **User Tasks**: After selecting a user, tap "Metrics" to get all tasks where the user was an assignee and calculate time metrics
- **Task Information**: Detailed information about each task including title, state, creation/update dates, labels, author, assignee, and label change history
- **Time Metrics**: Calculate and display time spent in different development stages (work, review, QA)
- **Export**: Export user tasks with detailed information and metrics to a JSON file


### Navigation Controls

- **Next**: Go to the next page of users
- **Previous**: Go to the previous page of users
- **Back**: Return to the Main menu

## Project Structure

```
GitLabAnalytics/
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
├── bot/                 # Telegram bot implementation
│   ├── __init__.py      # Package initialization
│   ├── config.py        # Bot configuration
│   ├── handler.py       # Message and command handlers
│   ├── main.py          # Bot entry point
│   └── menus/           # Keyboard menu definitions
│       ├── __init__.py
│       ├── start_menu.py
│       ├── main_menu.py
│       └── workers_menu.py
└── services/            # External service integrations
    ├── __init__.py      # Package initialization
    ├── config.py        # Service configuration
    └── GitLabService.py # GitLab API integration
```
## Dependencies

- `python-telegram-bot>=20.0` - Telegram Bot API framework
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests library
- `python-gitlab` - GitLab API client library
- `aiohttp` - Asynchronous HTTP client/server framework


## Development

To run the bot in development mode:

1. Ensure all dependencies are installed
2. Configure your `.env` file properly
3. Run the main script:
```bash
python3 -m bot.main
```
## GitLab API Permissions

The GitLab token should have sufficient permissions to read user information, issues, and project details. Typically, a "read_user", "read_api", and "read_repository" scopes are required for accessing user data, issues, and labels. For comprehensive access to all features of the bot, ensure your personal access token has appropriate scopes.

## Contributing

We welcome contributions to the GitLab Analytics Bot! Here's how you can help:

1. Fork the repository
2. Create a feature branch for your changes
3. Add your changes with appropriate documentation and tests
4. Submit a pull request with a clear description of your changes

When contributing, please follow these guidelines:
- Write clear, concise commit messages
- Add docstrings to any new functions or classes
- Maintain consistent code style with the existing codebase
- Update the README if your changes affect the user experience
- Ensure all functionality works as expected before submitting


1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

