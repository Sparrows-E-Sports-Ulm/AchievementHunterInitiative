import aiohttp
import asyncio
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode


class SteamAPIError(Exception):
    """Base exception for Steam API errors."""
    pass


class PrivateProfileError(SteamAPIError):
    """Raised when a Steam profile is private or friends-only."""
    pass


class InvalidAPIKeyError(SteamAPIError):
    """Raised when the Steam API key is invalid."""
    pass


class RateLimitError(SteamAPIError):
    """Raised when the Steam API rate limit is exceeded."""
    pass


class SteamWebAPI:
    """Simple Steam Web API implementation with built-in statistics tracking."""
    
    BASE_URL = "https://api.steampowered.com"
    
    def __init__(self, api_key: str, logger=None, database=None):
        self.api_key = api_key
        self.logger = logger
        self.database = database
        self.session: Optional[aiohttp.ClientSession] = None
        self._closed = False
        
        # In-memory statistics (for current session)
        self.session_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'rate_limit_hits': 0,
            'private_profile_errors': 0,
            'total_response_time_ms': 0
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._closed:
            raise RuntimeError("Cannot use SteamWebAPI after it has been closed")
        
        if self.session is None or self.session.closed:
            # Create session with timeout configuration
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                raise_for_status=False
            )
        return self.session
    
    async def _make_request(
        self, 
        endpoint: str, 
        version: int, 
        params: Dict[str, Any], 
        needKey: bool = True,
        endpoint_name: Optional[str] = None,
        steam_id: Optional[str] = None,
        app_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Steam Web API with statistics tracking.
        
        :param endpoint: API endpoint (e.g., 'ISteamUser/ResolveVanityURL')
        :param version: API version (1 -> v0001, 2 -> v0002, etc.)
        :param params: Query parameters
        :param needKey: Whether API key is needed
        :param endpoint_name: Human-readable endpoint name for tracking
        :param steam_id: Optional Steam ID for tracking
        :param app_id: Optional App ID for tracking
        :return: JSON response
        """
        if needKey:
            params['key'] = self.api_key
        version_str = f"v{version:04d}"
        url = f"{self.BASE_URL}/{endpoint}/{version_str}/?{urlencode(params)}"
        
        session = await self._get_session()
        
        # Track statistics
        start_time = time.time()
        success = True
        error_type = None
        
        try:
            self.session_stats['total_calls'] += 1
            
            async with session.get(url) as response:
                response_time_ms = int((time.time() - start_time) * 1000)
                self.session_stats['total_response_time_ms'] += response_time_ms
                
                # Check for specific error codes
                if response.status == 403:
                    success = False
                    error_type = 'PrivateProfile'
                    self.session_stats['private_profile_errors'] += 1
                    if self.logger:
                        self.logger.warning(f"Steam API request forbidden (403): {endpoint} - Likely private profile")
                    
                    # Track in database
                    if self.database and endpoint_name:
                        await self.database.increment_api_call(
                            endpoint_name, steam_id, app_id, False, error_type, response_time_ms
                        )
                    
                    raise PrivateProfileError("Steam profile is private or friends-only")
                
                elif response.status == 401:
                    success = False
                    error_type = 'InvalidAPIKey'
                    if self.logger:
                        self.logger.error(f"Steam API request unauthorized (401): Invalid API key")
                    
                    # Track in database
                    if self.database and endpoint_name:
                        await self.database.increment_api_call(
                            endpoint_name, steam_id, app_id, False, error_type, response_time_ms
                        )
                    
                    raise InvalidAPIKeyError("Invalid Steam API key")
                
                elif response.status == 429:
                    success = False
                    error_type = 'RateLimit'
                    self.session_stats['rate_limit_hits'] += 1
                    if self.logger:
                        self.logger.warning(f"Steam API rate limit exceeded (429)")
                    
                    # Track in database
                    if self.database and endpoint_name:
                        await self.database.increment_api_call(
                            endpoint_name, steam_id, app_id, False, error_type, response_time_ms
                        )
                    
                    raise RateLimitError("Steam API rate limit exceeded")
                
                response.raise_for_status()
                result = await response.json()
                
                # Track successful call
                self.session_stats['successful_calls'] += 1
                if self.database and endpoint_name:
                    await self.database.increment_api_call(
                        endpoint_name, steam_id, app_id, True, None, response_time_ms
                    )
                
                return result
                
        except aiohttp.ClientError as e:
            success = False
            error_type = 'ClientError'
            self.session_stats['failed_calls'] += 1
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if self.logger:
                self.logger.error(f"Steam API request failed: {e}")
            
            # Track in database
            if self.database and endpoint_name:
                await self.database.increment_api_call(
                    endpoint_name, steam_id, app_id, False, error_type, response_time_ms
                )
            
            raise
    
    async def resolve_vanity_url(self, vanity_url: str) -> Dict[str, Any]:
        """
        Resolve a vanity URL to a Steam ID.
        
        :param vanity_url: Steam vanity URL
        :return: API response containing steamid
        """
        return await self._make_request(
            'ISteamUser/ResolveVanityURL',
            1,
            {'vanityurl': vanity_url},
            endpoint_name='resolve_vanity_url'
        )
    
    async def get_player_summaries(self, steam_ids: str) -> Dict[str, Any]:
        """
        Get player summaries for one or more Steam IDs.
        
        :param steam_ids: Comma-separated Steam IDs or single Steam ID
        :return: API response containing player information
        """
        # Extract first steam_id for tracking if multiple
        first_steam_id = steam_ids.split(',')[0] if steam_ids else None
        
        return await self._make_request(
            'ISteamUser/GetPlayerSummaries',
            2,
            {'steamids': steam_ids},
            endpoint_name='get_player_summaries',
            steam_id=first_steam_id
        )
    
    async def get_owned_games(self, steam_id: str, include_appinfo: bool = True, 
                             include_played_free_games: bool = True) -> Dict[str, Any]:
        """
        Get owned games for a Steam user.
        
        :param steam_id: Steam ID
        :param include_appinfo: Include game information
        :param include_played_free_games: Include free games
        :return: API response containing owned games
        """
        params = {
            'steamid': steam_id,
            'include_appinfo': 1 if include_appinfo else 0,
            'include_played_free_games': 1 if include_played_free_games else 0
        }
        return await self._make_request(
            'IPlayerService/GetOwnedGames',
            1,
            params,
            endpoint_name='get_owned_games',
            steam_id=steam_id
        )
    
    async def get_user_stats_for_game(self, steam_id: str, app_id: int) -> Dict[str, Any]:
        """
        Get user stats for a specific game.
        
        :param steam_id: Steam ID
        :param app_id: Application ID
        :return: API response containing user stats
        """
        return await self._make_request(
            'ISteamUserStats/GetUserStatsForGame',
            2,
            {'steamid': steam_id, 'appid': app_id},
            endpoint_name='get_user_stats_for_game',
            steam_id=steam_id,
            app_id=app_id
        )
    
    async def get_global_achievement_percentages(self, app_id: int) -> Dict[str, Any]:
        """
        Get global achievement percentages for a specific game.
        
        :param app_id: Application ID
        :return: API response containing global achievement percentages
        """
        return await self._make_request(
            'ISteamUserStats/GetGlobalAchievementPercentagesForApp',
            2,
            {'gameid': app_id},
            needKey=False,
            endpoint_name='get_global_achievement_percentages',
            app_id=app_id
        )
    
    async def get_player_achievements(self, steam_id: str, app_id: int) -> Dict[str, Any]:
        """
        Get player achievements for a specific game.
        
        :param steam_id: Steam ID
        :param app_id: Application ID
        :return: API response containing achievements
        """
        return await self._make_request(
            'ISteamUserStats/GetPlayerAchievements',
            1,
            {'steamid': steam_id, 'appid': app_id},
            endpoint_name='get_player_achievements',
            steam_id=steam_id,
            app_id=app_id
        )
    
    async def get_schema_for_game(self, app_id: int) -> Dict[str, Any]:
        """
        Get schema (achievements, stats) for a game.
        
        :param app_id: Application ID
        :return: API response containing game schema
        """
        return await self._make_request(
            'ISteamUserStats/GetSchemaForGame',
            2,
            {'appid': app_id},
            endpoint_name='get_schema_for_game',
            app_id=app_id
        )
    
    async def get_recently_played_games(self, steam_id: str, count: int = 0) -> Dict[str, Any]:
        """
        Get recently played games for a Steam user.
        
        :param steam_id: Steam ID
        :param count: Number of games to return (0 for all)
        :return: API response containing recently played games
        """
        params = {'steamid': steam_id}
        if count > 0:
            params['count'] = count
        
        return await self._make_request(
            'IPlayerService/GetRecentlyPlayedGames',
            1,
            params,
            endpoint_name='get_recently_played_games',
            steam_id=steam_id
        )
    
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics.
        
        :return: Dictionary with session statistics
        """
        avg_response_time = 0
        if self.session_stats['successful_calls'] > 0:
            avg_response_time = (
                self.session_stats['total_response_time_ms'] / 
                self.session_stats['total_calls']
            )
        
        return {
            **self.session_stats,
            'average_response_time_ms': round(avg_response_time, 2)
        }
    
    async def close(self):
        """Close the aiohttp session."""
        if not self._closed and self.session and not self.session.closed:
            await self.session.close()
            self._closed = True
            if self.logger:
                self.logger.debug("SteamWebAPI session closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()