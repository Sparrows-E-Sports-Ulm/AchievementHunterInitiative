"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.4.0
"""

import json
import logging
import os
import platform
import random
import sys

import aiosqlite
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv

from database import DatabaseManager
from steam_api import SteamAPI
from utils.language_manager import get_language_manager

load_dotenv()

"""	
Setup bot intents (events restrictions)
For more information about intents, please go to the following websites:
https://discordpy.readthedocs.io/en/latest/intents.html
https://discordpy.readthedocs.io/en/latest/intents.html#privileged-intents


Default Intents:
intents.bans = True
intents.dm_messages = True
intents.dm_reactions = True
intents.dm_typing = True
intents.emojis = True
intents.emojis_and_stickers = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_scheduled_events = True
intents.guild_typing = True
intents.guilds = True
intents.integrations = True
intents.invites = True
intents.messages = True # `message_content` is required to get the content of the messages
intents.reactions = True
intents.typing = True
intents.voice_states = True
intents.webhooks = True

Privileged Intents (Needs to be enabled on developer portal of Discord), please use them only if you need them:
intents.members = True
intents.message_content = True
intents.presences = True
"""

intents = discord.Intents.default()

"""
Uncomment this if you want to use prefix (normal) commands.
It is recommended to use slash commands and therefore not use prefix commands.

If you want to use prefix commands, make sure to also enable the intent below in the Discord developer portal.
"""
# intents.message_content = True

# Setup both of the loggers


class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# Add the handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv("PREFIX")),
            intents=intents,
            help_command=None,
        )
        """
        This creates custom bot variables so that we can access these variables in cogs more easily.

        For example, The logger is available using the following code:
        - self.logger # In this class
        - bot.logger # In this file
        - self.bot.logger # In cogs
        """
        self.logger = logger
        self.database = None
        self.steamAPI = SteamAPI(logger = self.logger, api_key=os.getenv("STEAM_API_KEY"))
        self.bot_prefix = os.getenv("PREFIX")
        self.invite_link = os.getenv("INVITE_LINK")
        self.oauth2_server = None  # Will be initialized in setup_hook
        self.language_manager = get_language_manager(os.getenv("LOCALE", "en"))

    async def init_db(self) -> None:
        async with aiosqlite.connect(
            f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
        ) as db:
            with open(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/schema.sql",
                encoding = "utf-8"
            ) as file:
                await db.executescript(file.read())
            await db.commit()

    async def load_cogs(self) -> None:
        """
        The code in this function is executed whenever the bot will start.
        """
        from pathlib import Path

        cogs_dir = Path(f"{os.path.realpath(os.path.dirname(__file__))}/cogs")

        async def load_extensions_recursive(directory):
            for path in directory.iterdir():
                if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
                    # Konvertiere den Dateipfad in ein Python-Importformat
                    relative_path = path.relative_to(os.path.realpath(os.path.dirname(__file__)))
                    import_path = str(relative_path.with_suffix("")).replace("/", ".").replace("\\", ".")
                    try:
                        await self.load_extension(import_path)
                        self.logger.info(f"Loaded extension '{import_path}'")
                    except Exception as e:
                        exception = f"{type(e).__name__}: {e}"
                        self.logger.error(f"Failed to load extension {import_path}\n{exception}")
                elif path.is_dir() and not path.name.startswith("_"):
                    # Rekursiv in Unterordnern suchen
                    await load_extensions_recursive(path)
        await load_extensions_recursive(cogs_dir)

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        """
        Setup the game status task of the bot.
        """
        statuses = ["with you!", "with Krypton!", "with humans!"]
        await self.change_presence(activity=discord.Game(random.choice(statuses)))

    @status_task.before_loop
    async def before_status_task(self) -> None:
        """
        Before starting the status changing task, we make sure the bot is ready
        """
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        """
        This will just be executed when the bot starts the first time.
        """
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")
        await self.init_db()
        
        # Initialize database connection
        self.database = DatabaseManager(
            connection=await aiosqlite.connect(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
            )
        )
        
        # Update SteamAPI with database reference for statistics tracking
        self.steamAPI.database = self.database
        self.steamAPI.web_api.database = self.database
        
        await self.load_cogs()
        self.status_task.start()
        
        # Start OAuth2 server if configured
        try:
            from utils.oauth2_server import OAuth2CallbackServer
            oauth_port = int(os.getenv("OAUTH2_PORT", "8080"))
            self.oauth2_server = OAuth2CallbackServer(self, port=oauth_port)
            await self.oauth2_server.start()
        except Exception as e:
            self.logger.warning(f"OAuth2 server not started: {e}")
            self.logger.info("Set DISCORD_CLIENT_SECRET to enable /verify_steam command")

    async def close(self) -> None:
        """
        Cleanup when the bot is shutting down.
        """
        self.logger.info("Shutting down bot...")
        
        # Stop OAuth2 server
        if self.oauth2_server:
            await self.oauth2_server.stop()
            self.logger.info("Stopped OAuth2 server")
        
        # Close Steam API connections
        if self.steamAPI:
            await self.steamAPI.close()
            self.logger.info("Closed Steam API connections")
        
        # Close database connection
        if self.database:
            await self.database.close()
            self.logger.info("Closed database connection")
        
        # Call parent close method
        await super().close()
        self.logger.info("Bot shutdown complete")

    async def on_message(self, message: discord.Message) -> None:
        """
        The code in this event is executed every time someone sends a message, with or without the prefix

        :param message: The message that was sent.
        """
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)

    async def on_command_completion(self, context: Context) -> None:
        """
        The code in this event is executed every time a normal command has been *successfully* executed.

        :param context: The context of the command that has been executed.
        """
        full_command_name = context.command.qualified_name
        split = full_command_name.split(" ")
        executed_command = str(split[0])
        if context.guild is not None:
            self.logger.info(
                f"Executed {executed_command} command in {context.guild.name} (ID: {context.guild.id}) by {context.author} (ID: {context.author.id})"
            )
        else:
            self.logger.info(
                f"Executed {executed_command} command by {context.author} (ID: {context.author.id}) in DMs"
            )

    async def on_command_error(self, context: Context, error) -> None:
        """
        The code in this event is executed every time a normal valid command catches an error.

        :param context: The context of the normal command that failed executing.
        :param error: The error that has been faced.
        """
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            time_str = self.language_manager.format_time(hours, minutes, seconds)
            embed = discord.Embed(
                description=self.language_manager.get_error_string("command_cooldown", time=time_str),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                description=self.language_manager.get_error_string("not_owner"), color=0xE02B2B
            )
            await context.send(embed=embed)
            if context.guild:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the guild {context.guild.name} (ID: {context.guild.id}), but the user is not an owner of the bot."
                )
            else:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the bot's DMs, but the user is not an owner of the bot."
                )
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description=self.language_manager.get_error_string(
                    "missing_permissions", 
                    permissions=", ".join(error.missing_permissions)
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                description=self.language_manager.get_error_string(
                    "bot_missing_permissions", 
                    permissions=", ".join(error.missing_permissions)
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title=self.language_manager.get_general_string("error"),
                description=self.language_manager.get_error_string(
                    "missing_required_argument", 
                    error=str(error).capitalize()
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        else:
            raise error


bot = DiscordBot()
bot.run(os.getenv("TOKEN"))
