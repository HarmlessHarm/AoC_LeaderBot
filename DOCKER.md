# Running the Bot with Docker

This guide explains how to run the Advent of Code Telegram Bot on a VPS using Docker.

## Prerequisites

- Docker installed on your VPS
- Docker Compose installed on your VPS
- Your Telegram bot token

## Quick Start

### 1. Clone or Download the Project

```bash
git clone <your-repo-url> aoc-bot
cd aoc-bot
```

### 2. Create Environment File

Create a `.env` file in the project root with your bot token:

```bash
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
EOF
```

### 3. Build and Start the Bot

```bash
docker-compose up -d
```

This will:
- Build the Docker image
- Start the container
- Keep it running in the background
- Auto-restart if it crashes

### 4. Verify It's Running

```bash
docker-compose logs -f
```

You should see the startup logs. Press Ctrl+C to exit the logs.

## Common Commands

### Stop the Bot

```bash
docker-compose down
```

### View Logs

```bash
# Latest logs
docker-compose logs -f

# Last 50 lines
docker-compose logs --tail 50

# Specific number of lines
docker-compose logs --tail 100 -f
```

### Restart the Bot

```bash
docker-compose restart
```

### Rebuild the Image

If you make code changes:

```bash
docker-compose up -d --build
```

### Check Running Containers

```bash
docker ps
```

You should see `aoc-telegram-bot` in the list.

## Data Persistence

The bot stores data in two locations (automatically mounted as volumes):

- **`./data/`** - SQLite database and state files
- **`./logs/`** - Log files

These directories are persisted on your VPS, so data survives container restarts.

## Configuration on VPS

### Using a .env File

The bot reads the `TELEGRAM_BOT_TOKEN` from the `.env` file in the project directory. Docker Compose automatically loads it.

### Custom Database Path

To customize the database path, add to your `.env`:

```bash
DATABASE_PATH=data/bot_config.db
```

### Custom Log Path

To customize the log path, add to your `.env`:

```bash
LOG_FILE=logs/aoc_bot.log
```

## Updating the Bot

To update to a new version:

```bash
git pull
docker-compose up -d --build
```

## Resource Usage

The bot is lightweight:
- **CPU**: Minimal (polls every 15 minutes)
- **Memory**: ~100-150 MB
- **Disk**: Database grows slowly (~1-5 MB)

The docker-compose file includes commented-out resource limits. Uncomment if desired:

```yaml
deploy:
  resources:
    limits:
      memory: 256M
```

## Troubleshooting

### Bot won't start

Check the logs:
```bash
docker-compose logs
```

Look for error messages about the bot token or database.

### Permission denied errors

Ensure the `data/` and `logs/` directories are readable/writable:

```bash
chmod 755 data logs
```

### Cannot connect to Telegram

- Verify your bot token is correct
- Check your VPS has internet access
- Check that Telegram API isn't blocked in your region

### Database locked errors

The SQLite database is being accessed by multiple processes. This shouldn't happen, but if it does:

```bash
docker-compose restart
```

## Production Deployment

For a production VPS:

1. **Use systemd** to keep Docker running:
   ```bash
   sudo systemctl restart docker
   sudo systemctl enable docker
   ```

2. **Monitor logs** with:
   ```bash
   docker-compose logs -f > bot.log &
   ```

3. **Set up log rotation** in docker-compose.yml (already configured):
   - Logs are automatically rotated at 10MB
   - Keeps 3 backup files

4. **Regular backups** of the `data/` directory:
   ```bash
   tar -czf backup-$(date +%Y%m%d).tar.gz data/
   ```

## Example Full Setup

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Clone the bot
git clone <your-repo> aoc-bot
cd aoc-bot

# Create .env with your token
echo "TELEGRAM_BOT_TOKEN=your_token_here" > .env

# Start the bot
docker-compose up -d

# Verify it's running
docker-compose logs -f
```

That's it! Your bot is now running on your VPS.
