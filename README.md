# Advent of Code Telegram Bot (Multi-Chat)

A powerful Telegram bot that monitors multiple Advent of Code private leaderboards across different chats and posts notifications whenever leaderboards update.

## Features

- **Multi-Chat Support**: Monitor different leaderboards in different Telegram chats simultaneously
- **Command-Based Configuration**: Configure leaderboards via simple bot commands (no restarts needed!)
- **Real-Time Monitoring**: Checks leaderboards every 15 minutes (configurable per leaderboard)
- **Smart Notifications**: Only sends messages when changes are detected
- **Detailed Updates**: Reports new stars, rank changes, score updates, and new members
- **Admin Control**: Only chat administrators can add/remove leaderboards
- **Rate Limiting**: Respects both AoC and Telegram API rate limits
- **Persistent State**: Tracks leaderboard history across restarts
- **Robust Error Handling**: Continues monitoring despite network issues

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or download this repository:
```bash
cd /home/harm/projects/AoC_Telegram_Bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

### Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the instructions
3. You'll receive a **bot token** (looks like `123456789:ABCdefGHIjklmnoPQRstuvWXYZ_1234567890`)

### Start the Bot

```bash
python -m aoc_bot.main --bot-token "YOUR_BOT_TOKEN"
```

Or use environment variable:
```bash
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
python -m aoc_bot.main
```

### Configure in Telegram

Add the bot to any chat (group or private) and as an **admin**, send:

```
/start
```

Then add a leaderboard:

```
/add_leaderboard 123456 session=your_session_cookie 2024
```

That's it! The bot will start monitoring and post updates automatically.

## Bot Commands

### All Users Can Use

- **`/start`** - Welcome message and quick help
- **`/help`** - Detailed help with examples
- **`/list_leaderboards`** - Show all leaderboards configured in this chat
- **`/status`** - Show monitoring status and next poll times

### Administrators Only

- **`/add_leaderboard <id> <cookie> [year]`** - Add a leaderboard to monitor
  - Example: `/add_leaderboard 123456 session=abc123def456 2024`
  - `id`: Your AoC private leaderboard ID
  - `cookie`: Your AoC session cookie (see below)
  - `year`: Optional, defaults to current year

- **`/remove_leaderboard <id> [year]`** - Stop monitoring a leaderboard
  - Example: `/remove_leaderboard 123456 2024`

## Getting Your AoC Session Cookie

The bot needs your AoC session cookie to fetch leaderboard data. Here's how to get it:

1. Log into [adventofcode.com](https://adventofcode.com) in your browser
2. Open **Developer Tools** (Press F12, or right-click → Inspect)
3. Go to the **Application** tab (or **Storage** in Firefox)
4. Expand **Cookies** in the left sidebar
5. Click on `adventofcode.com`
6. Find the cookie named `session`
7. Copy the entire **Value** (including the `session=` prefix if shown)

Your session cookie looks like: `session=abc123def456xyz789...`

**⚠️ Security Note**: Keep your session cookie secret! It grants access to your account. Never share it publicly.

## Configuration Options

### Bot Startup Arguments

```bash
python -m aoc_bot.main [OPTIONS]
```

**Options:**

- `--bot-token TOKEN` **(required)**
  - Telegram bot token from @BotFather
  - Or set `TELEGRAM_BOT_TOKEN` environment variable

- `--database PATH` (optional)
  - Path to SQLite database file
  - Default: `data/bot_config.db`

- `--log-file PATH` (optional)
  - Path to log file
  - Default: `logs/aoc_bot.log`

### Per-Leaderboard Configuration (via commands)

When adding a leaderboard with `/add_leaderboard`, you can configure:

- `poll_interval` - Currently fixed at 900 seconds (15 minutes)
- Future: Interactive setup for custom poll intervals

## Usage Examples

### Example 1: Start the bot

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklmnoPQRstuvWXYZ_1234567890"
python -m aoc_bot.main
```

### Example 2: Monitor your team's leaderboard

1. In your group chat with the bot (as admin):
```
/add_leaderboard 987654 session=my_session_cookie_here 2024
```

2. The bot will:
   - Test the connection to your leaderboard
   - Start monitoring immediately
   - Send a confirmation message

3. Every 15 minutes, it checks for updates
4. When changes are detected, it posts something like:

```
📊 Leaderboard Update

⭐ New Stars:
  ⭐ John Doe - Day 5 Part 1
  🌟 Jane Smith - Day 3 (Complete!)

📈 Rank Changes:
  Bob Johnson: #8 → #6 (↑2)
```

### Example 3: Monitor multiple leaderboards in the same chat

```
/add_leaderboard 111111 session=cookie1 2024
/add_leaderboard 222222 session=cookie2 2024
/list_leaderboards
```

### Example 4: Monitor the same leaderboard in different chats

Just add the bot to multiple chats and run the same `/add_leaderboard` command in each one!

