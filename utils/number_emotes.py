"""
Number to Custom Emote Converter

Converts numbers to 4-part custom emotes (2x2 grid).
Each digit is split into top-left, top-right, bottom-left, bottom-right parts.
Emoji IDs are loaded from emoji_ids.json file.
"""

from typing import List, Tuple
import json
import os


class NumberEmoteConverter:
    """
    Converts numbers to custom Discord emotes split into 4 parts (2x2 grid).
    
    Each digit emote is composed of:
    - Top Left (TL) - part0
    - Top Right (TR) - part1
    - Bottom Left (BL) - part2
    - Bottom Right (BR) - part3
    
    NOTE: These are App Emojis (Application Emojis), not server emojis!
    Format: <:name:id> for app emojis
    """
    
    _emoji_data = None
    _emote_parts = None
    
    @classmethod
    def _load_emoji_data(cls):
        """Load emoji IDs from JSON file if not already loaded."""
        if cls._emoji_data is None:
            # Get the path to the emoji_ids.json file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(base_dir, 'achhi-data', 'emoji_ids.json')
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    cls._emoji_data = json.load(f)
                cls._build_emote_parts()
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Emoji data file not found at {json_path}. "
                    "Please run upload_emojis.sh to generate the file."
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in emoji data file: {e}")
    
    @classmethod
    def _build_emote_parts(cls):
        """Build the EMOTE_PARTS structure from the loaded emoji data."""
        cls._emote_parts = {}
        
        for digit in range(10):
            digit_str = str(digit)
            digit_data = cls._emoji_data[digit_str]
            cls._emote_parts[digit_str] = {
                'TL': f'<:{digit}_TL:{digit_data["TL"]}>',
                'TR': f'<:{digit}_TR:{digit_data["TR"]}>',
                'BL': f'<:{digit}_BL:{digit_data["BL"]}>',
                'BR': f'<:{digit}_BR:{digit_data["BR"]}>'
            }
    
    @classmethod
    def get_emote_parts(cls):
        """Get the emote parts dictionary, loading data if necessary."""
        if cls._emote_parts is None:
            cls._load_emoji_data()
        return cls._emote_parts
    
    @staticmethod
    def number_to_emotes(number: int, min_digits: int = 2) -> Tuple[str, str]:
        """
        Convert a number to custom emote strings (top row and bottom row).
        
        :param number: The number to convert (1, 2, 3, ..., 999, etc.)
        :param min_digits: Minimum number of digits (pads with zeros if needed)
        :return: Tuple of (top_row, bottom_row) strings with emotes
        
        Example:
            number_to_emotes(5) returns:
            - top_row: '<:0_part0:xxx><:0_part1:xxx><:5_part0:xxx><:5_part1:xxx>'
            - bottom_row: '<:0_part2:xxx><:0_part3:xxx><:5_part2:xxx><:5_part3:xxx>'
            
            This creates: 05
        """
        # Get emote parts (loads from JSON if needed)
        emote_parts = NumberEmoteConverter.get_emote_parts()
        
        # Convert number to string and pad with zeros
        num_str = str(number).zfill(min_digits)
        
        # Build top and bottom rows
        top_row = ""
        bottom_row = ""
        
        for digit in num_str:
            parts = emote_parts[digit]
            top_row += parts['TL'] + parts['TR']
            bottom_row += parts['BL'] + parts['BR']
        
        return top_row, bottom_row
    
    @staticmethod
    def number_to_emote_dict(number: int, min_digits: int = 2) -> dict:
        """
        Convert a number to a dictionary with all emote information.
        
        :param number: The number to convert
        :param min_digits: Minimum number of digits (pads with zeros if needed)
        :return: Dictionary with detailed emote information
        
        Example:
            {
                'number': 5,
                'padded': '05',
                'top_row': '<:0_part0:xxx><:0_part1:xxx><:5_part0:xxx><:5_part1:xxx>',
                'bottom_row': '<:0_part2:xxx><:0_part3:xxx><:5_part2:xxx><:5_part3:xxx>',
                'digits': [
                    {
                        'digit': '0',
                        'TL': '<:0_part0:xxx>',
                        'TR': '<:0_part1:xxx>',
                        'BL': '<:0_part2:xxx>',
                        'BR': '<:0_part3:xxx>'
                    },
                    {
                        'digit': '5',
                        'TL': '<:5_part0:xxx>',
                        'TR': '<:5_part1:xxx>',
                        'BL': '<:5_part2:xxx>',
                        'BR': '<:5_part3:xxx>'
                    }
                ]
            }
        """
        # Get emote parts (loads from JSON if needed)
        emote_parts = NumberEmoteConverter.get_emote_parts()
        
        num_str = str(number).zfill(min_digits)
        top_row, bottom_row = NumberEmoteConverter.number_to_emotes(number, min_digits)
        
        digits_info = []
        for digit in num_str:
            parts = emote_parts[digit]
            digits_info.append({
                'digit': digit,
                'TL': parts['TL'],
                'TR': parts['TR'],
                'BL': parts['BL'],
                'BR': parts['BR']
            })
        
        return {
            'number': number,
            'padded': num_str,
            'top_row': top_row,
            'bottom_row': bottom_row,
            'digits': digits_info
        }
    
    @staticmethod
    def format_for_embed(number: int, min_digits: int = 2, prefix: str = "", suffix: str = "") -> str:
        """
        Format number emotes for use in Discord embed fields.
        Creates a 2-line string with top and bottom rows.
        
        :param number: The number to convert
        :param min_digits: Minimum number of digits
        :param prefix: Text to add before the emotes
        :param suffix: Text to add after the emotes
        :return: Formatted string for Discord embed
        
        Example:
            format_for_embed(5, prefix="Rank ") returns:
            "Rank <emotes_top>\n<emotes_bottom>"
        """
        top_row, bottom_row = NumberEmoteConverter.number_to_emotes(number, min_digits)
        
        if prefix or suffix:
            return f"{prefix}{top_row}{suffix}\n{prefix}{bottom_row}{suffix}"
        else:
            return f"{top_row}\n{bottom_row}"


# Convenience functions for direct use
def number_to_emotes(number: int, min_digits: int = 2) -> Tuple[str, str]:
    """
    Convenience function to convert number to emotes.
    
    :param number: Number to convert
    :param min_digits: Minimum digits (default: 2)
    :return: Tuple of (top_row, bottom_row)
    """
    return NumberEmoteConverter.number_to_emotes(number, min_digits)


def format_rank_emote(rank: int) -> str:
    """
    Format a rank number as emotes for Discord.
    Automatically determines minimum digits based on rank.
    
    :param rank: The rank number (1-999+)
    :return: Formatted emote string for Discord
    """
    # Determine minimum digits
    if rank < 10:
        min_digits = 2  # 01-09
    elif rank < 100:
        min_digits = 2  # 10-99
    elif rank < 1000:
        min_digits = 3  # 100-999
    else:
        min_digits = 4  # 1000+
    
    return NumberEmoteConverter.format_for_embed(rank, min_digits)