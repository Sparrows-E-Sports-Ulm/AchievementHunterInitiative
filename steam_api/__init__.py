from .steam_user import SteamUser
from .steam_web_api import SteamWebAPI, PrivateProfileError, InvalidAPIKeyError, RateLimitError, SteamAPIError

class SteamAPI:
    def __init__(self, api_key: str, logger=None, database=None) -> None:
        if not api_key:
            raise ValueError("Steam API key is required")
        
        self.logger = logger
        self.api_key = api_key
        self.database = database
        self.web_api = SteamWebAPI(api_key, logger=logger, database=database)

    def create_user(self, identifier: str) -> SteamUser:
        """
        Creates a new SteamUser object with the current API key.
        Uses the shared web_api instance to avoid creating multiple sessions.
        
        :param identifier: Steam ID or vanity URL
        :return: SteamUser object
        """
        return SteamUser(self.api_key, identifier, logger=self.logger, web_api=self.web_api)

    async def _ensure_steam_id(self, identifier: str) -> str:
        """
        Ensures the identifier is a Steam ID, converting from vanity URL if necessary.
        
        :param identifier: Either a Steam ID or vanity URL
        :return: Steam ID
        """
        if identifier.isdigit():
            return identifier
        return await self.vantity_to_steamid(identifier)

    async def vantity_to_steamid(self, vanity_url: str) -> str:
        """
        Converts a Steam vanity URL to a Steam ID.

        :param vanity_url: The vanity URL of the Steam user.
        :return: The corresponding Steam ID.
        """
        response = await self.web_api.resolve_vanity_url(vanity_url)
        steam_id = response['response']['steamid']
        return steam_id

    async def exists(self, steam_id: str) -> bool:
        """
        Checks if a Steam user exists using the provided Steam ID.

        :param steam_id: The Steam ID of the user.
        :return: True if the user exists, False otherwise.
        """
        try:
            steam_id = await self._ensure_steam_id(steam_id)
            response = await self.web_api.get_player_summaries(steam_id)
            players = response.get('response', {}).get('players', [])
            return len(players) > 0
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking if user exists: {e}")
            return False
        
    async def get_player_profile_url(self, steam_id: str) -> str:
        """
        Retrieves the profile URL of a Steam user by their Steam ID.

        :param steam_id: The Steam ID of the user.
        :return: The profile URL of the user.
        """
        steam_id = await self._ensure_steam_id(steam_id)
        response = await self.web_api.get_player_summaries(steam_id)
        players = response.get('response', {}).get('players', [])
        if players:
            return players[0].get('profileurl', '')
        return ''
    
    async def close(self):
        """Close all API connections."""
        await self.web_api.close()

    async def get_global_achievement_percentage(self, app_id: int, achievement_name: str) -> float:
        """
        Get the global achievement percentage for a specific achievement.

        :param app_id: The application ID of the game.
        :param achievement_name: The name of the achievement.
        :return: The global achievement percentage.
        """
        response = await self.web_api.get_global_achievement_percentages(app_id)
        achievements = response.get('achievementpercentages', {}).get('achievements', [])
        for achievement in achievements:
            if achievement.get('name') == achievement_name:
                return achievement.get('percent', 0.0)
        return 0.0

# Export both classes for easy importing
__all__ = ['SteamAPI', 'SteamUser', 'PrivateProfileError', 'InvalidAPIKeyError', 'RateLimitError', 'SteamAPIError']