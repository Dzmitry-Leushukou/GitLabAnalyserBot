# GitLab Analytics Bot

A Telegram bot that provides analytics and information about GitLab users and projects.

## Features

- Fetch and display GitLab users information
- Provides worker analytics through a Telegram interface
- Easy to deploy with Docker

## Setup

1. Create a `.env` file based on `.env.example`
2. Set your GitLab URL and Personal Access Token
3. Run the application using Docker

## Configuration

The bot requires the following environment variables:
- `GITLAB_URL`: Your GitLab instance URL
- `GITLAB_TOKEN`: Personal Access Token with appropriate permissions
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token

## Running the Bot

You can run the bot using Docker Compose:

```
docker-compose up
```

## License

This project is licensed under the MIT License.