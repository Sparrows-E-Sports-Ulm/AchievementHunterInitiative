"""
Update Cog - Handles manual score recalculation requests.

This module provides the /update command that allows registered Achievement Hunters
to manually trigger a recalculation of their achievement score. The update is queued
in the score calculator to prevent system overload.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.message_views import MessageView


class Update(commands.Cog, name="update"):
    """
    Cog for updating Achievement Hunter scores.
    
    Allows registered hunters to manually request a score recalculation.
    Updates are queued and processed sequentially by the score calculator.
    """
    
    def __init__(self, bot) -> None:
        """
        Initialize the Update cog.
        
        :param bot: The Discord bot instance.
        """
        self.bot = bot
        self.lang = bot.language_manager
    
    
    @app_commands.command(
        name="update",
        description="Update your Steam achievement score."
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    @app_commands.describe(steam_id="Your unique Steam ID (optional if already linked).")
    async def update(
        self, 
        interaction: discord.Interaction, 
        steam_id: str | None = None
    ) -> None:
        """
        Manually trigger a score recalculation for a registered hunter.
        
        This command performs the following steps:
        1. Resolves the Steam ID (from parameter or Discord link)
        2. Validates that the hunter is registered
        3. Checks if calculator is available
        4. Verifies the hunter is not already in the queue
        5. Adds the update request to the calculation queue
        
        :param interaction: The Discord interaction that triggered this command.
        :param steam_id: Optional Steam ID. If not provided, uses Discord-linked account.
        """
        # Defer response as database/API calls may take time
        await interaction.response.defer(ephemeral=True)
        
        # ===== STEP 1: Resolve Steam ID =====
        # Clean up provided Steam ID or get from Discord link
        steam_id = steam_id.strip() if steam_id else None
        
        if not steam_id:
            # No Steam ID provided - try to get from Discord link
            hunter_data = await self.bot.database.get_hunter_by_discord_id(
                interaction.user.id
            )
            
            if not hunter_data:
                # User is not linked to any Steam account
                return await interaction.followup.send(
                    view=MessageView(
                        colour=discord.Color.red(),
                        message=self.lang.get("errors.not_linked")
                    )
                )
            
            steam_id = hunter_data.get('steam_id')
        
        # Normalize Steam ID (convert vanity URL to 64-bit ID)
        try:
            normalized_steam_id = await self.bot.steamAPI._ensure_steam_id(steam_id)
        except Exception as e:
            self.bot.logger.error(f"Error resolving Steam ID {steam_id}: {e}")
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get(
                        "errors.steam_id_resolution_failed",
                        steam_id=steam_id
                    )
                )
            )
        
        # ===== STEP 2: Validate Hunter Registration =====
        hunter = await self.bot.database.get_hunter_by_steam_id(normalized_steam_id)
        
        if not hunter:
            # Hunter is not registered in the database
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message=self.lang.get(
                        "commands.update.not_registered",
                        steam_id=steam_id
                    )
                )
            )
        
        # ===== STEP 3: Check Score Calculator Availability =====
        score_calculator = self.bot.get_cog("score_calculator")
        
        if not score_calculator:
            # Score calculator cog is not loaded
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.yellow(),
                    message=self.lang.get("commands.update.calculator_unavailable")
                )
            )
        
        # ===== STEP 4: Check Queue Status =====
        # Verify the hunter is not already in the calculation queue
        if score_calculator.is_in_queue(normalized_steam_id):
            # Already queued - inform user of their position
            position = score_calculator.get_queue_position(normalized_steam_id)
            
            return await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.yellow(),
                    message=self.lang.get(
                        "commands.update.allready_queued",
                        position=position
                    )
                )
            )
        
        # ===== STEP 5: Queue Score Recalculation =====
        queue_position = await score_calculator.add_to_queue(normalized_steam_id)
        
        self.bot.logger.info(
            f"Hunter {normalized_steam_id} queued for update at position {queue_position}"
        )
        
        return await interaction.followup.send(
            view=MessageView(
                colour=discord.Color.green(),
                message=self.lang.get(
                    "commands.update.success_queued",
                    position=queue_position
                )
            )
        )


async def setup(bot):
    """
    Setup function to add this cog to the bot.
    
    :param bot: The Discord bot instance.
    """
    await bot.add_cog(Update(bot))
