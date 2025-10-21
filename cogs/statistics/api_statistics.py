"""
API Statistics Cog - Displays Steam API usage statistics.

This module provides the /statistics command that shows comprehensive API usage
data including daily limits, call counts, error rates, and performance metrics.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import date, datetime, timedelta
from typing import Optional

from utils.message_views import MessageView


class APIStatistics(commands.Cog, name="statistics"):
    """
    Cog for displaying Steam API usage statistics.
    
    Tracks API calls, monitors daily limits, and provides insights into
    API performance and error rates.
    """
    
    # Steam API daily limit
    DAILY_API_LIMIT = 100000
    
    def __init__(self, bot) -> None:
        """
        Initialize the API Statistics cog.
        
        :param bot: The Discord bot instance.
        """
        self.bot = bot
        self.lang = bot.language_manager
    
    
    @app_commands.command(
        name="statistics",
        description="View Steam API usage statistics and performance metrics"
    )
    @app_commands.guilds(discord.Object(id=1418008309583319184))
    @app_commands.describe(
        period="Statistics period: today, week, month, or all (default: today)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="This Week", value="week"),
        app_commands.Choice(name="This Month", value="month"),
        app_commands.Choice(name="All Time", value="all")
    ])
    async def statistics(
        self,
        interaction: discord.Interaction,
        period: str = "today"
    ) -> None:
        """
        Display Steam API usage statistics.
        
        Shows comprehensive information about API usage including:
        - Total API calls and daily limit progress
        - Success/failure rates
        - Most called endpoints
        - Average response times
        - Error breakdown
        
        :param interaction: The Discord interaction that triggered this command.
        :param period: Time period for statistics (today, week, month, all)
        """
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get statistics based on period
            if period == "today":
                stats = await self._get_today_stats()
                title = "📊 Steam API Statistics - Today"
                color = self._get_usage_color(stats.get('total_calls', 0))
            elif period == "week":
                stats = await self._get_period_stats(days=7)
                title = "📊 Steam API Statistics - This Week"
                color = discord.Color.blue()
            elif period == "month":
                stats = await self._get_period_stats(days=30)
                title = "📊 Steam API Statistics - This Month"
                color = discord.Color.blue()
            else:  # all
                stats = await self._get_all_time_stats()
                title = "📊 Steam API Statistics - All Time"
                color = discord.Color.purple()
            
            # Create embed
            embed = discord.Embed(
                title=title,
                description=self._get_description(period, stats),
                color=color,
                timestamp=datetime.utcnow()
            )
            
            # Add fields based on available data
            self._add_statistics_fields(embed, stats, period)
            
            # Add footer
            embed.set_footer(
                text=f"Steam API Daily Limit: {self.DAILY_API_LIMIT:,} calls • Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.bot.logger.error(f"Error fetching API statistics: {e}")
            await interaction.followup.send(
                view=MessageView(
                    colour=discord.Color.red(),
                    message="❌ Failed to fetch API statistics. Please try again later."
                )
            )
    
    
    async def _get_today_stats(self) -> dict:
        """Get statistics for today."""
        stats_row = await self.bot.database.get_api_statistics_today()
        
        if not stats_row:
            return {'total_calls': 0, 'no_data': True}
        
        # Convert Row to dict
        stats = dict(stats_row)
        
        # Add session stats
        session_stats = self.bot.steamAPI.web_api.get_session_stats()
        stats['session_stats'] = session_stats
        
        # Calculate percentage of daily limit
        stats['usage_percentage'] = (stats['total_calls'] / self.DAILY_API_LIMIT) * 100
        
        # Get additional metrics
        stats['calls_last_hour'] = await self.bot.database.get_api_calls_recent(hours=1)
        stats['avg_response_time'] = await self.bot.database.get_average_response_time()
        
        return stats
    
    
    async def _get_period_stats(self, days: int) -> dict:
        """Get aggregated statistics for a period."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        stats_rows = await self.bot.database.get_api_statistics_range(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=days
        )
        
        if not stats_rows:
            return {'total_calls': 0, 'no_data': True}
        
        # Aggregate statistics
        aggregated = {
            'total_calls': 0,
            'failed_calls': 0,
            'rate_limit_hits': 0,
            'private_profile_errors': 0,
            'days_with_data': len(stats_rows)
        }
        
        for row in stats_rows:
            aggregated['total_calls'] += row['total_calls']
            aggregated['failed_calls'] += row['failed_calls']
            aggregated['rate_limit_hits'] += row['rate_limit_hits']
            aggregated['private_profile_errors'] += row['private_profile_errors']
        
        # Calculate success rate
        if aggregated['total_calls'] > 0:
            successful = aggregated['total_calls'] - aggregated['failed_calls']
            aggregated['success_rate'] = (successful / aggregated['total_calls']) * 100
            aggregated['avg_calls_per_day'] = aggregated['total_calls'] / aggregated['days_with_data']
        
        aggregated['avg_response_time'] = await self.bot.database.get_average_response_time()
        
        return aggregated
    
    
    async def _get_all_time_stats(self) -> dict:
        """Get all-time statistics."""
        total_calls = await self.bot.database.get_total_api_calls()
        
        if total_calls == 0:
            return {'total_calls': 0, 'no_data': True}
        
        # Get recent period for trends
        recent_stats_rows = await self.bot.database.get_api_statistics_range(limit=30)
        
        stats = {
            'total_calls': total_calls,
            'days_with_data': len(recent_stats_rows)
        }
        
        # Aggregate recent data
        if recent_stats_rows:
            total_recent_calls = sum(row['total_calls'] for row in recent_stats_rows)
            total_failed = sum(row['failed_calls'] for row in recent_stats_rows)
            
            stats['recent_avg_per_day'] = total_recent_calls / len(recent_stats_rows)
            
            if total_recent_calls > 0:
                stats['success_rate'] = ((total_recent_calls - total_failed) / total_recent_calls) * 100
        
        stats['avg_response_time'] = await self.bot.database.get_average_response_time()
        
        return stats
    
    
    def _get_description(self, period: str, stats: dict) -> str:
        """Generate description based on statistics."""
        if stats.get('no_data'):
            return "No API calls have been made yet in this period."
        
        if period == "today":
            usage_pct = stats.get('usage_percentage', 0)
            remaining = self.DAILY_API_LIMIT - stats.get('total_calls', 0)
            
            return (
                f"**Current Usage:** {stats['total_calls']:,} / {self.DAILY_API_LIMIT:,} calls "
                f"({usage_pct:.1f}%)\n"
                f"**Remaining Today:** {remaining:,} calls\n"
                f"**Last Hour:** {stats.get('calls_last_hour', 0):,} calls"
            )
        else:
            return f"Aggregated statistics for the selected period."
    
    
    def _get_usage_color(self, calls: int) -> discord.Color:
        """Get color based on usage percentage."""
        percentage = (calls / self.DAILY_API_LIMIT) * 100
        
        if percentage < 50:
            return discord.Color.green()
        elif percentage < 75:
            return discord.Color.gold()
        elif percentage < 90:
            return discord.Color.orange()
        else:
            return discord.Color.red()
    
    
    def _add_statistics_fields(self, embed: discord.Embed, stats: dict, period: str) -> None:
        """Add statistics fields to embed."""
        if stats.get('no_data'):
            return
        
        # Call Statistics
        call_stats_value = f"**Total Calls:** {stats.get('total_calls', 0):,}\n"
        
        if 'failed_calls' in stats:
            successful = stats['total_calls'] - stats['failed_calls']
            call_stats_value += f"**Successful:** {successful:,}\n"
            call_stats_value += f"**Failed:** {stats['failed_calls']:,}\n"
        
        if 'success_rate' in stats:
            call_stats_value += f"**Success Rate:** {stats['success_rate']:.1f}%"
        
        embed.add_field(
            name="📞 Call Statistics",
            value=call_stats_value,
            inline=True
        )
        
        # Performance Metrics
        if 'avg_response_time' in stats and stats['avg_response_time']:
            perf_value = f"**Avg Response:** {stats['avg_response_time']:.0f}ms\n"
            
            if 'avg_calls_per_day' in stats:
                perf_value += f"**Avg/Day:** {stats['avg_calls_per_day']:.0f} calls"
            elif 'recent_avg_per_day' in stats:
                perf_value += f"**Recent Avg/Day:** {stats['recent_avg_per_day']:.0f} calls"
            
            embed.add_field(
                name="⚡ Performance",
                value=perf_value,
                inline=True
            )
        
        # Error Breakdown
        if 'rate_limit_hits' in stats or 'private_profile_errors' in stats:
            error_value = ""
            
            if stats.get('rate_limit_hits', 0) > 0:
                error_value += f"**Rate Limits:** {stats['rate_limit_hits']:,}\n"
            
            if stats.get('private_profile_errors', 0) > 0:
                error_value += f"**Private Profiles:** {stats['private_profile_errors']:,}\n"
            
            if error_value:
                embed.add_field(
                    name="⚠️ Errors",
                    value=error_value.strip(),
                    inline=True
                )
        
        # Session Stats (only for today)
        if period == "today" and 'session_stats' in stats:
            session = stats['session_stats']
            session_value = (
                f"**Total:** {session['total_calls']:,}\n"
                f"**Successful:** {session['successful_calls']:,}\n"
                f"**Failed:** {session['failed_calls']:,}"
            )
            
            embed.add_field(
                name="🔄 Current Session",
                value=session_value,
                inline=True
            )
        
        # Most Called Endpoints
        if period == "today" or period == "all":
            # Get top endpoints asynchronously in the caller
            pass  # Would need to be added if detailed endpoint stats are desired


async def setup(bot):
    """
    Setup function to add this cog to the bot.
    
    :param bot: The Discord bot instance.
    """
    await bot.add_cog(APIStatistics(bot))
