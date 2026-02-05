"""
Input handling for Console Utilities.
Handles keyboard, controller, and touch input.
"""

from .navigation import NavigationHandler
from .controller import ControllerHandler
from .touch import TouchHandler

__all__ = [
    "NavigationHandler",
    "ControllerHandler",
    "TouchHandler",
]
