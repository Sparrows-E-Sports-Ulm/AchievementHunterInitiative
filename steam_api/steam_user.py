from .steam_web_api import SteamWebAPI, PrivateProfileError, InvalidAPIKeyError, RateLimitError, SteamAPIError
import traceback
import asyncio
from typing import Optional, Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .steam_web_api import SteamWebAPI

class SteamUser:
    """
    A comprehensive Steam User class that encapsulates all user-related functionality.
    
    This class allows you to create a user object and retrieve all necessary user data
    through a clean, object-oriented interface.
    """
    
    def __init__(self, api_key: str, identifier: str, logger = None, web_api: 'SteamWebAPI' = None):
        """
        Initialize a SteamUser object.
        
        :param api_key: Steam Web API key
        :param identifier: Steam ID or vanity URL
        :param logger: Optional logger instance
        :param web_api: Optional shared SteamWebAPI instance (recommended to share sessions)
        """
        if not api_key:
            raise ValueError("Steam API key is required")
        if not identifier:
            raise ValueError("User identifier (Steam ID or vanity URL) is required")
            
        self.api_key = api_key
        self.identifier = identifier
        self._steam_id: Optional[str] = None
        self._profile_data: Optional[Dict] = None
        self._games_data: Optional[Dict] = None
        
        # Use shared web_api if provided, otherwise create a new one
        self._owns_web_api = web_api is None
        self.web_api = web_api if web_api else SteamWebAPI(api_key, logger=logger)

        self.logger = logger 
    
    async def _ensure_steam_id(self) -> str:
        """
        Ensures we have a valid Steam ID, converting from vanity URL if necessary.
        
        :return: Steam ID
        """
        if self._steam_id:
            return self._steam_id
            
        if self.identifier.isdigit():
            self._steam_id = self.identifier
        else:
            steam_id = await self._vanity_to_steamid(self.identifier)
            if not steam_id:
                raise ValueError(f"Could not resolve vanity URL: {self.identifier}")
            self._steam_id = await self._vanity_to_steamid(self.identifier)
            
        return self._steam_id
    
    async def _vanity_to_steamid(self, vanity_url: str) -> str | None:
        """
        Converts a Steam vanity URL to a Steam ID.
        
        :param vanity_url: The vanity URL of the Steam user
        :return: The corresponding Steam ID
        """
        try:
            self.logger.debug(f"Resolving vanity URL: {vanity_url}")
            response = await self.web_api.resolve_vanity_url(vanity_url)

            if response['response']['success'] != 1:
                return None

            return response['response']['steamid']
        except Exception as e:
            error_msg = f"Error resolving vanity URL '{vanity_url}': {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise ValueError(error_msg)
           
    async def exists(self) -> bool:
        """
        Checks if this Steam user exists.
        
        :return: True if the user exists, False otherwise
        """
        try:
            steam_id = await self._ensure_steam_id()
            self.logger.debug(f"Checking if user exists with Steam ID: {steam_id}")
            response = await self.web_api.get_player_summaries(steam_id)
            self.logger.debug(f"Player summaries response: {response}")
            return len(response['response']['players']) > 0
        except Exception as e:
            self.logger.error(f"Error checking if user exists: {str(e)}")
            return False
        
    async def get_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches the player profile data.
        
        :param force_refresh: If True, forces a fresh API call instead of using cached data
        :return: A dictionary containing the player's profile information
        :raises PrivateProfileError: If the profile is private
        """
        if self._profile_data and not force_refresh:
            return self._profile_data
            
        try:
            steam_id = await self._ensure_steam_id()
            self.logger.debug(f"Fetching profile for Steam ID: {steam_id}")
            response = await self.web_api.get_player_summaries(steam_id)
            self.logger.debug(f"Profile response: {response}")
            players = response['response']['players']
            
            if not players:
                error_msg = f"No player found with Steam ID: {steam_id}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            self._profile_data = players[0]
            return self._profile_data
        except PrivateProfileError:
            # Re-raise private profile errors
            raise
        except Exception as e:
            error_msg = f"Error fetching player profile: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(error_msg)

    async def get_games(self, force_refresh: bool = False, include_free_games: bool = True) -> Dict[str, Any]:
        """
        Fetches the list of games owned by the player.
        
        :param force_refresh: If True, forces a fresh API call instead of using cached data
        :param include_free_games: If True, includes free-to-play games
        :return: A dictionary containing the list of games owned by the player
        :raises PrivateProfileError: If the profile is private
        """
        if self._games_data and not force_refresh:
            return self._games_data
            
        try:
            steam_id = await self._ensure_steam_id()
            self.logger.debug(f"Fetching games for Steam ID: {steam_id}, include_free_games: {include_free_games}")
            response = await self.web_api.get_owned_games(
                steam_id=steam_id, 
                include_appinfo=True,
                include_played_free_games=include_free_games
            )
            self.logger.debug(f"Games response: {response}")
            self._games_data = response
            return self._games_data
            
        except PrivateProfileError:
            # Re-raise private profile errors
            self.logger.warning(f"Cannot fetch games for {steam_id}: Profile is private")
            raise
        except Exception as e:
            error_msg = f"Error fetching player games: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(error_msg)
    
    async def get_game_achievements(self, app_id: int) -> Dict[str, Any] | None:
        """
        Fetches the player's achievements for a specific game.
        
        :param app_id: The App ID of the game
        :return: A dictionary containing the player's achievements for the specified game, or None if not accessible
        """
        try:
            steam_id = await self._ensure_steam_id()
            # Yield control to event loop before API call
            await asyncio.sleep(0)
            
            response = await self.web_api.get_player_achievements(
                steam_id=steam_id, 
                app_id=app_id
            )
            
            return response
            
        except (PrivateProfileError, RateLimitError) as e:
            # Silent fail for private profiles or rate limits on individual games
            self.logger.debug(f"Cannot fetch achievements for app {app_id}: {str(e)}")
            return None
        except Exception as e:
            self.logger.debug(f"Error fetching achievements for app {app_id}: {str(e)}")
            return None
    
    async def get_global_achievement_percentages(self, app_id: int) -> Dict[str, Any]:
        """
        Fetches global achievement percentages for a specific game.
        
        :param app_id: The App ID of the game
        :return: A dictionary containing global achievement percentages
        """
        try:
            # Yield control to event loop before API call
            await asyncio.sleep(0)
            
            response = await self.web_api.get_global_achievement_percentages(app_id=app_id)
            
            return response
            
        except Exception as e:
            self.logger.debug(f"Error fetching global achievements for app {app_id}: {str(e)}")
            return {'achievementpercentages': {'achievements': []}}
    
    async def get_game_stats(self, app_id: int) -> Dict[str, Any]:
        """
        Fetches the player's stats for a specific game.
        
        :param app_id: The App ID of the game
        :return: A dictionary containing the player's stats for the specified game
        """
        try:
            steam_id = await self._ensure_steam_id()
            response = await self.web_api.get_user_stats_for_game(
                steam_id=steam_id, 
                app_id=app_id
            )
            return response
            
        except Exception as e:
            raise Exception(f"Error fetching stats for app {app_id}: {str(e)}")
    
    async def get_recent_games(self, count: int = 10) -> Dict[str, Any]:
        """
        Fetches recently played games.
        
        :param count: Number of recent games to fetch
        :return: A dictionary containing recently played games
        """
        try:
            steam_id = await self._ensure_steam_id()
            response = await self.web_api.get_recently_played_games(
                steam_id=steam_id, 
                count=count
            )
            return response
            
        except Exception as e:
            raise Exception(f"Error fetching recent games: {str(e)}")
    
    async def get_all_user_data(self) -> Dict[str, Any]:
        """
        Fetches comprehensive user data including profile, games, and basic stats.
        
        :return: A dictionary containing all available user data
        """
        try:
            # Fetch all basic data
            profile = await self.get_profile()
            games = await self.get_games()
            recent_games = await self.get_recent_games()
            
            return {
                'steam_id': await self.steam_id,
                'profile': profile,
                'games': games,
                'recent_games': recent_games,
                'total_games': len(games.get('response', {}).get('games', [])),
                'account_created': profile.get('timecreated'),
                'last_logoff': profile.get('lastlogoff'),
                'profile_url': profile.get('profileurl'),
                'avatar': {
                    'small': profile.get('avatar'),
                    'medium': profile.get('avatarmedium'),
                    'large': profile.get('avatarfull')
                }
            }
        except Exception as e:
            raise Exception(f"Error fetching comprehensive user data: {str(e)}")
    
    async def _process_game_batch(self, games_batch: List[Dict], batch_num: int, total_batches: int) -> tuple[int, int]:
        """
        Process a batch of games in parallel.
        
        :param games_batch: List of games to process
        :param batch_num: Current batch number
        :param total_batches: Total number of batches
        :return: Tuple of (score, achievements_count) for this batch
        :raises PrivateProfileError: If a private profile error is detected
        """
        self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(games_batch)} games)")
        
        batch_score = 0
        batch_achievements = 0
        
        # Process games in this batch concurrently
        tasks = []
        for game in games_batch:
            app_id = game['appid']
            tasks.append(self._calculate_game_score(app_id))
        
        # Wait for all games in batch to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sum up the results and check for private profile errors
        for result in results:
            if isinstance(result, PrivateProfileError):
                # If we encounter a private profile error, raise it immediately
                self.logger.error("Private profile error detected in batch - aborting calculation")
                raise result
            if isinstance(result, Exception):
                # Other exceptions are logged but don't stop the calculation
                continue
            if result:
                score, achievements = result
                batch_score += score
                batch_achievements += achievements
        
        return batch_score, batch_achievements
    
    async def _calculate_game_score(self, app_id: int) -> Optional[tuple[int, int]]:
        """
        Calculate the score for a single game.
        
        :param app_id: The App ID of the game
        :return: Tuple of (score, achievements_count) or None if failed
        :raises PrivateProfileError: If profile becomes private during calculation
        """
        try:
            # Fetch both achievements and global percentages in parallel
            achievements_task = self.get_game_achievements(app_id)
            global_task = self.get_global_achievement_percentages(app_id)
            
            achievements_data, global_data = await asyncio.gather(
                achievements_task, 
                global_task,
                return_exceptions=True
            )
            
            # Check for private profile errors specifically
            if isinstance(achievements_data, PrivateProfileError):
                self.logger.error(f"Private profile error on game {app_id}")
                raise achievements_data
            
            # Handle other errors from either request
            if isinstance(achievements_data, Exception) or isinstance(global_data, Exception):
                self.logger.debug(f"Skipping game {app_id} - API error")
                return None
            
            if achievements_data is None:
                self.logger.debug(f"No achievements data for app {app_id}")
                return None
            
            player_achievements = achievements_data.get("playerstats", {}).get('achievements', [])
            if not player_achievements:
                return None
            
            global_achievements = global_data.get('achievementpercentages', {}).get('achievements', [])
            global_map = {ach['name']: ach['percent'] for ach in global_achievements}
            
            # Calculate score for this game
            game_score = 0
            game_achievements = 0
            
            for achievement in player_achievements:
                if achievement.get('achieved') == 1:
                    ach_name = achievement['apiname']
                    global_percent = int(float(global_map.get(ach_name, 100.0)))
                    
                    game_achievements += 1
                    if global_percent > 0:
                        score = (100 - global_percent)
                        game_score += score
            
            if game_achievements > 0:
                self.logger.debug(f"Game {app_id}: {game_achievements} achievements, {game_score} points")
            
            return game_score, game_achievements
            
        except PrivateProfileError:
            # Re-raise private profile errors to abort calculation
            raise
        except Exception as e:
            self.logger.debug(f"Error calculating score for game {app_id}: {e}")
            return None

    async def calculate_achievement_score(self, batch_size: int = 10) -> tuple[int, int]:
        """
        Calculates an achievement score based on the user's achievements across all games.
        Uses batch processing and parallel API calls for better performance.
        
        :param batch_size: Number of games to process in parallel per batch
        :return: Tuple of (total_score, total_achievements)
        :raises PrivateProfileError: If profile is private or game details are not accessible
        """
        try:
            games_data = await self.get_games()
            games = games_data.get('response', {}).get('games', [])
            
            if not games:
                self.logger.info("No games found for user")
                return 0, 0
            
            self.logger.info(f"Starting score calculation for {len(games)} games (batch size: {batch_size})")
            
            total_score = 0
            total_achievements = 0
            
            # Split games into batches
            batches = [games[i:i + batch_size] for i in range(0, len(games), batch_size)]
            total_batches = len(batches)
            
            # Process each batch sequentially (but games within batch are parallel)
            for batch_num, batch in enumerate(batches, 1):
                try:
                    batch_score, batch_achievements = await self._process_game_batch(
                        batch, batch_num, total_batches
                    )
                    total_score += batch_score
                    total_achievements += batch_achievements
                except PrivateProfileError:
                    # If we hit a private profile error during calculation, abort immediately
                    self.logger.error(f"Private profile detected during score calculation - aborting")
                    raise
                
                # Yield control between batches
                await asyncio.sleep(0.1)
                
                # Log progress
                games_processed = batch_num * batch_size
                if games_processed > len(games):
                    games_processed = len(games)
                progress = (games_processed / len(games)) * 100
                self.logger.info(
                    f"Progress: {games_processed}/{len(games)} games ({progress:.1f}%) - "
                    f"Current score: {total_score}, Achievements: {total_achievements}"
                )
            
            self.logger.info(
                f"Score calculation complete! Total score: {total_score}, "
                f"Total achievements: {total_achievements}"
            )
            
            return total_score, total_achievements
            
        except PrivateProfileError:
            # Re-raise private profile errors
            raise
        except Exception as e:
            error_msg = f"Error calculating achievement score: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(error_msg)
    
    def __str__(self) -> str:
        """String representation of the SteamUser object."""
        return f"SteamUser(identifier='{self.identifier}')"
    
    def __repr__(self) -> str:
        """Detailed string representation of the SteamUser object."""
        return f"SteamUser(api_key='***', identifier='{self.identifier}', steam_id='{self._steam_id}')"
    
    async def close(self):
        """Close all API connections (only if we own the web_api instance)."""
        if self._owns_web_api and self.web_api:
            await self.web_api.close()