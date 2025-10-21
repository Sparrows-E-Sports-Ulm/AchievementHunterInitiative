"""
OAuth2 Web Server for Steam Verification

This module provides a simple web server to handle Discord OAuth2 callbacks
for Steam account verification.
"""

from aiohttp import web
import asyncio
import logging
from typing import Optional, Dict
import os
from utils.steam_verification import SteamVerifier


class OAuth2CallbackServer:
    """
    Web server to handle OAuth2 callbacks for Steam verification.
    """
    
    def __init__(self, bot, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize the OAuth2 callback server.
        
        :param bot: The Discord bot instance
        :param host: Host to bind the server to
        :param port: Port to bind the server to
        """
        self.bot = bot
        self.host = host
        self.port = port
        self.logger = logging.getLogger(__name__)
        
        # Get OAuth2 credentials from environment or config
        self.client_id = os.getenv("DISCORD_CLIENT_ID", str(bot.application_id))
        self.client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        self.redirect_uri = os.getenv("DISCORD_REDIRECT_URI", f"http://localhost:{port}/callback")
        
        if not self.client_secret:
            self.logger.warning(
                "DISCORD_CLIENT_SECRET not set! OAuth2 verification will not work. "
                "Set the DISCORD_CLIENT_SECRET environment variable."
            )
        
        # Initialize verifier
        self.verifier = SteamVerifier(
            self.client_id,
            self.client_secret or "dummy",
            self.redirect_uri
        ) if self.client_secret else None
        
        # Store pending verifications (discord_id -> steam_id)
        self.pending_verifications: Dict[str, Dict] = {}
        
        # Create web app
        self.app = web.Application()
        self.setup_routes()
        
        self.runner: Optional[web.AppRunner] = None
    
    def setup_routes(self):
        """Set up web routes for OAuth2 callback."""
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_get('/callback', self.callback_handler)
        self.app.router.add_get('/verify', self.verify_start_handler)
    
    async def index_handler(self, request: web.Request) -> web.Response:
        """Handle root path."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Steam Verification</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #36393f;
                    color: #dcddde;
                }
                .container {
                    background-color: #2f3136;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                }
                h1 {
                    color: #7289da;
                }
                .button {
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #7289da;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-top: 20px;
                }
                .button:hover {
                    background-color: #677bc4;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎮 Steam Account Verification</h1>
                <p>Verify your Steam account ownership for the Achievement Hunter bot.</p>
                <p>This process will:</p>
                <ul>
                    <li>Check if you have linked Steam to your Discord account</li>
                    <li>Verify you own the Steam account you're registering</li>
                    <li>Automatically register you as an Achievement Hunter</li>
                </ul>
                <p><strong>Note:</strong> Make sure you have linked your Steam account in Discord first!</p>
                <p>Go to: Discord Settings → Connections → Add → Steam</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def verify_start_handler(self, request: web.Request) -> web.Response:
        """
        Start verification process.
        Redirects to Discord OAuth2 authorization.
        """
        if not self.verifier:
            return web.Response(
                text="OAuth2 is not configured. Please set DISCORD_CLIENT_SECRET.",
                status=500
            )
        
        # Redirect to Discord OAuth2
        oauth_url = self.verifier.get_oauth_url()
        raise web.HTTPFound(oauth_url)
    
    async def callback_handler(self, request: web.Request) -> web.Response:
        """Handle OAuth2 callback from Discord."""
        if not self.verifier:
            return self.error_response("OAuth2 is not configured")
        
        # Get authorization code
        code = request.query.get('code')
        error = request.query.get('error')
        
        if error:
            self.logger.error(f"OAuth2 error: {error}")
            return self.error_response(f"Authorization failed: {error}")
        
        if not code:
            return self.error_response("No authorization code received")
        
        try:
            # Exchange code for access token
            token_data = await self.verifier.exchange_code(code)
            
            if not token_data:
                return self.error_response("Failed to exchange authorization code")
            
            access_token = token_data.get('access_token')
            
            # Get user info
            user_info = await self.verifier.get_user_info(access_token)
            
            if not user_info:
                return self.error_response("Failed to fetch user information")
            
            discord_id = user_info.get('id')
            username = user_info.get('username')
            
            # Auto-detect Steam ID
            steam_id = await self.verifier.auto_detect_steam_id(access_token)
            
            if not steam_id:
                return self.error_response(
                    "No Steam account found! Please link your Steam account in Discord first."
                )
            
            # Try to register the user
            success, message = await self.register_user(discord_id, steam_id, username)
            
            if success:
                return self.success_response(steam_id, message)
            else:
                return self.error_response(message)
        
        except Exception as e:
            self.logger.error(f"Error in OAuth2 callback: {e}")
            return self.error_response(f"An error occurred: {str(e)}")
    
    async def register_user(
        self, 
        discord_id: str, 
        steam_id: str, 
        username: str
    ) -> tuple[bool, str]:
        """
        Register user in the database.
        
        :param discord_id: Discord user ID
        :param steam_id: Steam ID
        :param username: Discord username
        :return: Tuple of (success, message)
        """
        try:
            # Check if already registered
            existing_hunter = await self.bot.database.get_hunter_by_steam_id(steam_id)
            
            if existing_hunter:
                return False, "This Steam account is already registered!"
            
            # Check if Discord ID already has an account
            existing_by_discord = await self.bot.database.get_hunter_by_discord_id(discord_id)
            
            if existing_by_discord:
                return False, "Your Discord account is already registered with another Steam account!"
            
            # Verify Steam account exists and is public
            if not await self.bot.steamAPI.exists(steam_id):
                return False, "Steam account does not exist or is not accessible."
            
            # Get Steam profile
            steam_user = self.bot.steamAPI.create_user(steam_id)
            steam_profile = await steam_user.get_profile(force_refresh=True)
            
            # Check visibility
            visibility_state = steam_profile.get('communityvisibilitystate', 0)
            
            if visibility_state != 3:
                return False, (
                    "Your Steam profile must be public to register! "
                    "Please change your Steam privacy settings and try again."
                )
            
            # Register in database
            steam_name = steam_profile.get('personaname', username)
            await self.bot.database.add_hunter(
                steam_id=steam_id,
                steam_name=steam_name,
                discord_id=discord_id
            )
            
            # Add to calculation queue
            score_calculator = self.bot.get_cog("score_calculator")
            if score_calculator:
                await score_calculator.add_to_queue(steam_id)
            
            return True, f"Successfully registered as {steam_name}! Your score is being calculated."
        
        except Exception as e:
            self.logger.error(f"Error registering user: {e}")
            return False, f"Registration error: {str(e)}"
    
    def success_response(self, steam_id: str, message: str) -> web.Response:
        """Generate success HTML response."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Success</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #36393f;
                    color: #dcddde;
                }}
                .container {{
                    background-color: #2f3136;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    text-align: center;
                }}
                .success {{
                    color: #43b581;
                    font-size: 48px;
                }}
                h1 {{
                    color: #43b581;
                }}
                .steam-id {{
                    background-color: #202225;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Verification Successful!</h1>
                <p>{message}</p>
                <div class="steam-id">Steam ID: {steam_id}</div>
                <p>You can now close this window and return to Discord.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    def error_response(self, error_message: str) -> web.Response:
        """Generate error HTML response."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #36393f;
                    color: #dcddde;
                }}
                .container {{
                    background-color: #2f3136;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    text-align: center;
                }}
                .error {{
                    color: #f04747;
                    font-size: 48px;
                }}
                h1 {{
                    color: #f04747;
                }}
                .error-message {{
                    background-color: #202225;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                    border-left: 4px solid #f04747;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>Verification Failed</h1>
                <div class="error-message">{error_message}</div>
                <p>Please try again or use <code>/register</code> in Discord.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def start(self):
        """Start the web server."""
        if not self.verifier:
            self.logger.warning("OAuth2 server not starting - CLIENT_SECRET not configured")
            return
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        
        self.logger.info(f"OAuth2 callback server started on http://{self.host}:{self.port}")
        self.logger.info(f"Redirect URI: {self.redirect_uri}")
    
    async def stop(self):
        """Stop the web server."""
        if self.runner:
            await self.runner.cleanup()
            self.logger.info("OAuth2 callback server stopped")
