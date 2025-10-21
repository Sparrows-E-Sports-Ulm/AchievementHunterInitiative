"""
Global Score Calculator Service

This Cog manages a global queue for calculating Steam achievement scores.
It can be used by multiple commands (register, update, etc.) without blocking the bot.

Uses a separate thread pool to completely isolate heavy calculations from the Discord bot's event loop.
"""

import asyncio
from discord.ext import commands, tasks
from typing import Optional, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import functools


class ScoreCalculator(commands.Cog, name="score_calculator"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.calculation_queue = asyncio.Queue()
        self.current_calculation: Optional[str] = None
        self.calculation_stats: Dict[str, dict] = {}
        
        # Create a thread pool for CPU-intensive calculations
        # max_workers=2 means max 2 calculations can run simultaneously
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ScoreCalc")
        
        self.score_calculator_task.start()

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.bot.logger.info("Unloading ScoreCalculator cog...")
        
        # Cancel the background task
        if self.score_calculator_task.is_running():
            self.score_calculator_task.cancel()
        
        # Shutdown the thread pool gracefully
        # wait=True ensures all running tasks complete before shutdown
        self.thread_pool.shutdown(wait=True)
        
        self.bot.logger.info("ScoreCalculator cog unloaded")

    @tasks.loop(seconds=5)
    async def score_calculator_task(self):
        """
        Background task that processes the calculation queue.
        Runs every 5 seconds to check for new items in the queue.
        """
        if not self.calculation_queue.empty() and self.current_calculation is None:
            steam_id = await self.calculation_queue.get()
            self.current_calculation = steam_id
            
            # Create a task for the calculation so it doesn't block the loop
            asyncio.create_task(self._process_calculation(steam_id))
    
    async def _process_calculation(self, steam_id: str):
        """
        Process a single calculation in a separate task.
        
        :param steam_id: The Steam ID to calculate
        """
        try:
            await self._calculate_and_store_score(steam_id)
        except Exception as e:
            self.bot.logger.error(f"Error calculating score for {steam_id}: {e}")
        finally:
            self.current_calculation = None
            self.calculation_queue.task_done()

    @score_calculator_task.before_loop
    async def before_score_calculator(self):
        """Wait for the bot to be ready before starting the task"""
        await self.bot.wait_until_ready()

    def _calculate_score_sync(self, steam_id: str, api_key: str, batch_size: int) -> tuple:
        """
        Synchronous function that runs in a separate thread.
        This completely isolates the calculation from the Discord bot's event loop.
        
        :param steam_id: The Steam ID to calculate
        :param api_key: Steam API key
        :param batch_size: Batch size for parallel processing
        :return: Tuple of (score, total_achievements, error)
        """
        import asyncio
        from steam_api import SteamUser, PrivateProfileError
        
        steam_user = None
        loop = None
        
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create Steam user (will create its own web_api instance in this thread)
            steam_user = SteamUser(api_key, steam_id, logger=self.bot.logger)
            
            # Run the calculation in this thread's event loop
            score, total_achievements = loop.run_until_complete(
                steam_user.calculate_achievement_score(batch_size=batch_size)
            )
            
            # Close the steam_user session
            loop.run_until_complete(steam_user.close())
            
            return (score, total_achievements, None)
            
        except PrivateProfileError as e:
            return (0, 0, f"PRIVATE_PROFILE: {str(e)}")
        except Exception as e:
            return (0, 0, str(e))
        finally:
            # Ensure cleanup
            if steam_user and loop:
                try:
                    loop.run_until_complete(steam_user.close())
                except Exception:
                    pass
            
            if loop:
                try:
                    loop.close()
                except Exception:
                    pass

    async def _calculate_and_store_score(self, steam_id: str) -> None:
        """
        Internal method to calculate and store the achievement score.
        Runs the heavy calculation in a separate thread to avoid blocking the bot.

        :param steam_id: The Steam ID of the hunter whose score should be calculated.
        """
        start_time = datetime.now()
        self.bot.logger.info(f"Started calculating score for Steam ID: {steam_id} (using thread pool)")
        
        try:
            # Lock the hunter to prevent concurrent updates
            await self.bot.database.update_hunter_lock(steam_id, 1)
            
            # Get batch size from performance config if available
            perf_config = self.bot.get_cog("performance_config")
            batch_size = perf_config.get_batch_size() if perf_config else 15
            
            # Run the calculation in a separate thread to completely isolate it from the bot
            # This prevents ANY blocking of the Discord bot's event loop
            loop = asyncio.get_event_loop()
            score, total_achievements, error = await loop.run_in_executor(
                self.thread_pool,
                self._calculate_score_sync,
                steam_id,
                self.bot.steamAPI.api_key,
                batch_size
            )
            
            if error:
                # Check if it's a private profile error
                if error.startswith("PRIVATE_PROFILE:"):
                    self.bot.logger.warning(f"Cannot calculate score for {steam_id}: Profile is private")
                    # Don't raise an exception, just log and unlock
                    await self.bot.database.update_hunter_lock(steam_id, 0)
                    return
                raise Exception(error)
            
            # Update database (these are quick async operations)
            await self.bot.database.update_hunter_score(steam_id, score)
            await self.bot.database.update_hunter_total_achievements(steam_id, total_achievements)
            
            # Unlock the hunter
            await self.bot.database.update_hunter_lock(steam_id, 0)
            
            # Store statistics
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.calculation_stats[steam_id] = {
                'score': score,
                'total_achievements': total_achievements,
                'calculated_at': end_time,
                'duration_seconds': duration
            }
            
            self.bot.logger.info(
                f"Successfully calculated score for {steam_id}: "
                f"Score={score}, Achievements={total_achievements}, Duration={duration:.2f}s"
            )
            
        except Exception as e:
            self.bot.logger.error(f"Error calculating score for {steam_id}: {e}")
            # Make sure to unlock the hunter even if an error occurs
            try:
                await self.bot.database.update_hunter_lock(steam_id, 0)
            except Exception as unlock_error:
                self.bot.logger.error(f"Error unlocking hunter {steam_id}: {unlock_error}")
            raise

    async def add_to_queue(self, steam_id: str) -> int:
        """
        Add a Steam ID to the calculation queue.

        :param steam_id: The Steam ID to add to the queue
        :return: Position in queue (0 if currently being processed)
        """
        # Check if already in queue
        if steam_id == self.current_calculation:
            return 0
        
        # Check if already in queue
        queue_items = list(self.calculation_queue._queue)
        if steam_id in queue_items:
            return queue_items.index(steam_id) + 1
        
        # Add to queue
        await self.calculation_queue.put(steam_id)
        position = self.calculation_queue.qsize()
        
        self.bot.logger.info(f"Added {steam_id} to calculation queue. Position: {position}")
        return position

    def get_queue_size(self) -> int:
        """
        Get the current size of the calculation queue.

        :return: Number of items in queue
        """
        return self.calculation_queue.qsize()

    def is_calculating(self, steam_id: str) -> bool:
        """
        Check if a specific Steam ID is currently being calculated.

        :param steam_id: The Steam ID to check
        :return: True if currently being calculated, False otherwise
        """
        return self.current_calculation == steam_id

    def is_in_queue(self, steam_id: str) -> bool:
        """
        Check if a specific Steam ID is in the queue.

        :param steam_id: The Steam ID to check
        :return: True if in queue, False otherwise
        """
        if self.current_calculation == steam_id:
            return True
        return steam_id in list(self.calculation_queue._queue)

    def get_queue_position(self, steam_id: str) -> Optional[int]:
        """
        Get the position of a Steam ID in the queue.

        :param steam_id: The Steam ID to check
        :return: Position in queue (0 if currently processing, None if not in queue)
        """
        if self.current_calculation == steam_id:
            return 0
        
        queue_items = list(self.calculation_queue._queue)
        if steam_id in queue_items:
            return queue_items.index(steam_id) + 1
        
        return None

    def get_calculation_stats(self, steam_id: str) -> Optional[dict]:
        """
        Get the calculation statistics for a Steam ID.

        :param steam_id: The Steam ID to get stats for
        :return: Dictionary with stats or None if not found
        """
        return self.calculation_stats.get(steam_id)


async def setup(bot):
    await bot.add_cog(ScoreCalculator(bot))
