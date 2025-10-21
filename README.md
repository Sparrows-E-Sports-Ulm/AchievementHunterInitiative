# 🏆 Achievement Hunter Initiative Bot

<p align="center">
  <img src="https://img.shields.io/badge/discord.py-2.6.3-blue.svg" alt="discord.py">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License">
</p>

A Discord bot that tracks and ranks Steam achievement hunters! Compete with friends, climb the leaderboard, and play achievement quiz minigames.

## 📋 Table of Contents

- [Features](#-features)
- [Commands](#-commands)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Steam API Setup](#-steam-api-setup)
- [Custom Emojis Setup](#-custom-emojis-setup)
- [Usage](#-usage)
- [Database](#-database)
- [Docker Support](#-docker-support)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

- **Achievement Tracking**: Automatically tracks Steam achievements and calculates scores
- **Smart Scoring System**: Rare achievements are worth more points (100 - global_percent)
- **Leaderboard**: Global rankings by score or total achievements
- **Achievement Quiz**: Interactive quiz game with multiple rounds

## 🤖 Commands

### Registration & Setup
- `/register <steam_id>` - Register as an Achievement Hunter
- `/verify_steam` - Link your Discord account with Steam (OAuth2)
- `/update` - Manually update your achievement score

### Leaderboard & Stats
- `/leaderboard [category] [page]` - View the global leaderboard
  - Categories: `score` (default), `achievements`
  - Paginated results with navigation
- `/rank [steam_id] [category]` - View rank with surrounding players
- `/hunter <steam_id>` - View detailed hunter profile

### Performance & Queue
- `/performance <steam_id>` - View score changes and updates
- `/queue_status` - Check the update queue status

### Minigames
- `/achievement-quiz [rounds]` - Start an Achievement Quiz game
  - Default: 3 rounds
  - Range: 1-10 rounds
  - Creates a dedicated thread for the game

### Owner Only
- `/load <extension>` - Load a cog
- `/unload <extension>` - Unload a cog
- `/reload <extension>` - Reload a cog
- `/shutdown` - Safely shutdown the bot

## 🚀 Installation

### Prerequisites
- Python 3.12 or higher
- A Discord Bot Token
- Steam Web API Key
- Git (optional)

### Step 1: Clone the Repository

```bash
git clone https://github.com/AllRoundJonU/AchievementHunterInitiativeBot.git
cd AchievementHunterInitiativeBot
```

### Step 2: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Rename `.env.example` to `.env` and fill in your values:

```env
# Discord Bot Configuration
TOKEN=your_discord_bot_token
PREFIX=!
INVITE_LINK=your_bot_invite_link

# Discord OAuth2 (Optional - for /verify_steam)
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
DISCORD_REDIRECT_URI=http://localhost:8080/callback
OAUTH2_PORT=8080

# Steam API
STEAM_API_KEY=your_steam_api_key

# Bot Owner
OWNER_IDS=your_discord_id,another_owner_id
```

### Step 4: Run the Bot

```bash
python bot.py
```

## ⚙️ Configuration

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the token and paste it in your `.env` file
5. Enable the following **Privileged Gateway Intents**:
   - Server Members Intent (optional)
   - Message Content Intent (if using prefix commands)

### Bot Permissions

The bot requires the following permissions:
- `Read Messages/View Channels`
- `Send Messages`
- `Embed Links`
- `Attach Files`
- `Read Message History`
- `Add Reactions`
- `Create Public Threads`
- `Send Messages in Threads`
- `Use Application Commands`

**Invite Link Template:**
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=414464736320&scope=bot%20applications.commands
```

## 🎮 Steam API Setup

### Get Your Steam API Key

1. Go to [Steam Web API Key](https://steamcommunity.com/dev/apikey)
2. Register for an API key
3. Copy the key and paste it in your `.env` file as `STEAM_API_KEY`

### Steam Profile Privacy

For the bot to track achievements, Steam profiles must be **public**. Users with private profiles will receive an error when trying to register or update.

**To make your profile public:**
1. Go to Steam → Edit Profile → Privacy Settings
2. Set "Game details" to **Public**

## 🎨 Custom Emojis Setup

The bot uses custom 2x2 grid emojis for displaying numbers in ranks. These are **Application Emojis** (not server emojis).

### Option 1: Use Existing Emojis

If you already have custom number emojis uploaded, update `achhi-data/emoji_ids.json` with your emoji IDs:

```json
{
  "0": {
    "TL": "your_emoji_id",
    "TR": "your_emoji_id",
    "BL": "your_emoji_id",
    "BR": "your_emoji_id"
  },
  ...
}
```

### Option 2: Upload New Emojis

1. Create your digit images (0-9) as PNG files (256x256px recommended)
2. Place them in `achhi-data/emoji-processing/` as `0.png`, `1.png`, etc.
3. Edit `achhi-data/upload_emojis.sh`:
   ```bash
   DISCORD_TOKEN="your_bot_token"
   APPLICATION_ID="your_application_id"
   ```
4. Run the script (requires ImageMagick and jq):
   ```bash
   cd achhi-data
   chmod +x upload_emojis.sh
   ./upload_emojis.sh
   ```

The script will:
- Resize images to 256x256px
- Split each into 4 quadrants (TL, TR, BL, BR)
- Upload as Discord application emojis
- Generate `emoji_ids.json` automatically

### Requirements for Upload Script
- **ImageMagick**: `sudo apt install imagemagick` (Linux) or `brew install imagemagick` (Mac)
- **jq**: `sudo apt install jq` (Linux) or `brew install jq` (Mac)
- **curl** and **base64** (usually pre-installed)

## 📖 Usage

### For Users

1. **Register**: Use `/register <your_steam_id>` to join the Achievement Hunter Initiative
2. **Update**: Use `/update` to refresh your achievement score
3. **Check Rank**: Use `/rank` to see your position on the leaderboard
4. **View Leaderboard**: Use `/leaderboard` to see the top hunters
5. **Play Minigames**: Use `/achievement-quiz` to start a fun quiz game

### For Server Admins

- The bot automatically updates all registered hunters periodically
- Use `/queue_status` to monitor the update queue
- Locked hunters (via database flag) won't be updated automatically

### Score Calculation

The bot calculates scores based on achievement rarity:

```
Score per achievement = 100 - global_achievement_percentage
```

**Example:**
- Achievement with 5% global completion = 95 points
- Achievement with 50% global completion = 50 points
- Achievement with 90% global completion = 10 points

Rarer achievements are worth more points!

## 🗄️ Database

The bot uses SQLite for data storage. The database is automatically created on first run.

### Schema

**hunters** table:
- `steam_id` (PRIMARY KEY) - Steam ID64
- `steam_name` - Steam display name
- `discord_id` - Linked Discord user ID (optional)
- `score` - Total achievement score
- `total_achievements` - Total unlocked achievements
- `total_games` - Total owned games
- `last_updated` - Last update timestamp
- `locked` - Lock flag to prevent auto-updates

### Database Location
```
database/database.db
```

## 🐳 Docker Support

Run the bot in a Docker container:

```bash
docker compose up -d --build
```

The bot will run in detached mode (background).

### Docker Compose Configuration

```yaml
version: '3.8'
services:
  bot:
    build: .
    env_file:
      - .env
    volumes:
      - ./database:/app/database
      - ./achhi-data:/app/achhi-data
    restart: unless-stopped
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please ensure:
- Code follows [PEP 8](https://peps.python.org/pep-0008/) style guide
- All tests pass
- Documentation is updated
- Commit messages are descriptive

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## 🐛 Known Issues & Limitations

- **Private Profiles**: Cannot track users with private Steam profiles
- **Rate Limiting**: Steam API has rate limits; large updates may take time
- **Emoji Limit**: Discord allows max 2000 application emojis per bot
- **Thread Permissions**: Bot needs "Create Public Threads" permission for minigames

## 📚 Additional Documentation

- [OAuth2 Setup Guide](OAUTH2_SETUP.md) - Detailed Steam verification setup
- [Updates](UPDATES.md) - Version history and changelog
- [Code of Conduct](CODE_OF_CONDUCT.md) - Community guidelines
- [License](LICENSE.md) - Apache 2.0 License

## 🙏 Credits

**Template Base**: This project was built using [kkrypt0nn's Python Discord Bot Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)

**Orginal Idea and Code:** [Sparrows-E-Sports-Ulm](https://github.com/Sparrows-E-Sports-Ulm/AchievementHunterInitiativeBot)

**Technologies Used**:
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client
- [aiosqlite](https://github.com/omnilib/aiosqlite) - Async SQLite wrapper
- [Steam Web API](https://steamcommunity.com/dev) - Steam data integration

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details.

**Original template credits must be maintained as per the template license.**

## 💬 Support

Need help? Have questions?

- Open an [Issue](https://github.com/AllRoundJonU/AchievementHunterInitiativeBot/issues)
- Check existing issues for solutions
- Read the documentation in this README

## 🌟 Star History

If you find this project useful, please consider giving it a star! ⭐

---

<p align="center">
  Made with ❤️ for the Sparrows E-Sports Achievement Hunter community
</p>