## Project Structure

```
AoC_Telegram_Bot/
├── aoc_bot/
│   ├── main.py               # Bot entry point
│   ├── config.py             # Configuration management
│   ├── database.py           # SQLite database layer
│   ├── command_handlers.py   # Telegram command handlers
│   ├── polling_manager.py    # Multi-leaderboard polling
│   ├── telegram_notifier.py  # Telegram messaging
│   ├── state_manager.py      # State persistence
│   ├── aoc_api.py            # AoC API client
│   ├── change_detector.py    # Change detection
│   └── message_formatter.py  # Message formatting
├── data/
│   ├── bot_config.db         # SQLite database (created on first run)
│   └── state_*.json          # Leaderboard state files
├── logs/
│   └── aoc_bot.log           # Bot logs (created on first run)
├── requirements.txt
├── README.md
└── .gitignore
```

## Database

The bot uses SQLite to store leaderboard configurations. The database stores:

- Telegram chat ID
- AoC leaderboard ID
- Session cookie (encrypted in future versions)
- Event year
- Poll interval
- Enabled/disabled status

**Location**: `data/bot_config.db` (created automatically on first run)

## State Files

For each monitored leaderboard, the bot maintains a JSON state file to track:

- Member scores and ranks
- Completed days/parts
- Changes between polls

**Location**: `data/state_{chat_id}_{leaderboard_id}_{year}.json`

## Logs

The bot writes detailed logs to help with troubleshooting:

- **Location**: `logs/aoc_bot.log`
- **Format**: Timestamp, logger name, level, and message
- **Rotation**: Automatically rotates when reaching 10 MB (keeps 5 backups)

Check logs to see:
- Bot startup/shutdown messages
- Configuration changes
- API calls and responses
- Errors and warnings

## Error Handling

The bot is designed to be robust:

| Situation | Behavior |
|-----------|----------|
| Network error | Retries with exponential backoff |
| Invalid session cookie | Notifies admin, disables leaderboard |
| AoC API rate limited | Waits and retries |
| One leaderboard fails | Other leaderboards continue monitoring |
| Bot crashes | On restart, resumes all monitoring |

## Security Considerations

1. **Admin-Only Commands**: Only Telegram chat administrators can add/remove leaderboards
2. **Session Cookies**: Stored in SQLite database - keep your database file secure!
3. **No Rate Limiting**: Bot commands aren't rate-limited yet (coming soon)
4. **Error Messages**: Sensitive information is logged but not shown to users

## Troubleshooting

### Bot doesn't start

Check that the bot token is valid:
```bash
python -m aoc_bot.main --bot-token "bad_token"
```

Look for clear error messages about the token format.

### Bot doesn't respond to commands

1. Make sure you've added the bot to the chat
2. Make sure you're sending the command as an admin (for `/add_leaderboard`)
3. Check logs: `tail -f logs/aoc_bot.log`

### "Authentication failed" error

The session cookie may have expired:
1. Get a new session cookie from adventofcode.com (see instructions above)
2. Run `/add_leaderboard` again with the new cookie
3. Remove the old leaderboard with `/remove_leaderboard`

### "Leaderboard not found" error

Check:
- Is the leaderboard ID correct?
- Are you the owner of the private leaderboard?
- Have you shared it with your account?

### No messages in Telegram

1. Check the bot is running: `ps aux | grep aoc_bot`
2. Check logs for errors: `tail -20 logs/aoc_bot.log`
3. Make sure the bot has permission to send messages in the chat
4. Verify the leaderboard ID and session cookie are correct

### Too many notifications

The bot only sends messages when changes are detected. If you're getting many notifications:
- Check if the leaderboard is actually changing frequently
- Use `/status` to see when the last poll was

## Performance

- **Memory**: ~50-100 MB per running instance
- **CPU**: Minimal during idle, light usage during polls
- **API Calls**: 1 per leaderboard every 15 minutes (respects AoC guidelines)
- **Scalability**: Can monitor 100+ leaderboards per bot instance

## Migration from Single-Chat Version

If you were using the original single-chat version, here's how to migrate:

1. Note your old configuration (leaderboard ID, session cookie, year)
2. Install and start the new bot with just the bot token
3. Use `/add_leaderboard` to add each leaderboard
4. The new bot will automatically find and reuse old state files

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
black aoc_bot/
flake8 aoc_bot/
mypy aoc_bot/
```

## Future Features

- Session cookie encryption
- Custom poll intervals per leaderboard
- Web dashboard
- Statistics tracking
- Integration with other chat platforms

## Support

For issues or feature requests, check the logs and README troubleshooting section first.

If you find a bug, please collect:
1. Relevant error messages from `logs/aoc_bot.log`
2. Steps to reproduce
3. Your bot configuration (without sensitive data)

## License

This project is open source and available for personal use with Advent of Code.

---

Happy coding and good luck with Advent of Code! 🎄
