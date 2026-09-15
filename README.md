# Discord Honeypot Bot

A lightweight Discord bot that automatically kicks users who post image or file attachments in configured honeypot channels.

## Features

- Automatic kick for image/file attachments in honeypot channels
- Admin configuration panel with `/honeypot` command
- Exemption system for specific users, roles, or bots
- Trigger logging with recent activity view
- Persistent settings via SQLite database

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a Discord Application**
   - Go to https://discord.com/developers/applications
   - Create a new application and bot
   - Copy the bot token

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your bot token
   ```

4. **Invite the bot**
   Use this OAuth2 URL (replace YOUR_CLIENT_ID):
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=268468736&scope=bot%20applications.commands
   ```
   Required permissions: Manage Messages, Kick Members, Send Messages, Read Message History

5. **Run the bot**
   ```bash
   python main.py
   ```

## Environment Variables

| Variable | Description | Required |
|--------|-------------|----------|
| `BOT_TOKEN` | Your Discord bot token | Yes |
| `DB_PATH` | Path to SQLite database file | No (default: honeypot.db) |

## Commands

- `/honeypot` - Open configuration panel
- `/honeypot_configure` - Set honeypot channel
- `/honeypot_disable` - Disable honeypot
- `/honeypot_status` - View current status
- `/honeypot_exempt` - Add exemption
- `/honeypot_exemptions` - List exemptions
- `/honeypot_triggers` - View recent triggers
