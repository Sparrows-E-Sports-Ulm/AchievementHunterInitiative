"""
Language Manager for the Achievement Hunter Initiative Bot
Handles loading and retrieving localized strings from JSON files.
"""

import json
import os
from typing import Optional, Dict, Any


class LanguageManager:
    """
    Manages language strings for the bot.
    Supports multiple languages and dynamic string formatting.
    """
    
    def __init__(self, default_locale: str = "en"):
        """
        Initialize the language manager.
        
        :param default_locale: The default locale to use (default: "en")
        """
        self.default_locale = default_locale
        self.current_locale = default_locale
        self.strings: Dict[str, Any] = {}
        self.locales_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "locales"
        )
        
    def load_locale(self, locale: str = None) -> bool:
        """
        Load a locale file.
        
        :param locale: The locale to load (default: current_locale)
        :return: True if successful, False otherwise
        """
        if locale is None:
            locale = self.current_locale
            
        locale_file = os.path.join(self.locales_dir, f"{locale}.json")
        
        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                self.strings = json.load(f)
                self.current_locale = locale
                return True
        except FileNotFoundError:
            print(f"Locale file not found: {locale_file}")
            return False
        except json.JSONDecodeError as e:
            print(f"Error decoding locale file {locale_file}: {e}")
            return False
    
    def get(self, key: str, **kwargs) -> str:
        """
        Get a localized string by key path.
        
        Key path format: "category.subcategory.key"
        Example: "commands.register.success"
        
        :param key: The key path to the string
        :param kwargs: Optional parameters for string formatting
        :return: The localized string, formatted if kwargs provided
        """
        keys = key.split(".")
        value = self.strings
        
        try:
            for k in keys:
                value = value[k]
            
            # Format string if kwargs provided
            if kwargs and isinstance(value, str):
                return value.format(**kwargs)
            
            return value
        except (KeyError, TypeError):
            # Return the key itself if not found (helpful for debugging)
            return f"[Missing: {key}]"
    
    def get_command_strings(self, command_name: str) -> Dict[str, Any]:
        """
        Get all strings for a specific command.
        
        :param command_name: The name of the command
        :return: Dictionary of all strings for that command
        """
        try:
            return self.strings["commands"][command_name]
        except KeyError:
            return {}
    
    def get_error_string(self, error_key: str, **kwargs) -> str:
        """
        Get an error message string.
        
        :param error_key: The error key
        :param kwargs: Optional parameters for string formatting
        :return: The formatted error message
        """
        return self.get(f"errors.{error_key}", **kwargs)
    
    def get_general_string(self, key: str, **kwargs) -> str:
        """
        Get a general string.
        
        :param key: The key within general strings
        :param kwargs: Optional parameters for string formatting
        :return: The formatted string
        """
        return self.get(f"general.{key}", **kwargs)
    
    def set_locale(self, locale: str) -> bool:
        """
        Change the current locale.
        
        :param locale: The new locale to use
        :return: True if successful, False otherwise
        """
        return self.load_locale(locale)
    
    def get_available_locales(self) -> list[str]:
        """
        Get a list of available locales.
        
        :return: List of locale codes
        """
        try:
            files = os.listdir(self.locales_dir)
            return [f[:-5] for f in files if f.endswith(".json")]
        except FileNotFoundError:
            return []
    
    def format_time(self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> str:
        """
        Format time duration using localized strings.
        
        :param hours: Number of hours
        :param minutes: Number of minutes
        :param seconds: Number of seconds
        :return: Formatted time string
        """
        parts = []
        
        if hours > 0:
            parts.append(self.get("general.time_format.hours", hours=round(hours)))
        if minutes > 0:
            parts.append(self.get("general.time_format.minutes", minutes=round(minutes)))
        if seconds > 0:
            parts.append(self.get("general.time_format.seconds", seconds=round(seconds)))
        
        return " ".join(parts)
    
    def get_profile_visibility(self, state: int) -> str:
        """
        Get the localized profile visibility string.
        
        :param state: The visibility state (1=private, 2=friends_only, 3=public)
        :return: Localized visibility string
        """
        visibility_map = {
            1: "general.profile_visibility.private",
            2: "general.profile_visibility.friends_only",
            3: "general.profile_visibility.public"
        }
        
        return self.get(visibility_map.get(state, "general.profile_visibility.private"))


# Global instance
_language_manager: Optional[LanguageManager] = None


def get_language_manager(locale: str = "en") -> LanguageManager:
    """
    Get the global language manager instance.
    
    :param locale: The locale to use (only on first call)
    :return: LanguageManager instance
    """
    global _language_manager
    
    if _language_manager is None:
        _language_manager = LanguageManager(locale)
        _language_manager.load_locale()
    
    return _language_manager


# Convenience function for quick access
def get_string(key: str, **kwargs) -> str:
    """
    Quick access to get a localized string.
    
    :param key: The key path to the string
    :param kwargs: Optional parameters for string formatting
    :return: The localized string
    """
    return get_language_manager().get(key, **kwargs)
