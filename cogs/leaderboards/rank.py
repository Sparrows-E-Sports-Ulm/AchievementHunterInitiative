import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import math
from dataclasses import dataclass, field
from utils.number_emotes import number_to_emotes
from utils.message_views import ErrorMessageView


@dataclass
class SectionData:
    rank: int
    steam_name: str
    score: int
    total_achievements: int
    profile_url: str = field(default=None)

@dataclass
class RankboardData:
    sections: list[SectionData]
    total_hunters: int
    type : str  # "score" or "achievements"


class RankView(discord.ui.LayoutView):
    def __init__(self, data: RankboardData):
        super().__init__(timeout=300)  # 5 Minuten Timeout
        self.data = data
        self._build_view()


    def _build_view(self):
        """Build the complete rank view."""
        # Clear existing items
        self.clear_items()
        
        container = discord.ui.Container(
            accent_colour=discord.Color.blue()
        )
        header = discord.ui.TextDisplay(f'## 📊 Achievement Hunter Rank - {self.data.type.capitalize()}')
        container.add_item(header)
        
        # Add sections
        for section_data in self.data.sections:
            top_row, bottom_row = number_to_emotes(section_data.rank, min_digits=2)

            current_section = discord.ui.Section(
                discord.ui.TextDisplay(
                    f"{top_row} **{section_data.steam_name}**\n"
                    f"{bottom_row} Score: {section_data.score:,}, Achievements: {section_data.total_achievements:,}"
                ),
                accessory=discord.ui.Button(style=discord.ButtonStyle.link, label="Profile", url=section_data.profile_url) if section_data.profile_url else None
            )
            container.add_item(current_section)
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Add total hunters info
        total_section = discord.ui.Section(
            discord.ui.TextDisplay(
                f"Total Registered Hunters: **{self.data.total_hunters:,}**"
            )
        )
        container.add_item(total_section)
        
        self.add_item(container)


class Rank(commands.Cog, name="rank"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="rank", 
        description="Shows a hunter's position in the leaderboard with context"
    )
    @app_commands.describe(
        steam_id="Steam ID or vanity URL (optional, defaults to your own)",
        category="Category: score or achievements (default: score)",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Score", value="score"),
        app_commands.Choice(name="Achievements", value="total_achievements")
    ])
    async def rank(
        self, 
        interaction: discord.Interaction,
        steam_id: str,
        category: app_commands.Choice[str] = None,
    ) -> None:
        """
        Shows a hunter's rank in the leaderboard with surrounding players.
        
        :param interaction: The interaction that triggered the command.
        :param steam_id: Optional Steam ID or vanity URL to look up.
        :param category: The category to rank by (score or achievements).
        """
        await interaction.response.defer()
        
        # Determine sort category
        order_by = category.value if category else "score"
        category_name = "Score" if order_by == "score" else "Achievements"
        
        try:
            # If steam_id is provided, look up that hunter
            if steam_id:
                # Normalize the steam_id (convert vanity URL if needed)
                try:
                    target_steam_id = await self.bot.steamAPI._ensure_steam_id(steam_id)
                except Exception as e:
                    self.bot.logger.error(f"Error resolving Steam ID {steam_id}: {e}")
                    return await interaction.followup.send(view=ErrorMessageView(error_message=
                        f"❌ Could not resolve Steam ID: `{steam_id}`\n"
                        "Please provide a valid Steam ID or vanity URL."
                    ))
                
                # Get hunter data from database
                hunter = await self.bot.database.get_hunter_by_steam_id(target_steam_id)
                
                if not hunter:
                    return await interaction.followup.send(
                        f"❌ Hunter with Steam ID `{steam_id}` is not registered.\n"
                        "They need to use `/register` first."
                    )
                
                is_self = False
            else:
                # Get the user's own hunter data
                hunter = await self.bot.database.get_hunter_by_discord_id(str(interaction.user.id))
                
                if not hunter:
                    return await interaction.followup.send(
                        "❌ You are not registered yet!\n"
                        "Use `/register` to sign up as an Achievement Hunter."
                    )
                
                target_steam_id = hunter['steam_id']
                is_self = True
            
            # Get rank and surrounding hunters
            hunters, rank = await self.bot.database.get_hunters_around_rank(
                target_steam_id,
                context_size=2,
                order_by=order_by
            )
            
            if rank is None:
                return await interaction.followup.send(
                    "❌ Error retrieving rank. Please try again later."
                )
            
            # Create embed
            total = await self.bot.database.get_total_hunters_count()
            
            # Calculate percentile
            percentile = ((total - rank) / total * 100) if total > 0 else 0
            
            # Title changes based on whether it's self or another user
            title_prefix = "Your" if is_self else f"{hunter['steam_name']}'s"
            embed = discord.Embed(
                title=f"📊 {title_prefix} Position - {category_name}",
                description=f"Rank **#{rank}** out of **{total}** Hunters\n"
                           f"Top **{100-percentile:.1f}%**",
                color=discord.Color.blue()
            )
            
            # Show surrounding hunters
            if hunters:
                leaderboard_text = ""
                for h in hunters:
                    # Mark the target user
                    is_target_user = h['steam_id'] == target_steam_id
                    indicator = "👉 " if is_target_user else "    "
                    
                    # Medals for top 3
                    h_rank = h['rank']
                    if h_rank == 1:
                        medal = "🥇"
                    elif h_rank == 2:
                        medal = "🥈"
                    elif h_rank == 3:
                        medal = "🥉"
                    else:
                        medal = f"#{h_rank}"
                    
                    # Value based on category
                    value = h[order_by]
                    value_formatted = f"{value:,}" if value else "0"
                    
                    # Steam Name (truncate if too long)
                    name = h['steam_name']
                    if len(name) > 18:
                        name = name[:15] + "..."
                    
                    # Formatting for target user
                    if is_target_user:
                        leaderboard_text += f"{indicator}**{medal} {name}** - **{value_formatted}**\n"
                    else:
                        leaderboard_text += f"{indicator}{medal} {name} - {value_formatted}\n"
                
                embed.add_field(
                    name=f"Rankings (±2 positions)", 
                    value=leaderboard_text, 
                    inline=False
                )
            
            # Show user stats
            user_value = hunter[order_by]
            user_value_formatted = f"{user_value:,}" if user_value else "0"
            
            stats_text = f"**{category_name}:** {user_value_formatted}\n"
            
            # Show difference to next/previous rank
            if hunters:
                # Find position of user in the list
                user_idx = next((i for i, h in enumerate(hunters) if h['steam_id'] == target_steam_id), None)
                
                if user_idx is not None:
                    # Rank above (higher rank)
                    if user_idx > 0:
                        above = hunters[user_idx - 1]
                        diff_above = above[order_by] - user_value
                        stats_text += f"📈 To rank #{above['rank']}: {diff_above:,} points\n"
                    
                    # Rank below (lower rank)
                    if user_idx < len(hunters) - 1:
                        below = hunters[user_idx + 1]
                        diff_below = user_value - below[order_by]
                        stats_text += f"📉 Lead over #{below['rank']}: {diff_below:,} points\n"
            
            embed.add_field(name="Stats", value=stats_text, inline=False)
            
            embed.set_footer(text="Use /leaderboard to see the full rankings")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.bot.logger.error(f"Error in rank command: {e}")
            await interaction.followup.send(
                "❌ Error retrieving position. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Rank(bot))