"""
Performance Configuration Command

Allows administrators to adjust the batch size for score calculations
to optimize performance vs. resource usage.
"""

import discord
from discord import app_commands
from discord.ext import commands


class PerformanceConfig(commands.Cog, name="performance_config"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.default_batch_size = 15  # Default batch size for parallel processing

    @app_commands.command(
        name="performance", 
        description="View or configure performance settings for score calculations."
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        batch_size="Number of games to process in parallel (5-30, default: 15)"
    )
    async def performance_config(
        self, 
        interaction: discord.Interaction, 
        batch_size: int = None
    ) -> None:
        """
        View or configure performance settings.

        :param interaction: The interaction that triggered the command.
        :param batch_size: Optional new batch size (5-30)
        """
        await interaction.response.defer(ephemeral=True)

        score_calculator = self.bot.get_cog("score_calculator")
        
        if not score_calculator:
            return await interaction.followup.send(
                "The score calculator is currently unavailable."
            )
        
        embed = discord.Embed(
            title="⚡ Performance Configuration",
            color=discord.Color.gold()
        )
        
        # If batch_size is provided, update it
        if batch_size is not None:
            if batch_size < 5 or batch_size > 30:
                return await interaction.followup.send(
                    "❌ Batch size must be between 5 and 30.",
                    ephemeral=True
                )
            
            self.default_batch_size = batch_size
            embed.add_field(
                name="✅ Updated",
                value=f"Batch size set to: **{batch_size}**",
                inline=False
            )
        
        # Display current configuration
        embed.add_field(
            name="📊 Current Batch Size",
            value=f"**{self.default_batch_size}** games processed in parallel",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ What is Batch Size?",
            value=(
                "Batch size determines how many games are processed simultaneously.\n\n"
                "**Higher values (20-30):**\n"
                "✅ Faster calculations\n"
                "❌ More resource usage\n"
                "❌ Risk of rate limiting\n\n"
                "**Lower values (5-10):**\n"
                "✅ More stable\n"
                "✅ Less resource usage\n"
                "❌ Slower calculations\n\n"
                "**Recommended: 15** (balanced)"
            ),
            inline=False
        )
        
        # Get queue stats
        queue_size = score_calculator.get_queue_size()
        current = score_calculator.current_calculation
        
        embed.add_field(
            name="📋 Queue Status",
            value=(
                f"Currently processing: {'Yes' if current else 'No'}\n"
                f"Queue size: {queue_size}"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use /performance <batch_size> to change the setting")
        
        await interaction.followup.send(embed=embed)
    
    def get_batch_size(self) -> int:
        """Get the current batch size setting."""
        return self.default_batch_size


async def setup(bot):
    await bot.add_cog(PerformanceConfig(bot))
