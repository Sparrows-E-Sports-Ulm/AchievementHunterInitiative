"""
Steam Account Verification via Discord Connections

This module handles Steam account verification by checking if a user has
linked their Steam account to Discord and if it matches the claimed Steam ID.
"""

import aiohttp
from typing import Optional, Dict, List
import logging


class SteamVerificationError(Exception):
    """Base exception for Steam verification errors."""
    pass


class NoSteamConnectionError(SteamVerificationError):
    """Raised when user has no Steam connection in Discord."""
    pass


class SteamIDMismatchError(SteamVerificationError):
    """Raised when claimed Steam ID doesn't match Discord connection."""
    pass


class SteamVerifier:
    """
    Handles Steam account verification via Discord OAuth2 connections.
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize the Steam Verifier.
        
        :param client_id: Discord application client ID
        :param client_secret: Discord application client secret
        :param redirect_uri: OAuth2 redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.logger = logging.getLogger(__name__)
        
        # Discord API endpoints
        self.token_url = "https://discord.com/api/v10/oauth2/token"
        self.connections_url = "https://discord.com/api/v10/users/@me/connections"
        self.user_url = "https://discord.com/api/v10/users/@me"
    
    def get_oauth_url(self) -> str:
        """
        Generate OAuth2 authorization URL.
        
        :return: OAuth2 URL for user to authorize
        """
        return (
            f"https://discord.com/api/oauth2/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"scope=identify%20connections"
        )
    
    async def exchange_code(self, code: str) -> Optional[Dict]:
        """
        Exchange OAuth2 authorization code for access token.
        
        :param code: Authorization code from OAuth2 callback
        :return: Token data including access_token and refresh_token
        """
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=data, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Token exchange failed: {error_text}")
                        return None
        except Exception as e:
            self.logger.error(f"Error exchanging code: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """
        Get user information from Discord API.
        
        :param access_token: OAuth2 access token
        :return: User information including ID and username
        """
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.user_url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching user info: {e}")
            return None
    
    async def get_connections(self, access_token: str) -> List[Dict]:
        """
        Get user's connected accounts from Discord.
        
        :param access_token: OAuth2 access token
        :return: List of connection objects
        """
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.connections_url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch connections: {error_text}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching connections: {e}")
            return []
    
    async def get_steam_connection(self, access_token: str) -> Optional[Dict]:
        """
        Get user's Steam connection from Discord.
        
        :param access_token: OAuth2 access token
        :return: Steam connection object or None if not found
        """
        connections = await self.get_connections(access_token)
        
        for connection in connections:
            if connection.get('type') == 'steam':
                return connection
        
        return None
    
    async def verify_steam_ownership(
        self, 
        access_token: str, 
        claimed_steam_id: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Verify that a user owns the claimed Steam account.
        
        :param access_token: OAuth2 access token
        :param claimed_steam_id: The Steam ID the user claims to own
        :return: Tuple of (is_verified, actual_steam_id, error_message)
        """
        try:
            # Get Steam connection
            steam_connection = await self.get_steam_connection(access_token)
            
            if not steam_connection:
                return False, None, "No Steam account linked to your Discord account"
            
            # Get the Steam ID from connection
            connected_steam_id = steam_connection.get('id')
            
            if not connected_steam_id:
                return False, None, "Could not retrieve Steam ID from Discord connection"
            
            # Verify it matches the claimed ID
            # Convert to string for comparison (both 64-bit Steam IDs)
            if str(connected_steam_id) == str(claimed_steam_id):
                return True, connected_steam_id, None
            else:
                return False, connected_steam_id, (
                    f"Steam ID mismatch!\n"
                    f"Your Discord is linked to Steam ID: `{connected_steam_id}`\n"
                    f"But you tried to register: `{claimed_steam_id}`"
                )
        
        except Exception as e:
            self.logger.error(f"Error verifying Steam ownership: {e}")
            return False, None, f"Verification error: {str(e)}"
    
    async def auto_detect_steam_id(self, access_token: str) -> Optional[str]:
        """
        Automatically detect user's Steam ID from Discord connections.
        
        :param access_token: OAuth2 access token
        :return: Steam ID if found, None otherwise
        """
        steam_connection = await self.get_steam_connection(access_token)
        
        if steam_connection:
            return steam_connection.get('id')
        
        return None


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_verification():
        # These would come from environment variables or config
        CLIENT_ID = "your_client_id"
        CLIENT_SECRET = "your_client_secret"
        REDIRECT_URI = "http://localhost:8080/callback"
        
        verifier = SteamVerifier(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
        
        # Generate OAuth URL
        print("OAuth URL:", verifier.get_oauth_url())
        
        # After user authorizes, you get a code
        # code = "example_code_from_callback"
        # token_data = await verifier.exchange_code(code)
        # access_token = token_data['access_token']
        
        # Verify Steam ownership
        # is_verified, steam_id, error = await verifier.verify_steam_ownership(
        #     access_token,
        #     claimed_steam_id="76561198000000000"
        # )
        
        # if is_verified:
        #     print(f"✅ Verified! Steam ID: {steam_id}")
        # else:
        #     print(f"❌ Verification failed: {error}")
    
    asyncio.run(test_verification())
