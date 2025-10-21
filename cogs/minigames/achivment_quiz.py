import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from typing import Dict, List, Set
from dataclasses import dataclass

@dataclass
class Achievement:
    name: str
    description: str
    game_name: str
    icon_url: str
    global_percentage: float = 0.0

class GameLobby:
    """Represents an active game lobby"""
    def __init__(self, channel_id: int, rounds: int = 3):
        self.channel_id = channel_id
        self.players: Set[int] = set()  # Discord user IDs
        self.scores: Dict[int, int] = {}  # user_id -> score
        self.current_round = 0
        self.total_rounds = rounds
        self.is_active = False
        self.is_game_started = False
        self.thread = None  # Reference to the thread

class JoinButton(discord.ui.Button):
    """Button to join the game lobby"""
    def __init__(self, lobby: GameLobby):
        super().__init__(style=discord.ButtonStyle.green, label="Join 🎮", custom_id="join_game")
        self.lobby = lobby

    async def callback(self, interaction: discord.Interaction):
        if self.lobby.is_game_started:
            await interaction.response.send_message(
                "❌ The game has already started!", ephemeral=True
            )
            return
        
        user_id = interaction.user.id
        if user_id in self.lobby.players:
            await interaction.response.send_message(
                "✅ You're already in the lobby!", ephemeral=True
            )
        else:
            self.lobby.players.add(user_id)
            self.lobby.scores[user_id] = 0
            await interaction.response.send_message(
                f"✅ You joined the lobby! Players: {len(self.lobby.players)}", 
                ephemeral=True
            )
            
            # Update the embed
            if interaction.message:
                embed = interaction.message.embeds[0]
                embed.set_field_at(
                    0, 
                    name="Players", 
                    value=f"{len(self.lobby.players)} players joined", 
                    inline=False
                )
                await interaction.message.edit(embed=embed)

class StartButton(discord.ui.Button):
    """Button to start the game"""
    def __init__(self, lobby: GameLobby, minigame_cog):
        super().__init__(style=discord.ButtonStyle.blurple, label="Start Game 🚀", custom_id="start_game")
        self.lobby = lobby
        self.minigame_cog = minigame_cog

    async def callback(self, interaction: discord.Interaction):
        if self.lobby.is_game_started:
            await interaction.response.send_message(
                "❌ The game is already running!", ephemeral=True
            )
            return
        
        if len(self.lobby.players) < 1:
            await interaction.response.send_message(
                "❌ At least 1 player is required!", ephemeral=True
            )
            return
        
        await interaction.response.send_message("🚀 Starting game...", ephemeral=True)
        self.lobby.is_game_started = True
        
        # Disable the view
        self.view.stop()
        for item in self.view.children:
            item.disabled = True
        await interaction.message.edit(view=self.view)
        
        # Start the game (use thread if available, otherwise channel)
        game_channel = self.lobby.thread if self.lobby.thread else interaction.channel
        await self.minigame_cog.run_game(game_channel, self.lobby)

