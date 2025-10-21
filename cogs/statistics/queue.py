import discord
from discord import app_commands
from discord.ext import commands


class QueueStatus(commands.Cog, name="queue_status"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="queue", description="Check the status of the score calculation queue."
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    async def queue_status(self, interaction: discord.Interaction) -> None:
        """
        This command shows the current status of the score calculation queue.

        :param interaction: The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)

        score_calculator = self.bot.get_cog("score_calculator")
        
        if not score_calculator:
            return await interaction.followup.send(
                "The score calculator is currently unavailable."
            )
        
        queue_size = score_calculator.get_queue_size()
        current_calculation = score_calculator.current_calculation
        
        embed = discord.Embed(
            title="📊 Score Calculation Queue Status",
            color=discord.Color.blue()
        )
        
        if current_calculation:
            embed.add_field(
                name="🔄 Currently Processing",
                value=f"Steam ID: `{current_calculation}`",
                inline=False
            )
        else:
            embed.add_field(
                name="🔄 Currently Processing",
                value="No calculation in progress",
                inline=False
            )
        
        embed.add_field(
            name="📋 Queue Size",
            value=f"{queue_size} calculation(s) waiting",
            inline=False
        )
        
        if queue_size == 0 and not current_calculation:
            embed.add_field(
                name="✅ Status",
                value="Queue is empty and ready for new calculations",
                inline=False
            )
        
        # Check if the user has a calculation in progress
        hunter_data = await self.bot.database.get_hunter_by_discord_id(interaction.user.id)
        if hunter_data:
            steam_id = hunter_data.get('steam_id')
            position = score_calculator.get_queue_position(steam_id)
            
            if position is not None:
                if position == 0:
                    embed.add_field(
                        name="👤 Your Status",
                        value="Your score is currently being calculated",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="👤 Your Status",
                        value=f"Your calculation is in queue at position {position}",
                        inline=False
                    )
            else:
                # Check if we have recent stats
                stats = score_calculator.get_calculation_stats(steam_id)
                if stats:
                    embed.add_field(
                        name="👤 Last Calculation",
                        value=f"Score: {stats['score']}\n"
                              f"Achievements: {stats['total_achievements']}\n"
                              f"Duration: {stats['duration_seconds']:.2f}s\n"
                              f"Calculated at: <t:{int(stats['calculated_at'].timestamp())}:R>",
                        inline=False
                    )
        
        return await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(QueueStatus(bot))
