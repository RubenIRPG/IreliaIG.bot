# IreliaIG Twitch Bot

A Twitch bot that monitors League of Legends games and posts live updates to your Twitch channel.

## Features

- **Live Game Tracking**: Detects when you start a game and posts champion compositions
- **Game End Notifications**: Posts detailed game statistics when games finish
- **Rank Monitoring**: Shows current League rank
- **Statistics Commands**: Various commands for win/loss streaks, KDA, winrate, etc.
- **Irelia Stats**: Special tracking for Irelia games
- **Anti-Spam**: Cooldowns and permission checks for commands

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the bot by editing `bot_config.ini` or setting environment variables:
- `RIOT_API_KEY`: Your Riot Games API key (get from https://developer.riotgames.com/)
- `GAME_NAME`: Your League of Legends summoner name
- `TAG_LINE`: Your Riot ID tagline (e.g., "EUW")
- `REGION`: Your region (europe, americas, asia)
- `TWITCH_TOKEN`: Your Twitch OAuth token (get from https://twitchapps.com/tmi/)
- `TWITCH_CHANNEL`: Your Twitch channel name
- `SLEEP_IN_GAME`: Seconds to wait between checks when in game (default: 25)
- `SLEEP_OUT_GAME`: Seconds to wait between checks when not in game (default: 120)

### Railway Deployment

1. **Get API Keys:**
   - **Riot API Key**: Go to https://developer.riotgames.com/ and create an application
   - **Twitch Token**: Go to https://twitchapps.com/tmi/ and generate an OAuth token

2. **Deploy to Railway:**
   - Go to [Railway.app](https://railway.com) and create a new project
   - Connect your GitHub repository (or upload files)
   - In Railway dashboard, go to Variables and set:
     ```
     RIOT_API_KEY=RGAPI-xxxxxxxxxxxxx
     GAME_NAME=YourSummonerName
     TAG_LINE=YourTagLine
     REGION=europe
     TWITCH_TOKEN=oauth:xxxxxxxxxxxxxxxxx
     TWITCH_CHANNEL=your_channel_name
     SLEEP_IN_GAME=25
     SLEEP_OUT_GAME=120
     ```

3. **Deploy**: Railway will automatically detect the Python app and deploy it. The bot will start running continuously.

### Environment Variables

- `RIOT_API_KEY` (required): Your Riot Games API key
- `GAME_NAME` (required): League summoner name
- `TAG_LINE` (required): Riot ID tagline (e.g., "EUW")
- `REGION` (optional): Region (default: europe)
- `TWITCH_TOKEN` (required): Twitch OAuth token
- `TWITCH_CHANNEL` (required): Twitch channel name
- `SLEEP_IN_GAME` (optional): Check interval when in game (default: 25)
- `SLEEP_OUT_GAME` (optional): Check interval when not in game (default: 120)

## Commands

- `!hora` - Show current time
- `!rank` - Show current League rank
- `!irelia` - Show Irelia statistics
- `!last` - Show last game result
- `!today` - Show today's session stats (24h)
- `!wins` - Show today's ranked wins
- `!losses` - Show today's ranked losses
- `!kda` - Show average KDA from last 15 games
- `!winrate` - Show winrate from last 15 games
- `!tilt` - Check current lose streak
- `!winstreak` - Show current win streak
- `!historial` - Show recent games history
- `!cmd` - List all commands

### Owner/Mod Commands

- `!apistatus` - Check API status
- `!rankrefresh` - Manually refresh rank
- `!clearcache` - Clear match cache
- `!refresh` - Rebuild match cache
- `!updatekey <key>` - Update Riot API key
- `!health` - Check bot health
- `!clearlose` - Remove most recent loss
- `!setstreak <number>` - Manually set win streak

## Automatic Messages

The bot automatically posts:
- Game start notifications with champion compositions
- Detailed game end statistics (K/D/A, KP%, damage, CS/min, etc.)
- Win/loss streak notifications
- Tilt warnings for loss streaks

## Files

- `IreliaIG.py` - Main bot code
- `bot_config.ini` - Configuration file (local only)
- `requirements.txt` - Python dependencies
- `champions.json` - Champion data cache
- `match_cache.json` - Match history cache
- `bot_persistent_stats.json` - Persistent statistics
- `irelia_data.json` - Irelia-specific stats
- `bot.log` - Bot logs

## Notes

- The bot uses Riot's API with rate limiting
- Match data is cached to reduce API calls
- Statistics are calculated from ranked Solo Queue games only
- The bot respects Twitch's message limits and includes cooldowns