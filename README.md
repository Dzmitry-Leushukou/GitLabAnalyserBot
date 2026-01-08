# GitLab Analytics Bot

A comprehensive Telegram bot that integrates with GitLab API to provide user information, task analytics, and automated task management from GitLab instances.

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
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Development](#development)
- [GitLab API Permissions](#gitlab-api-permissions)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

This project is a Telegram bot that connects to a GitLab instance and allows users to browse GitLab users through a simple chat interface. The bot provides pagination functionality to navigate through users and displays user information in a clean, organized manner. Additionally, it can analyze task assignments, calculate time metrics for different development stages, and generate detailed reports about user activities in GitLab. The bot also features AI-powered task assignment based on natural language processing and voice message support with speech-to-text functionality.

The application is built using Python and the python-telegram-bot library, with asynchronous operations for efficient API communication. It leverages GitLab's API to fetch user data, tasks, and metrics, while also integrating with external services like LLMs and OpenAI's Whisper for advanced features.

## Features

- **GitLab Integration**: Connects to GitLab API to fetch user information, tasks, and project details
- **Telegram Interface**: Simple chat-based interface for interacting with GitLab data
- **Pagination**: Navigate through users with Next/Previous controls for large datasets
- **Responsive Menus**: Interactive keyboard menus for easy navigation
- **User Details**: Click on any user to view detailed information including name, username, and avatar
- **User Tasks**: Get all tasks where the user was an assignee with full information
- **Task History**: Access to comprehensive task history including label changes and assignee changes
- **Time Metrics**: Calculate time spent in different stages (work, review, QA) for tasks
- **Export Functionality**: Export user tasks with detailed information to JSON files
- **Configuration**: Environment-based configuration for easy setup
- **Progress Tracking**: Real-time progress updates during data fetching operations
- **AI Task Assignment**: Natural language processing for intelligent task assignment
- **Voice Recognition**: Speech-to-text functionality for voice message processing
- **LLM Integration**: Connects to external LLM services for advanced task analysis
- **Label Management**: Intelligent label suggestions based on task content
- **Real-time Status Updates**: Progress indicators during long-running operations
- **Multi-language Support**: Voice recognition for multiple languages (Russian by default)

## Prerequisites

- Python 3.8 or higher
- GitLab instance with API access
- Telegram Bot Token (obtained from @BotFather)
- LLM service endpoint (optional, for AI features)
- OpenAI API key (optional, for voice recognition features)
- GitLab personal access token with appropriate permissions

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Dzmitry-Leushukou/GitLabAnalyserBot.git
cd GitLabAnalytics
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on the `.env.example`:
```bash
cp .env.example .env
```

5. Configure the environment variables (see Configuration section below)

6. Verify your installation:
```bash
python -c "import telegram; print('Telegram bot library installed successfully')"
python -c "import gitlab; print('GitLab library installed successfully')"
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

# LLM Service Configuration (optional)
LLM_URL=your-llm-service-url
CREATE_TASK_LLM_API_KEY=your-create-task-llm-api-key
GET_LABELS_LLM_API_KEY=your-get-labels-llm-api-key

# Whisper Service Configuration (optional)
WHISPER_API_KEY=your-openai-api-key
DEFAULT_PROJECT_ID=your-default-project-id
```

### Configuration Details

- `PAGE_SIZE`: Number of users to display per page (default: 4)
- `PROGRESS_STEP`: Interval for progress updates during task processing (default: 10)
- `TELEGRAM_TOKEN`: Your Telegram bot token (obtained from @BotFather)
- `GITLAB_URL`: URL of your GitLab instance (e.g., https://gitlab.com)
- `GITLAB_TOKEN`: GitLab personal access token with appropriate permissions
- `LLM_URL`: URL of your LLM service endpoint (optional, for AI features)
- `CREATE_TASK_LLM_API_KEY`: API key for creating tasks via LLM service (optional)
- `GET_LABELS_LLM_API_KEY`: API key for getting labels via LLM service (optional)
- `WHISPER_API_KEY`: OpenAI API key for voice recognition (optional, for voice features)
- `DEFAULT_PROJECT_ID`: Default GitLab project ID for task creation

## Usage

1. Make sure your configuration is properly set in the `.env` file
2. Run the bot:
```bash
python bot/main.py
```

3. Start the bot in Telegram by sending `/start` command
4. Use the interactive menus to navigate through GitLab users

### Basic Usage Flow

1. **Start the Bot**: Send `/start` command to initialize the bot
2. **Navigate to Users**: Click "Start" then "Workers" to view GitLab users
3. **Browse Users**: Use "Next" and "Previous" buttons to navigate through user pages
4. **Select User**: Tap on any user name to view detailed information
5. **View Metrics**: Click "Metrics" to get all tasks and time metrics for the selected user
6. **Export Data**: The bot will generate a JSON file with detailed metrics
7. **Create Tasks**: Send natural language messages to create GitLab tasks automatically

## Bot Commands

- `/start` - Initialize the bot and show the start menu

## Bot Features

After selecting a user, you can access additional functionality:
- **View User Tasks**: Get all tasks where the selected user was an assignee
- **Task History**: View comprehensive history of label changes and assignee changes for each task
- **Time Metrics**: Calculate and view time spent in different development stages (work, review, QA)
- **Export Data**: Export user tasks with detailed information and metrics to JSON files
- **AI Task Creation**: Send natural language messages to create GitLab tasks automatically assigned to appropriate users
- **Voice Commands**: Support for voice messages that are converted to text and processed as commands
- **Progress Tracking**: Real-time progress updates during data fetching operations

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
- **AI Task Creation**: Send natural language messages to create GitLab tasks automatically assigned to appropriate users
- **Voice Recognition**: Send voice messages that will be transcribed and processed as commands

### Navigation Controls

- **Next**: Go to the next page of users
- **Previous**: Go to the previous page of users
- **Back**: Return to the Main menu
- **Main menu**: Return to the main menu from any point

## API Reference

The GitLab Analytics Bot exposes several services that can be used programmatically:

### GitLabService API

The GitLabService handles all communication with the GitLab API:

- `get_users(page: int) -> List[Dict]`: Retrieve a paginated list of GitLab users
- `get_user(user_id: int) -> Dict`: Get detailed information about a specific user
- `get_all_historical_user_assignments(user_id: int, username: str, progress_callback=None) -> List[Dict]`: Get all tasks where the user is involved
- `get_user_metrics(user_id: int, username: str, progress_callback=None) -> List[Dict]`: Get metrics for all tasks assigned to a user
- `create_new_task(project_id: int, task_name: str, task_description: str, assignee_id: int, labels: List[str]) -> Dict`: Create a new task in GitLab
- `get_user_id_by_name(user_name: str) -> Optional[int]`: Find GitLab user ID by name
- `get_labels_from_project_id(project_id: int) -> List[Dict]`: Get all labels from a GitLab project

### LLMService API

The LLMService handles communication with external LLM services:

- `process_task_assignment(workers: List[str], user_message: str) -> Dict[str, str]`: Process assignment and return structured data
- `set_labels(labels: List[Dict[str, str]], user_message: str) -> Dict[str, str]`: Set appropriate labels for a task based on user message

### WhisperService API

The WhisperService handles voice message transcription:

- `transcribe_audio_file(audio_path: str, language: Optional[str] = "ru") -> Dict[str, Any]`: Transcribe an audio file
- `transcribe_telegram_voice(voice_bytes: bytes, language: Optional[str] = "ru") -> Dict[str, Any]`: Transcribe a voice message from Telegram
- `is_available() -> bool`: Check if the Whisper service is available

## Project Structure

```
GitLabAnalytics/
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore rules
├── README.md            # Project documentation
├── requirements.txt     # Python dependencies
├── bot/                 # Telegram bot implementation
│   ├── __init__.py      # Package initialization
│   ├── config.py        # Bot configuration
│   ├── handler.py       # Message and command handlers
│   ├── main.py          # Bot entry point
│   └── menus/           # Keyboard menu definitions
│       ├── __init__.py  # Package initialization
│       ├── start_menu.py # Start menu implementation
│       ├── main_menu.py # Main menu implementation
│       ├── workers_menu.py # Workers menu implementation
│       ├── worker_menu.py # Worker detail menu implementation
│       └── workers_menu.py # Workers menu implementation (duplicate - may be removed)
└── services/            # External service integrations
    ├── __init__.py      # Package initialization
    ├── config.py        # Service configuration
    ├── GitLabService.py # GitLab API integration
    ├── LLMService.py    # LLM service integration
    └── WhisperService.py # Whisper service integration
```

## Dependencies

- `python-telegram-bot>=20.0` - Telegram Bot API framework
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests library
- `python-gitlab` - GitLab API client library
- `aiohttp` - Asynchronous HTTP client/server framework
- `openai>=1.0.0` - OpenAI API client library (for voice recognition)
- `pydub>=0.25.1` - Audio manipulation library (for voice processing)
- `ffmpeg-python>=0.2.0` - FFmpeg wrapper for audio processing
- `asyncio` - Asynchronous programming library

## Development

To run the bot in development mode:

1. Ensure all dependencies are installed
2. Configure your `.env` file properly
3. Run the main script:
```bash
python3 -m bot.main
```

### Development Commands

- **Run the bot**: `python bot/main.py`
- **Install dependencies**: `pip install -r requirements.txt`
- **Check code formatting**: `python -m black .` (if black is installed)
- **Run tests**: `python -m pytest` (if tests exist)

### Environment Setup

For development, you may want to set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## GitLab API Permissions

The GitLab token should have sufficient permissions to read user information, issues, and project details. Typically, the following scopes are required for accessing user data, issues, and labels:

- `read_user` - Read user information
- `read_api` - Access to API endpoints
- `read_repository` - Access to repository information
- `api` - Full API access (for creating tasks and managing labels)

For comprehensive access to all features of the bot, ensure your personal access token has appropriate scopes. The token should be created with the minimum required permissions for security.

To create a GitLab personal access token:

1. Go to your GitLab profile settings
2. Navigate to "Access Tokens"
3. Create a new token with appropriate scopes
4. Copy the token and add it to your `.env` file as `GITLAB_TOKEN`

## Troubleshooting

### Common Issues

**Bot doesn't start**
- Check that your `TELEGRAM_TOKEN` is correctly set in the `.env` file
- Verify that the token format is correct (should contain colons)
- Ensure all dependencies are installed

**GitLab API access errors**
- Verify that your `GITLAB_TOKEN` has the required permissions
- Check that `GITLAB_URL` is correctly formatted (e.g., https://gitlab.com)
- Ensure the GitLab instance is accessible from your network

**Voice recognition not working**
- Verify that `WHISPER_API_KEY` is correctly set
- Check that your OpenAI account has sufficient credits
- Ensure the Whisper service is available and properly configured

**AI features not working**
- Verify that LLM service URLs and API keys are correctly configured
- Check that the LLM service is running and accessible
- Ensure network connectivity to the LLM service endpoint

**Task creation fails**
- Verify that the project ID exists and is accessible
- Check that the user has permissions to create issues in the project
- Ensure all required fields are provided when creating tasks

### Logging and Debugging

The application uses Python's logging module for debugging. To enable more detailed logging:

1. Modify the logging level in `bot/main.py` or `services/GitLabService.py`
2. Look for log files or console output for error messages
3. Check the specific service logs for detailed error information

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
- Add unit tests for new functionality where appropriate
- Follow Python PEP 8 style guidelines
