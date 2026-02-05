"""
Controller input handling for Console Utilities.
Manages controller button mapping and input matching.
"""

import pygame
from typing import Dict, Any, Optional, List


class ControllerHandler:
    """
    Handles controller input mapping and button detection.

    Supports both button-based D-pads and hat-based D-pads,
    as well as custom button mappings.
    """

    # Essential buttons that must be mapped
    ESSENTIAL_BUTTONS = [
        'select', 'back', 'start', 'detail',
        'search', 'up', 'down', 'left', 'right'
    ]

    # Optional buttons
    OPTIONAL_BUTTONS = [
        'left_shoulder', 'right_shoulder',
        'left_trigger', 'right_trigger'
    ]

    def __init__(self, mapping: Optional[Dict[str, Any]] = None):
        """
        Initialize controller handler.

        Args:
            mapping: Optional initial button mapping
        """
        self._mapping: Dict[str, Any] = mapping or {}
        self._joystick: Optional[pygame.joystick.JoystickType] = None

    def set_mapping(self, mapping: Dict[str, Any]) -> None:
        """Set the button mapping."""
        self._mapping = mapping

    def get_mapping(self) -> Dict[str, Any]:
        """Get the current button mapping."""
        return self._mapping.copy()

    def set_joystick(self, joystick: Optional[pygame.joystick.JoystickType]) -> None:
        """Set the joystick to use."""
        self._joystick = joystick

    def get_button(self, action: str) -> Optional[Any]:
        """
        Get the button/key mapping for an action.

        Args:
            action: Action name (e.g., 'select', 'back', 'up')

        Returns:
            Button identifier or None if not mapped
        """
        return self._mapping.get(action)

    def set_button(self, action: str, button: Any) -> None:
        """
        Set the button mapping for an action.

        Args:
            action: Action name
            button: Button identifier
        """
        self._mapping[action] = button

    def needs_mapping(self) -> bool:
        """
        Check if controller mapping is needed.

        Returns:
            True if mapping is incomplete, False otherwise
        """
        # Touchscreen mode doesn't need button mapping
        if self._mapping.get('touchscreen_mode'):
            return False

        # Check if all essential buttons are mapped
        return not all(
            button in self._mapping
            for button in self.ESSENTIAL_BUTTONS
        )

    def is_touchscreen_mode(self) -> bool:
        """Check if running in touchscreen-only mode."""
        return self._mapping.get('touchscreen_mode', False)

    def input_matches_action(
        self,
        event: pygame.event.Event,
        action: str
    ) -> bool:
        """
        Check if a pygame event matches a mapped action.

        Args:
            event: Pygame event to check
            action: Action name to match against

        Returns:
            True if event matches the action
        """
        button_info = self.get_button(action)

        if button_info is None:
            return False

        # Check joystick button events
        if event.type == pygame.JOYBUTTONDOWN:
            if isinstance(button_info, int):
                return event.button == button_info

        # Check D-pad/hat events
        elif event.type == pygame.JOYHATMOTION:
            if ((isinstance(button_info, (tuple, list))) and
                    len(button_info) >= 3 and button_info[0] == "hat"):
                _, expected_x, expected_y = button_info[0:3]
                return event.value == (expected_x, expected_y)

        # Check keyboard events
        elif event.type == pygame.KEYDOWN:
            # Map actions to default keyboard keys
            keyboard_map = {
                'select': pygame.K_RETURN,
                'back': pygame.K_ESCAPE,
                'start': pygame.K_SPACE,
                'detail': pygame.K_d,
                'search': pygame.K_s,
                'up': pygame.K_UP,
                'down': pygame.K_DOWN,
                'left': pygame.K_LEFT,
                'right': pygame.K_RIGHT,
                'left_shoulder': pygame.K_q,
                'right_shoulder': pygame.K_e,
            }

            default_key = keyboard_map.get(action)
            if default_key and event.key == default_key:
                return True

        return False

    def get_button_name(self, action: str) -> str:
        """
        Get a display name for a button action.

        Args:
            action: Action name

        Returns:
            Human-readable button name
        """
        button_names = {
            'select': 'A/Confirm',
            'back': 'B/Back',
            'start': 'Start',
            'detail': 'Y/Detail',
            'search': 'X/Search',
            'up': 'D-pad Up',
            'down': 'D-pad Down',
            'left': 'D-pad Left',
            'right': 'D-pad Right',
            'left_shoulder': 'L1/LB',
            'right_shoulder': 'R1/RB',
            'left_trigger': 'L2/LT',
            'right_trigger': 'R2/RT',
        }
        return button_names.get(action, action.replace('_', ' ').title())

    def get_action_for_event(
        self,
        event: pygame.event.Event
    ) -> Optional[str]:
        """
        Get the action name for a pygame event.

        Args:
            event: Pygame event

        Returns:
            Action name or None if no match
        """
        for action in self.ESSENTIAL_BUTTONS + self.OPTIONAL_BUTTONS:
            if self.input_matches_action(event, action):
                return action
        return None

    def collect_mapping_step(
        self,
        event: pygame.event.Event,
        action: str
    ) -> bool:
        """
        Process an event during mapping collection.

        Args:
            event: Pygame event
            action: Action to map

        Returns:
            True if mapping was recorded
        """
        if event.type == pygame.JOYBUTTONDOWN:
            self._mapping[action] = event.button
            return True

        if event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            if action == "up" and hat_y == 1:
                self._mapping[action] = ("hat", 0, 1)
                return True
            elif action == "down" and hat_y == -1:
                self._mapping[action] = ("hat", 0, -1)
                return True
            elif action == "left" and hat_x == -1:
                self._mapping[action] = ("hat", -1, 0)
                return True
            elif action == "right" and hat_x == 1:
                self._mapping[action] = ("hat", 1, 0)
                return True

        return False

    def get_unmapped_actions(self) -> List[str]:
        """
        Get list of essential actions that are not yet mapped.

        Returns:
            List of unmapped action names
        """
        return [
            action for action in self.ESSENTIAL_BUTTONS
            if action not in self._mapping
        ]

    def clear_mapping(self) -> None:
        """Clear all button mappings."""
        self._mapping = {}
