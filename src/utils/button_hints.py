"""
Button hints utility for Console Utilities.
Maps action names to button names based on input mode.
"""

from typing import Dict

# Button mappings for each input mode
KEYBOARD_BUTTONS: Dict[str, str] = {
    "select": "Enter",
    "back": "Esc",
    "start": "Space",
    "search": "S",
    "detail": "D",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "delete": "Backspace",
    "left_shoulder": "Q",
    "right_shoulder": "E",
}

GAMEPAD_BUTTONS: Dict[str, str] = {
    "select": "A",
    "back": "B",
    "start": "Start",
    "search": "X",
    "detail": "Y",
    "up": "D-pad Up",
    "down": "D-pad Down",
    "left": "D-pad Left",
    "right": "D-pad Right",
    "delete": "X",
    "left_shoulder": "L",
    "right_shoulder": "R",
}

TOUCH_BUTTONS: Dict[str, str] = {
    "select": "Tap",
    "back": "Back",
    "start": "Menu",
    "search": "Search",
    "detail": "Long press",
    "up": "Swipe up",
    "down": "Swipe down",
    "left": "Swipe left",
    "right": "Swipe right",
    "delete": "Delete",
    "left_shoulder": "L",
    "right_shoulder": "R",
}


def get_button_name(action: str, input_mode: str) -> str:
    """
    Get the button name for an action based on input mode.

    Args:
        action: The action name (e.g., "select", "back", "start")
        input_mode: Current input mode ("keyboard", "gamepad", or "touch")

    Returns:
        The button name for the given action and input mode
    """
    if input_mode == "gamepad":
        return GAMEPAD_BUTTONS.get(action, action)
    elif input_mode == "touch":
        return TOUCH_BUTTONS.get(action, action)
    else:  # keyboard
        return KEYBOARD_BUTTONS.get(action, action)


def get_button_hint(action: str, label: str, input_mode: str) -> str:
    """
    Get a formatted button hint string.

    Args:
        action: The action name (e.g., "select", "back")
        label: The label to show (e.g., "Download", "Back")
        input_mode: Current input mode

    Returns:
        Formatted hint string like "A: Download" or "Enter: Download"
    """
    button = get_button_name(action, input_mode)
    return f"{button}: {label}"


def get_combined_hints(hints: list, input_mode: str) -> str:
    """
    Get combined hints for multiple actions.

    Args:
        hints: List of (action, label) tuples
        input_mode: Current input mode

    Returns:
        Combined hint string like "A: Download | B: Back"
    """
    hint_strings = [
        get_button_hint(action, label, input_mode) for action, label in hints
    ]
    return " | ".join(hint_strings)


def get_download_hint(input_mode: str) -> str:
    """Get the hint text for starting a download."""
    button = get_button_name("start", input_mode)
    return f"Press {button} to download"


def get_search_hints(input_mode: str) -> str:
    """Get the hint text for search modal."""
    if input_mode == "gamepad":
        return get_combined_hints(
            [
                ("select", "Select"),
                ("back", "Cancel"),
                ("delete", "Delete"),
            ],
            input_mode,
        )
    else:
        return get_combined_hints(
            [
                ("select", "Search"),
                ("back", "Cancel"),
                ("delete", "Delete"),
            ],
            input_mode,
        )


def get_game_details_hints(input_mode: str) -> str:
    """Get the hint text for game details modal."""
    return get_combined_hints(
        [
            ("select", "Download"),
            ("back", "Back"),
        ],
        input_mode,
    )
