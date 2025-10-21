"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.4.0
"""

import aiosqlite
from datetime import date, datetime
from typing import Optional

class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection
        # Enable row factory to access columns by name
        self.connection.row_factory = aiosqlite.Row


    async def add_hunter(self, steam_id, steam_name: str, discord_id: str = None) -> None:
        """
        This function will add a hunter to the database.

        :param steam_id: The Steam ID of the hunter that should be added.
        :param steam_name: The Steam name of the hunter.
        :param discord_id: Optional Discord ID of the hunter (for verified accounts).
        """
        if discord_id:
            await self.connection.execute(
                "INSERT INTO hunters(steam_id, steam_name, discord_id) VALUES (?, ?, ?)",
                (steam_id, steam_name, discord_id),
            )
        else:
            await self.connection.execute(
                "INSERT INTO hunters(steam_id, steam_name) VALUES (?, ?)",
                (steam_id, steam_name),
            )
        await self.connection.commit()

    async def is_hunter_locked(self, steam_id: str) -> bool:
        """
        This function will check if a hunter is locked in the database to prevent score updates.

        :param steam_id: The Steam ID of the hunter that should be checked.
        :return: True if the hunter is locked, False otherwise.
        """
        cursor = await self.connection.execute(
            "SELECT locked FROM hunters WHERE steam_id=?", (steam_id,)
        )
        row = await cursor.fetchone()
        if row:
            return bool(row["locked"])
        return False

    async def update_hunter_lock(self, steam_id: str, lock: int) -> None:
        """
        This function will lock a hunter in the database to prevent score updates.

        :param steam_id: The Steam ID of the hunter that should be locked.
        """
        await self.connection.execute(
            "UPDATE hunters SET locked=? WHERE steam_id=?",
            (lock, steam_id,),
        )
        await self.connection.commit()

    async def update_hunter_score(self, steam_id: str, score: int) -> None:
        """
        This function will update the score of a hunter in the database.

        :param steam_id: The Steam ID of the hunter that should be updated.
        :param score: The new score of the hunter.
        """
        await self.connection.execute(
            "UPDATE hunters SET score=?, last_updated=CURRENT_TIMESTAMP WHERE steam_id=?",
            (score, steam_id),
        )
        await self.connection.commit()

    async def update_hunter_total_achievements(self, steam_id: str, total_achievements: int) -> None:
        """
        This function will update the total achievements of a hunter in the database.

        :param steam_id: The Steam ID of the hunter that should be updated.
        :param total_achievements: The new total achievements of the hunter.
        """
        await self.connection.execute(
            "UPDATE hunters SET total_achievements=? WHERE steam_id=?",
            (total_achievements, steam_id),
        )
        await self.connection.commit()

    async def get_hunter_by_steam_id(self, steam_id: str) -> aiosqlite.Row | None:
        """
        This function will return a hunter from the database by their Steam ID.

        :param steam_id: The Steam ID of the hunter that should be returned.
        :return: The hunter with the given Steam ID or None if no hunter was found.
        """
        cursor = await self.connection.execute(
            "SELECT * FROM hunters WHERE steam_id=?", (steam_id,)
        )
        return await cursor.fetchone()
    
    async def get_hunter_by_discord_id(self, discord_id: str) -> aiosqlite.Row | None:
        """
        This function will return a hunter from the database by their Discord ID.

        :param discord_id: The Discord ID of the hunter that should be returned.
        :return: The hunter with the given Discord ID or None if no hunter was found.
        """
        cursor = await self.connection.execute(
            "SELECT * FROM hunters WHERE discord_id=?", (discord_id,)
        )
        return await cursor.fetchone()
    
    async def link_discord_id(self, steam_id: str, discord_id: str) -> None:
        """
        This function will link a Discord ID to a hunter in the database.

        :param steam_id: The Steam ID of the hunter that should be linked.
        :param discord_id: The Discord ID that should be linked to the hunter.
        """
        await self.connection.execute(
            "UPDATE hunters SET discord_id=? WHERE steam_id=?",
            (discord_id, steam_id),
        )
        await self.connection.commit()

    async def get_scoreboard(self, limit: int = 10, offset: int = 0, order_by: str = "score") -> list[aiosqlite.Row]:
        """
        This function will return the scoreboard from the database.

        :param limit: The maximum number of hunters that should be returned.
        :param offset: The number of hunters that should be skipped.
        :param order_by: The column to sort by. Options: 'score', 'total_achievements', 'last_updated'
        :return: A list of hunters ordered by the specified column in descending order.
        """
        # Validate order_by to prevent SQL injection
        valid_columns = ['score', 'total_achievements', 'last_updated']
        if order_by not in valid_columns:
            order_by = 'score'
        
        cursor = await self.connection.execute(
            f"SELECT * FROM hunters ORDER BY {order_by} DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return await cursor.fetchall()
    
    async def get_hunter_rank(self, steam_id: str, order_by: str = "score") -> int | None:
        """
        Get the rank/position of a hunter in the leaderboard.
        
        :param steam_id: The Steam ID of the hunter.
        :param order_by: The column to rank by. Options: 'score', 'total_achievements'
        :return: The rank (1-based) of the hunter, or None if not found.
        """
        # Validate order_by to prevent SQL injection
        valid_columns = ['score', 'total_achievements']
        if order_by not in valid_columns:
            order_by = 'score'
        
        # Get the rank using a subquery
        cursor = await self.connection.execute(
            f"""
            SELECT rank FROM (
                SELECT steam_id, ROW_NUMBER() OVER (ORDER BY {order_by} DESC) as rank
                FROM hunters
            ) WHERE steam_id = ?
            """,
            (steam_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row['rank']
        return None
    
    async def get_hunters_around_rank(
        self, 
        steam_id: str, 
        context_size: int = 5, 
        order_by: str = "score"
    ) -> tuple[list[aiosqlite.Row], int | None]:
        """
        Get hunters around a specific user's rank (before and after).
        
        :param steam_id: The Steam ID of the hunter to center around.
        :param context_size: Number of hunters to show before and after the target hunter.
        :param order_by: The column to rank by. Options: 'score', 'total_achievements'
        :return: Tuple of (list of hunters, user's rank). Returns ([], None) if user not found.
        """
        # Validate order_by to prevent SQL injection
        valid_columns = ['score', 'total_achievements']
        if order_by not in valid_columns:
            order_by = 'score'
        
        # First, get the user's rank
        rank = await self.get_hunter_rank(steam_id, order_by)
        
        if rank is None:
            return ([], None)
        
        # Calculate offset (rank - context_size - 1, but not less than 0)
        offset = max(0, rank - context_size - 1)
        
        # Calculate limit (context_size before + user + context_size after)
        limit = context_size * 2 + 1
        
        # Get the hunters
        cursor = await self.connection.execute(
            f"""
            SELECT *, ROW_NUMBER() OVER (ORDER BY {order_by} DESC) as rank
            FROM hunters
            ORDER BY {order_by} DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        hunters = await cursor.fetchall()
        
        return (hunters, rank)
    
    async def get_total_hunters_count(self) -> int:
        """
        Get the total number of hunters in the database.
        
        :return: The total count of hunters.
        """
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as count FROM hunters"
        )
        row = await cursor.fetchone()
        return row['count'] if row else 0
    
    async def get_random_hunter_with_score(self) -> aiosqlite.Row | None:
        """
        Get a random hunter with score > 0.
        
        :return: A random hunter row or None if no hunters found.
        """
        cursor = await self.connection.execute(
            "SELECT * FROM hunters WHERE score > 0 ORDER BY RANDOM() LIMIT 1"
        )
        return await cursor.fetchone()
    
    async def close(self) -> None:
        """
        Close the database connection.
        """
        if self.connection:
            await self.connection.close()

    # ===== API STATISTICS METHODS =====
    
    async def increment_api_call(
        self,
        endpoint: str,
        steam_id: Optional[str] = None,
        app_id: Optional[int] = None,
        success: bool = True,
        error_type: Optional[str] = None,
        response_time_ms: Optional[int] = None
    ) -> None:
        """
        Increment API call statistics for the current date and log the call.
        
        :param endpoint: The API endpoint name (e.g., 'get_player_summaries')
        :param steam_id: Optional Steam ID involved in the call
        :param app_id: Optional App ID involved in the call
        :param success: Whether the call was successful
        :param error_type: Type of error if call failed (e.g., 'RateLimit', 'PrivateProfile')
        :param response_time_ms: Response time in milliseconds
        """
        today = date.today().isoformat()
        
        # Insert or update daily statistics
        await self.connection.execute(
            """
            INSERT INTO api_statistics (date, total_calls, {endpoint})
            VALUES (?, 1, 1)
            ON CONFLICT(date) DO UPDATE SET
                total_calls = total_calls + 1,
                {endpoint} = {endpoint} + 1
            """.format(endpoint=endpoint),
            (today,)
        )
        
        # Update error counters if applicable
        if not success:
            await self.connection.execute(
                """
                UPDATE api_statistics
                SET failed_calls = failed_calls + 1
                WHERE date = ?
                """,
                (today,)
            )
            
            if error_type == 'RateLimit':
                await self.connection.execute(
                    """
                    UPDATE api_statistics
                    SET rate_limit_hits = rate_limit_hits + 1
                    WHERE date = ?
                    """,
                    (today,)
                )
            elif error_type == 'PrivateProfile':
                await self.connection.execute(
                    """
                    UPDATE api_statistics
                    SET private_profile_errors = private_profile_errors + 1
                    WHERE date = ?
                    """,
                    (today,)
                )
        
        # Log the individual call
        await self.connection.execute(
            """
            INSERT INTO api_call_log (endpoint, steam_id, app_id, success, error_type, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (endpoint, steam_id, app_id, success, error_type, response_time_ms)
        )
        
        await self.connection.commit()
    
    async def get_api_statistics_today(self) -> Optional[aiosqlite.Row]:
        """
        Get API statistics for today.
        
        :return: Today's API statistics row or None if no calls made today
        """
        today = date.today().isoformat()
        cursor = await self.connection.execute(
            "SELECT * FROM api_statistics WHERE date = ?",
            (today,)
        )
        return await cursor.fetchone()
    
    async def get_api_statistics_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30
    ) -> list[aiosqlite.Row]:
        """
        Get API statistics for a date range.
        
        :param start_date: Start date in ISO format (YYYY-MM-DD), defaults to 30 days ago
        :param end_date: End date in ISO format (YYYY-MM-DD), defaults to today
        :param limit: Maximum number of records to return
        :return: List of API statistics rows
        """
        if not end_date:
            end_date = date.today().isoformat()
        
        if start_date:
            cursor = await self.connection.execute(
                """
                SELECT * FROM api_statistics
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (start_date, end_date, limit)
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT * FROM api_statistics
                WHERE date <= ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (end_date, limit)
            )
        
        return await cursor.fetchall()
    
    async def get_total_api_calls(self) -> int:
        """
        Get the total number of API calls ever made.
        
        :return: Total API call count
        """
        cursor = await self.connection.execute(
            "SELECT COALESCE(SUM(total_calls), 0) as total FROM api_statistics"
        )
        row = await cursor.fetchone()
        return row['total'] if row else 0
    
    async def get_api_calls_recent(self, hours: int = 1) -> int:
        """
        Get the number of API calls in the last X hours.
        
        :param hours: Number of hours to look back
        :return: Number of API calls in the specified time period
        """
        cursor = await self.connection.execute(
            """
            SELECT COUNT(*) as count
            FROM api_call_log
            WHERE timestamp >= datetime('now', '-{} hours')
            """.format(hours)
        )
        row = await cursor.fetchone()
        return row['count'] if row else 0
    
    async def get_most_called_endpoints(self, limit: int = 5) -> list[tuple[str, int]]:
        """
        Get the most frequently called API endpoints.
        
        :param limit: Number of top endpoints to return
        :return: List of tuples (endpoint_name, call_count)
        """
        cursor = await self.connection.execute(
            """
            SELECT endpoint, COUNT(*) as count
            FROM api_call_log
            GROUP BY endpoint
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        return [(row['endpoint'], row['count']) for row in rows]
    
    async def get_average_response_time(self) -> Optional[float]:
        """
        Get the average API response time across all calls.
        
        :return: Average response time in milliseconds or None if no data
        """
        cursor = await self.connection.execute(
            """
            SELECT AVG(response_time_ms) as avg_time
            FROM api_call_log
            WHERE response_time_ms IS NOT NULL
            """
        )
        row = await cursor.fetchone()
        return row['avg_time'] if row and row['avg_time'] else None
    
    async def cleanup_old_api_logs(self, days: int = 30) -> int:
        """
        Clean up API call logs older than specified days.
        
        :param days: Number of days to keep logs for
        :return: Number of deleted records
        """
        cursor = await self.connection.execute(
            """
            DELETE FROM api_call_log
            WHERE timestamp < datetime('now', '-{} days')
            """.format(days)
        )
        await self.connection.commit()
        return cursor.rowcount if cursor.rowcount else 0

    