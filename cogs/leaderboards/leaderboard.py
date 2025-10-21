import discord
from discord import app_commands
from discord.ext import commands
import math
from dataclasses import dataclass, field
from utils.number_emotes import number_to_emotes



@dataclass
class SectionData:
    rank: int
    steam_name: str
    score: int
    total_achievements: int
    profile_url: str = field(default=None)

@dataclass
class LeaderboardData:
    sections: list[SectionData]
    current_page: int
    total_pages: int
    type : str  # "score" or "achievements"

class LeaderboardView(discord.ui.LayoutView):
    def __init__(self, data: LeaderboardData, bot=None):
        super().__init__(timeout=300)  # 5 Minuten Timeout
        self.data = data
        self.bot = bot
        self._build_view()

    def _build_view(self):
        """Build the complete leaderboard view."""
        # Clear existing items
        self.clear_items()
        
        container = discord.ui.Container(
            accent_colour=discord.Color.gold()
        )
        header = discord.ui.TextDisplay(f'## 🏆 Achievement Hunter Leaderboard - {self.data.type.capitalize()}')
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

        # Add a action row for navigation with buttons (if needed)
        if self.data.total_pages > 1:
            action_row = discord.ui.ActionRow()
            
            # Previous button
            prev_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="◀ Previous",
                custom_id=f"leaderboard_prev",
                disabled=(self.data.current_page <= 1)
            )
            prev_button.callback = self._previous_page_callback
            action_row.add_item(prev_button)
            
            # Next button
            next_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Next ▶",
                custom_id=f"leaderboard_next",
                disabled=(self.data.current_page >= self.data.total_pages)
            )
            next_button.callback = self._next_page_callback
            action_row.add_item(next_button)
            
            container.add_item(action_row)

        footer = discord.ui.TextDisplay('-#'f' **Page:** {self.data.current_page}/{self.data.total_pages}\n')
        container.add_item(footer)
        self.add_item(container)

    async def _previous_page_callback(self, interaction: discord.Interaction):
        """Handle previous page button click."""
        await interaction.response.defer()
        
        if self.data.current_page <= 1:
            return
        
        # Load previous page
        new_page = self.data.current_page - 1
        await self._load_and_update_page(interaction, new_page)

    async def _next_page_callback(self, interaction: discord.Interaction):
        """Handle next page button click."""
        await interaction.response.defer()
        
        if self.data.current_page >= self.data.total_pages:
            return
        
        # Load next page
        new_page = self.data.current_page + 1
        await self._load_and_update_page(interaction, new_page)

    async def _load_and_update_page(self, interaction: discord.Interaction, new_page: int):
        """Load data for a new page and update the message."""
        if not self.bot:
            return
        
        per_page = 8
        offset = (new_page - 1) * per_page
        
        # Determine order_by from type
        order_by = "score" if self.data.type.lower() == "score" else "total_achievements"
        
        # Fetch new data
        hunters = await self.bot.database.get_scoreboard(
            limit=per_page,
            offset=offset,
            order_by=order_by
        )
        
        if not hunters:
            await interaction.followup.send("No data available for this page.", ephemeral=True)
            return
        
        # Build new sections
        sections: list[SectionData] = []
        for idx, hunter in enumerate(hunters, start=offset + 1):
            section = SectionData(
                rank=idx,
                steam_name=hunter['steam_name'],
                score=hunter['score'],
                total_achievements=hunter['total_achievements'],
                profile_url=await self.bot.steamAPI.get_player_profile_url(hunter['steam_id'])
            )
            sections.append(section)
        
        # Update data
        self.data.sections = sections
        self.data.current_page = new_page
        
        # Rebuild view
        self._build_view()
        
        # Edit the original message
        try:
            await interaction.edit_original_response(view=self)
        except Exception as e:
            if self.bot:
                self.bot.logger.error(f"Error updating leaderboard: {e}")

    async def on_timeout(self):
        """Disable buttons when view times out."""
        # Disable all buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class Leaderboard(commands.Cog, name="leaderboard"):
    def __init__(self, bot) -> None:
        self.bot = bot
    
    @app_commands.command(
        name="leaderboard", 
        description="Shows the Achievement Hunter Leaderboard"
    )
    @app_commands.describe(
        page="Page number (default: 1)",
        category="Category: score or achievements (default: score)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Score", value="score"),
        app_commands.Choice(name="Achievements", value="total_achievements")
    ])
    async def leaderboard(
        self, 
        interaction: discord.Interaction, 
        page: int = 1,
        category: app_commands.Choice[str] = None
    ) -> None:
        """
        Displays the leaderboard with pagination support.
        
        :param interaction: The interaction that triggered the command.
        :param page: The page number to display (default: 1).
        :param category: The category to sort by (score or achievements).
        """

        await interaction.response.defer()

        # Validierung
        if page < 1:
            page = 1
        
        # Bestimme Sortier-Kategorie
        order_by = category.value if category else "score"
        category_name = "Score" if order_by == "score" else "Achievements"
        
        per_page = 8
        offset = (page - 1) * per_page
        
        
        # Daten holen
        hunters = await self.bot.database.get_scoreboard(
            limit=per_page,
            offset=offset,
            order_by=order_by
        )
        
        total_hunters = await self.bot.database.get_total_hunters_count()
        total_pages = max(1, math.ceil(total_hunters / per_page))
        
        # Sicherstellen, dass die Seite gültig ist
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * per_page
            hunters = await self.bot.database.get_scoreboard(
                limit=per_page,
                offset=offset,
                order_by=order_by
            )

        if not hunters:
            await interaction.followup.send(
            "No hunters have been registered yet.",
            ephemeral=True
        )
            
        sections: list[SectionData] = []
        for idx, hunter in enumerate(hunters, start=offset + 1):
            section = SectionData(
                rank=idx,
                steam_name=hunter['steam_name'],
                score=hunter['score'],
                total_achievements=hunter['total_achievements'],
                profile_url= await self.bot.steamAPI.get_player_profile_url(hunter['steam_id']) or None
            )
            sections.append(section)

        leaderboard_data = LeaderboardData(
            sections=sections,
            current_page=page,
            total_pages=total_pages,
            type=category_name
        )

        await interaction.followup.send(view=LeaderboardView(leaderboard_data, bot=self.bot))

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))