class LobbyView(discord.ui.View):
    """View containing lobby buttons"""
    def __init__(self, lobby: GameLobby, minigame_cog, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.add_item(JoinButton(lobby))
        self.add_item(StartButton(lobby, minigame_cog))

class AnswerButton(discord.ui.Button):
    """Button for answering a question"""
    def __init__(self, game_name: str, is_correct: bool, callback_func):
        super().__init__(style=discord.ButtonStyle.secondary, label=game_name)
        self.game_name = game_name
        self.is_correct = is_correct
        self.callback_func = callback_func
        self.responders: Set[int] = set()

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # Check if user already answered
        if user_id in self.responders:
            await interaction.response.send_message(
                "❌ You already answered!", ephemeral=True
            )
            return
        
        self.responders.add(user_id)
        await self.callback_func(interaction, self.is_correct)


class QuestionLayout(discord.ui.LayoutView):
    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """
        Create a visual progress bar for the global achievement percentage.
        
        :param percentage: The percentage value (0-100)
        :param width: Width of the progress bar in characters
        :return: Formatted progress bar string
        """
        filled = int((percentage / 100) * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"{bar} {percentage:.2f}%"
    

    def __init__(self, games: List[str], correct_game: str, lobby: GameLobby, achievment: Achievement, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.lobby = lobby
        self.answered_users: Set[int] = set()
        self.correct_answers_count: int = 0  # Track only correct answers for scoring
        self.all_answered: asyncio.Event = asyncio.Event()  # Event to signal all players answered
        self.achievement = achievment
        self.games = games
        self.correct_game = correct_game
        self._build_layout()
        
    def _build_layout(self):
        """Build the layout for the current Achievement with answer buttons."""
        # Clear existing items
        self.clear_items()

        # Shuffle the games
        random.shuffle(self.games)

        # Row that contains the answer buttons
        action_row = discord.ui.ActionRow()

        container = discord.ui.Container(
            accent_colour=discord.Color.onyx_embed()
        )

        round_header = discord.ui.TextDisplay(f'### 🏆 Achievement Quiz - Round {self.lobby.current_round}/{self.lobby.total_rounds}')
        container.add_item(round_header)

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

        achievement_section = discord.ui.Section(
            discord.ui.TextDisplay(f'## {self.achievement.name}'),
            discord.ui.TextDisplay(f'_{self.achievement.description}_\n\n**Global Achievement Rate:**\n{self._create_progress_bar(self.achievement.global_percentage)}'),
            accessory=discord.ui.Thumbnail(media=self.achievement.icon_url)
        )

        container.add_item(achievement_section)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        # Add buttons for each game
        for game in self.games:
            is_correct = (game == self.correct_game)
            button = AnswerButton(game, is_correct, self.handle_answer)
            action_row.add_item(button)

        question = discord.ui.TextDisplay('-#' + ' **Which game does this achievement belong to?**')
        container.add_item(question)
        container.add_item(action_row)

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        footer = discord.ui.TextDisplay('-#' + ' You have 30 seconds to answer!')
        container.add_item(footer)
        self.add_item(container)

        
    async def handle_answer(self, interaction: discord.Interaction, is_correct: bool):
        user_id = interaction.user.id
        
        # Check if user is in the lobby
        if user_id not in self.lobby.players:
            await interaction.response.send_message(
                "❌ You're not part of this game!", ephemeral=True
            )
            return
        
        # Check if user already answered
        if user_id in self.answered_users:
            await interaction.response.send_message(
                "❌ You already answered!", ephemeral=True
            )
            return
        
        self.answered_users.add(user_id)
        
        if is_correct:
            # Award points based on correct answer position (not total answers)
            self.correct_answers_count += 1
            points = 100 - (self.correct_answers_count - 1) * 10
            points = max(points, 10)  # Minimum 10 points
            self.lobby.scores[user_id] = self.lobby.scores.get(user_id, 0) + points
            
            await interaction.response.send_message(
                f"✅ Correct! +{points} points! (Total: {self.lobby.scores[user_id]})", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Wrong! No points.", ephemeral=True
            )
    
        # Check if all players have answered
        if len(self.answered_users) >= len(self.lobby.players):
            self.all_answered.set()  # Signal that everyone answered
    
    async def on_timeout(self):
        # Disable all buttons when time runs out
        for container in self.children:
            if isinstance(container, discord.ui.Container):
                for item in container.children:
                    if isinstance(item, discord.ui.ActionRow):
                        for button in item.children:
                            if hasattr(button, 'disabled'):
                                button.disabled = True


class AchivmentQuiz(commands.Cog, name="achivment_quiz"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_lobbies: Dict[int, GameLobby] = {}  # channel_id -> GameLobby

    @app_commands.command(
        name="achievement-quiz",
        description="Start an Achievement Quiz minigame"
    )
    @app_commands.describe(
        rounds="Number of rounds (default: 3)"
    )
    async def achievement_quiz(
        self,
        interaction: discord.Interaction,
        rounds: int = 3
    ) -> None:
        """
        Start an Achievement Quiz minigame.
        
        :param interaction: The interaction that triggered the command.
        :param rounds: Number of rounds to play (default: 3).
        """
        channel_id = interaction.channel_id
        
        # Check if there's already an active lobby in this channel
        if channel_id in self.active_lobbies and self.active_lobbies[channel_id].is_active:
            return await interaction.response.send_message(
                "❌ There's already a game running in this channel!", ephemeral=True
            )
        
        # Validate rounds
        if rounds < 1 or rounds > 10:
            return await interaction.response.send_message(
                "❌ Rounds must be between 1 and 10!", ephemeral=True
            )
        
        # Defer the response since we're creating a thread
        await interaction.response.defer()
        
        try:
            # Create a public thread for the game
            thread = await interaction.channel.create_thread(
                name=f"🎮 Achievement Quiz - {interaction.user.display_name}",
                auto_archive_duration=60,  # Archive after 60 minutes of inactivity
                type=discord.ChannelType.public_thread,  # Make it a public thread
                reason="Achievement Quiz Minigame"
            )
            
            # Create new lobby (use thread id instead of channel id)
            lobby = GameLobby(thread.id, rounds)
            lobby.is_active = True
            lobby.thread = thread
            self.active_lobbies[thread.id] = lobby
            
            # Create lobby embed
            embed = discord.Embed(
                title="🎮 Achievement Quiz Lobby",
                description=(
                    f"**Rounds:** {rounds}\n\n"
                    "**How it works:**\n"
                    "1️⃣ Join the lobby\n"
                    "2️⃣ The host starts the game\n"
                    "3️⃣ Guess the correct game for each achievement\n"
                    "4️⃣ Earn points for correct answers!\n\n"
                    "**Point System:**\n"
                    "🥇 First correct answer: 100 points\n"
                    "🥈 Second correct answer: 90 points\n"
                    "🥉 Third correct answer: 80 points\n"
                    "... and so on (minimum 10 points)"
                ),
                color=discord.Color.blue()
            )
            embed.add_field(name="Players", value="0 players joined", inline=False)
            embed.set_footer(text="⏰ Lobby closes in 3 minutes")
            
            # Create view with buttons
            view = LobbyView(lobby, self, timeout=180)
            
            # Send lobby message in the thread
            await thread.send(embed=embed, view=view)
            
            # Send confirmation in main channel
            await interaction.followup.send(
                f"✅ Achievement Quiz started! {thread.mention}",
                ephemeral=False
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to create threads!", ephemeral=True
            )
        except Exception as e:
            self.bot.logger.error(f"Error creating thread for minigame: {e}")
            await interaction.followup.send(
                "❌ Error creating game thread!", ephemeral=True
            )

    async def run_game(self, channel: discord.TextChannel | discord.Thread, lobby: GameLobby):
        """
        Run the actual game rounds.
        
        :param channel: The channel or thread to send messages to.
        :param lobby: The game lobby.
        """
        try:
            # Welcome message
            welcome_embed = discord.Embed(
                title="🚀 Game Starting!",
                description=f"**{len(lobby.players)} players** are participating.\nGood luck! 🍀",
                color=discord.Color.green()
            )
            await channel.send(embed=welcome_embed)
            await asyncio.sleep(3)
            
            for round_num in range(1, lobby.total_rounds + 1):
                lobby.current_round = round_num
                # Get random achievement
                achievement_data = await self.get_random_achievement()
                
                if not achievement_data:
                    await channel.send("❌ Error loading achievement. Skipping round.")
                    continue


                self.bot.logger.info(achievement_data)
                
                achievement_name = achievement_data['achievement_name']
                achievement_desc = achievement_data['achievement_desc']
                correct_game = achievement_data['game_name']
                wrong_games = achievement_data['wrong_games']
                achievement_icon = achievement_data.get('achievement_icon')  # Get icon URL

                # Create the Achievement View and send it
                questionView = QuestionLayout(
                    games=[correct_game] + wrong_games,
                    correct_game=correct_game,
                    lobby=lobby,
                    achievment=Achievement(
                        name=achievement_name,
                        description=achievement_desc,
                        game_name=correct_game,
                        icon_url=achievement_icon or "",
                        global_percentage=achievement_data.get("global_percentage", 0.0)
                    ),
                    timeout=30
                )
                message = await channel.send(view=questionView)
                
                # Wait for either timeout or all players to answer
                try:
                    await asyncio.wait_for(questionView.all_answered.wait(), timeout=30)
                    # All players answered before timeout
                except asyncio.TimeoutError:
                    # Timeout reached, some players didn't answer
                    pass
                
                # Show correct answer
                result_embed = discord.Embed(
                    title="✅ Correct Answer",
                    description=f"The achievement **{achievement_name}** belongs to:\n\n**{correct_game}**",
                    color=discord.Color.green()
                )
                await channel.send(embed=result_embed)
                
                # Disable buttons
                await questionView.on_timeout()
                await message.edit(view=questionView)
                
                # Wait before next round
                if round_num < lobby.total_rounds:
                    await asyncio.sleep(5)
            
            # Game finished - show results
            await self.show_results(channel, lobby)
            
        except Exception as e:
            self.bot.logger.error(f"Error in minigame: {e}")
            await channel.send("❌ An error occurred. The game has been terminated.")
        finally:
            # Clean up
            if lobby.channel_id in self.active_lobbies:
                del self.active_lobbies[lobby.channel_id]

    async def get_random_achievement(self) -> Dict | None:
        """
        Get a random achievement from a random hunter.
        
        :return: Dictionary with achievement data or None if failed.
        """
        try:
            # Get random hunter with score > 0
            hunter = await self.bot.database.get_random_hunter_with_score()
            
            if not hunter:
                self.bot.logger.error("No hunters with score > 0 found")
                return None
            
            steam_id = hunter['steam_id']
            steam_user = self.bot.steamAPI.create_user(steam_id)
            
            # Get games
            games_data = await steam_user.get_games()
            games = games_data.get('response', {}).get('games', [])
            
            if not games:
                self.bot.logger.error(f"No games found for hunter {steam_id}")
                return None
            
            # Try to find a game with achievements (max 10 attempts)
            for _ in range(10):
                random_game = random.choice(games)
                app_id = random_game['appid']
                game_name = random_game['name']
                
                # Get achievements for this game
                achievements_data = await steam_user.get_game_achievements(app_id)
                
                if not achievements_data:
                    continue
                
                achievements = achievements_data.get('playerstats', {}).get('achievements', [])
                
                # Filter for achieved achievements
                achieved = [ach for ach in achievements if ach.get('achieved') == 1]
                
                if not achieved:
                    continue
                
                # Pick a random achieved achievement
                achievement = random.choice(achieved)
                achievement_name = achievement.get('name', 'Unknown Achievement')
                achievement_icon_hash = achievement.get('icon', '')  # Get icon hash
                
                # Construct icon URL if hash is available
                achievement_icon_url = None
                if achievement_icon_hash:
                    # Steam CDN URL format for achievement icons
                    achievement_icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{achievement_icon_hash}.jpg"
                
                # Try to get description from schema
                achievement_desc = None
                try:
                    schema = await self.bot.steamAPI.web_api.get_schema_for_game(app_id)
                    schema_achievements = schema.get('game', {}).get('availableGameStats', {}).get('achievements', [])
                    
                    for sch_ach in schema_achievements:
                        if sch_ach.get('name') == achievement.get('apiname'):
                            achievement_desc = sch_ach.get('description', '')
                            achievement_name = sch_ach.get('displayName', achievement_name)
                            # Also try to get better quality icon from schema if available
                            if sch_ach.get('icon'):
                                achievement_icon_url = sch_ach.get('icon')
                            break
                except:
                    pass

                # Try to get the global achievement percentage
                try:
                    global_percentage = await self.bot.steamAPI.get_global_achievement_percentage(app_id, achievement.get('apiname'))
                    # Ensure it's a float
                    global_percentage = float(global_percentage) if global_percentage is not None else 0.0
                except Exception as e:
                    self.bot.logger.error(f"Error getting global achievement percentage: {e}")
                    global_percentage = 0.0
                
                # Get 3 wrong games
                other_games = [g for g in games if g['appid'] != app_id and 'name' in g]
                if len(other_games) < 3:
                    # Not enough games, try again
                    continue
                
                wrong_games = random.sample(other_games, 3)
                wrong_game_names = [g['name'] for g in wrong_games]
                
                return {
                    'achievement_name': achievement_name,
                    'achievement_desc': achievement_desc or 'No description available',
                    "global_percentage": global_percentage,
                    'game_name': game_name,
                    'wrong_games': wrong_game_names,
                    'achievement_icon': achievement_icon_url
                }
            
            self.bot.logger.error("Could not find a suitable achievement after 10 attempts")
            return None
            
        except Exception as e:
            self.bot.logger.error(f"Error getting random achievement: {e}")
            return None

    async def show_results(self, channel: discord.TextChannel | discord.Thread, lobby: GameLobby):
        """
        Show final game results.
        
        :param channel: The channel or thread to send the results to.
        :param lobby: The game lobby.
        """
        # Sort players by score
        sorted_players = sorted(
            lobby.scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Create results embed
        embed = discord.Embed(
            title="🏁 Game Finished - Final Results",
            description=f"**{lobby.total_rounds} rounds played**",
            color=discord.Color.gold()
        )
        
        # Add leaderboard
        leaderboard_text = ""
        for idx, (user_id, score) in enumerate(sorted_players, 1):
            user = await self.bot.fetch_user(user_id)
            
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"#{idx}"
            
            leaderboard_text += f"{medal} **{user.display_name}** - {score} points\n"
        
        if leaderboard_text:
            embed.add_field(
                name="🏆 Leaderboard",
                value=leaderboard_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 Leaderboard",
                value="No participants scored points.",
                inline=False
            )
        
        embed.set_footer(text="Thanks for playing! Use /achievement-quiz to start a new game.")
        
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AchivmentQuiz(bot))
