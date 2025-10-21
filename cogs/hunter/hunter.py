import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

from dataclasses import dataclass, field

@dataclass
class HunterData:
    steam_id: str
    steam_name: str | None = None
    discord_id: str | None = None
    score: int = 0
    total_achievements: int = 0
    avatar_url: str | None = None


class Layout(discord.ui.LayoutView):
    def __init__(self, hunter: HunterData):
        super().__init__()
        self.hunter = hunter 

    
        container = discord.ui.Container()
        header = discord.ui.Section(
            discord.ui.TextDisplay(f'## {self.hunter.steam_name or "Unknown"}`s Profile'),
            discord.ui.TextDisplay(f'**Steam ID:** `{self.hunter.steam_id}`\n'
                       f'**Total Score:** `{self.hunter.score:,}`\n'
                       f'**Total Achievements:** `{self.hunter.total_achievements:,}`\n'),
            accessory=discord.ui.Thumbnail(media=self.hunter.avatar_url) if self.hunter.avatar_url else None
        )
        
        container.add_item(header)
        self.add_item(container)


class Hunter(commands.Cog, name="hunter"):
    def __init__(self, bot):
        self.bot = bot
        self.hunter = None

    @commands.hybrid_command(
        name="hunter", description="Get information about a registered hunter."
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    @app_commands.describe(steam_id="The Steam ID of the hunter.")
    async def hunter(self, context: Context, steam_id: str | None = None) -> None:
        """
        This command will return information about a registered hunter.

        :param interaction: The interaction that triggered the command.
        :param steam_id: The Steam ID of the hunter that should be returned. If None, the command will try to use the Discord ID of the user.
        """

        if steam_id is None:
            # Try to get the hunter by their Discord ID
            hunter = await self.bot.database.get_hunter_by_discord_id(str(context.user.id))
            if hunter is None:
                return await context.send(
                    "You are not registered as a hunter. Please provide a Steam ID or register using /register."
                )
            steam_id = hunter["steam_id"]
        else:
            # Try to get the hunter by their Steam ID
            hunter = self.bot.steamAPI.create_user(steam_id)
            profileData = await hunter.get_profile()
            databaseData = await self.bot.database.get_hunter_by_steam_id(profileData.get('steamid'))
            
            if databaseData is None:
                return await context.send(
                    "The provided Steam ID is not registered as a hunter. Please check and try again."
                )
            
            self.hunter = HunterData(
                steam_id=profileData.get('steamid'),
                steam_name=profileData.get('personaname'),
                avatar_url=profileData.get('avatarfull'),
                discord_id=databaseData['discord_id'] if databaseData else None,
                score=databaseData['score'] if databaseData else 0,
                total_achievements=databaseData['total_achievements'] if databaseData else 0
            )

        await context.send(view=Layout(self.hunter))

async def setup(bot):
    await bot.add_cog(Hunter(bot))