"""
Register Cog - Handles new hunter registration with Steam profile validation.

This module provides the /register command that allows users to register as
Achievement Hunters by providing their Steam ID or vanity URL. It performs
comprehensive validation checks on Steam profile visibility and accessibility.
"""

import discord
from discord import app_commands
from discord.ext import commands

from steam_api import PrivateProfileError
from utils.message_views import MessageView


class Register(commands.Cog, name="register"):
    """
    Cog for registering new Achievement Hunters.
    
    Handles user registration with Steam profile validation, privacy checks,
    and automatic queueing for initial score calculation.
    """
    
    def __init__(self, bot) -> None:
        """
        Initialize the Register cog.
        
        :param bot: The Discord bot instance.
        """
        self.bot = bot
        self.lang = bot.language_manager
    
    
    @app_commands.command(
        name="register",
        description="Register your Steam ID with the bot."
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    @app_commands.describe(steam_id="Your Steam ID or Vanity URL name")
    async def register(
        self, 
        interaction: discord.Interaction, 
        steam_id: str
    ) -> None:
        """
        Register a user as an Achievement Hunter.
        
        This command performs the following steps:
        1. Validates that the Steam ID exists
        2. Normalizes the Steam ID (converts vanity URLs)
        3. Checks if the user is already registered
        4. Validates Steam profile visibility (must be public)
        5. Verifies game details are accessible
        6. Registers the hunter in the database
        7. Queues initial score calculation
        
        :param interaction: The Discord interaction that triggered this command.
        :param steam_id: The Steam ID (64-bit) or vanity URL name to register.
        """
        # Defer response as Steam API calls may take time
        await interaction.response.defer(ephemeral=True)
        
        # ===== STEP 1: Validate Steam ID Existence =====
        if not await self.bot.steamAPI.exists(steam_id):
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get("errors.steam_id_not_found", steam_id=steam_id)
                )
            )
        
        # ===== STEP 2: Normalize Steam ID (Convert Vanity URL) =====
        try:
            normalized_steam_id = await self.bot.steamAPI._ensure_steam_id(steam_id)
        except Exception as e:
            self.bot.logger.error(f"Error resolving Steam ID {steam_id}: {e}")
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get("commands.steam_id_resolution_failed", steam_id=steam_id)
                )
            )
        
        # ===== STEP 3: Check for Duplicate Registration =====
        if await self.bot.database.get_hunter_by_steam_id(normalized_steam_id):
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.yellow(),
                    message=self.lang.get("commands.register.already_registered")
                )
            )
        
        # ===== STEP 4: Validate Steam Profile Accessibility =====
        try:
            # Create Steam user object
            steam_user = self.bot.steamAPI.create_user(normalized_steam_id)
            
            # Fetch Steam profile with forced refresh
            steam_profile = await steam_user.get_profile(force_refresh=True)
            
            # Check Steam community visibility state
            # 3 = Public, 2 = Friends Only, 1 = Private
            visibility_state = steam_profile.get('communityvisibilitystate', 0)
            
            if visibility_state != 3:
                # Profile is not public - registration not allowed
                visibility_text = self.lang.get_profile_visibility(visibility_state)
                
                self.bot.logger.warning(
                    f"Cannot register {normalized_steam_id}: "
                    f"Profile visibility is '{visibility_text}' (state: {visibility_state})"
                )
                
                return await interaction.followup.send(
                    view=MessageView(
                        colour=discord.Color.red(),
                        message=self.lang.get(
                            "commands.register.profile_not_public", 
                            visibility=visibility_text
                        )
                    )
                )
            
            # ===== STEP 5: Verify Game Details Access =====
            games_response = await steam_user.get_games(
                force_refresh=True, 
                include_free_games=False
            )
            
            # Check if we received valid game data
            if not games_response or 'response' not in games_response:
                raise PrivateProfileError("Cannot access game details")
        
        except PrivateProfileError:
            # Game details are private
            self.bot.logger.warning(
                f"Cannot register {normalized_steam_id}: Game details are not public"
            )
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get("commands.register.game_details_private")
                )
            )
        
        except Exception as e:
            # Unexpected error during profile fetch
            self.bot.logger.error(
                f"Error fetching profile for {normalized_steam_id}: {e}"
            )
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get("commands.register.fetch_failed")
                )
            )
        
        # ===== STEP 6: Register Hunter in Database =====
        steam_name = steam_profile.get('personaname', 'Unknown')
        
        self.bot.logger.debug(
            f"Registering new hunter: {steam_name} ({normalized_steam_id})"
        )
        
        await self.bot.database.add_hunter(
            steam_id=str(normalized_steam_id),
            steam_name=steam_name
        )
        
        # ===== STEP 7: Queue Initial Score Calculation =====
        score_calculator = self.bot.get_cog("score_calculator")
        
        if score_calculator:
            # Calculator is available - add to queue
            queue_position = await score_calculator.add_to_queue(normalized_steam_id)
            
            message = MessageView(
                colour=discord.Color.green(),
                header=self.lang.get("commands.register.success_header"),
                message=self.lang.get(
                    "commands.register.success_queued",
                    position=queue_position,
                    steam_id=steam_id
                )
            )
        else:
            # Calculator is not available - warn user
            message = MessageView(
                colour=discord.Color.orange(),
                message=self.lang.get("commands.register.calculator_unavailable")
            )
        
        return await interaction.followup.send(view=message)


async def setup(bot):
    """
    Setup function to add this cog to the bot.
    
    :param bot: The Discord bot instance.
    """
    await bot.add_cog(Register(bot))