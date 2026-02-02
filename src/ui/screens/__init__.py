"""
UI Screens - Full page components with data binding.
The final layer of the atomic design hierarchy.
"""

from .systems_screen import SystemsScreen
from .games_screen import GamesScreen
from .settings_screen import SettingsScreen
from .utils_screen import UtilsScreen
from .credits_screen import CreditsScreen
from .add_systems_screen import AddSystemsScreen
from .systems_settings_screen import SystemsSettingsScreen
from .system_settings_screen import SystemSettingsScreen
from .screen_manager import ScreenManager

__all__ = [
    'SystemsScreen',
    'GamesScreen',
    'SettingsScreen',
    'UtilsScreen',
    'CreditsScreen',
    'AddSystemsScreen',
    'SystemsSettingsScreen',
    'SystemSettingsScreen',
    'ScreenManager',
]
