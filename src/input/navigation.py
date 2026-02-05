"""
Navigation state and continuous navigation handling for Console Utilities.
Manages D-pad/keyboard navigation with acceleration for held buttons.
"""

import pygame
from typing import Dict, Optional, Callable, Any

from constants import (
    NAVIGATION_INITIAL_DELAY,
    NAVIGATION_START_RATE,
    NAVIGATION_MAX_RATE,
    NAVIGATION_ACCELERATION,
)


class NavigationHandler:
    """
    Handles navigation state and continuous navigation for held buttons.

    Provides acceleration for held directional inputs, starting slow
    and speeding up over time.
    """

    DIRECTIONS = ("up", "down", "left", "right")

    def __init__(self):
        # Current state of each direction (pressed or not)
        self._state: Dict[str, bool] = {d: False for d in self.DIRECTIONS}

        # Time when button was first pressed
        self._start_time: Dict[str, int] = {d: 0 for d in self.DIRECTIONS}

        # Time of last navigation repeat
        self._last_repeat: Dict[str, int] = {d: 0 for d in self.DIRECTIONS}

        # Current velocity (ms between repeats)
        self._velocity: Dict[str, float] = {d: 0 for d in self.DIRECTIONS}

        # Optional joystick reference
        self._joystick: Optional[pygame.joystick.JoystickType] = None

        # Controller mapping for button-based D-pad
        self._controller_mapping: Dict[str, Any] = {}

    def set_joystick(self, joystick: Optional[pygame.joystick.JoystickType]) -> None:
        """Set the joystick to use for input."""
        self._joystick = joystick

    def set_controller_mapping(self, mapping: Dict[str, Any]) -> None:
        """Set the controller button mapping."""
        self._controller_mapping = mapping

    def update(self) -> None:
        """
        Update navigation state based on current joystick/keyboard input.
        Should be called once per frame.
        """
        current_time = pygame.time.get_ticks()

        # Reset all states first
        for direction in self.DIRECTIONS:
            self._state[direction] = False

        # Check joystick state if available
        if self._joystick and self._joystick.get_init():
            self._update_from_joystick()

        # Check keyboard state as fallback
        self._update_from_keyboard()

        # Update timing for newly pressed/released directions
        self._update_timing(current_time)

    def _update_from_joystick(self) -> None:
        """Update state from joystick input."""
        if not self._joystick:
            return

        # Check hat-based D-pad
        if self._joystick.get_numhats() > 0:
            hat = self._joystick.get_hat(0)
            if hat[1] > 0:
                self._state["up"] = True
            elif hat[1] < 0:
                self._state["down"] = True
            if hat[0] < 0:
                self._state["left"] = True
            elif hat[0] > 0:
                self._state["right"] = True

        # Check button-based D-pad
        for direction in self.DIRECTIONS:
            button_info = self._controller_mapping.get(direction)
            if (
                isinstance(button_info, int)
                and self._joystick.get_numbuttons() > button_info
            ):
                if self._joystick.get_button(button_info):
                    self._state[direction] = True

    def _update_from_keyboard(self) -> None:
        """Update state from keyboard input."""
        keys = pygame.key.get_pressed()

        if keys[pygame.K_UP]:
            self._state["up"] = True
        if keys[pygame.K_DOWN]:
            self._state["down"] = True
        if keys[pygame.K_LEFT]:
            self._state["left"] = True
        if keys[pygame.K_RIGHT]:
            self._state["right"] = True

    def _update_timing(self, current_time: int) -> None:
        """Update timing for navigation acceleration."""
        for direction in self.DIRECTIONS:
            if self._state[direction]:
                if self._start_time[direction] == 0:
                    # First press - record start time and reset velocity
                    self._start_time[direction] = current_time
                    self._last_repeat[direction] = current_time
                    self._velocity[direction] = NAVIGATION_START_RATE
            else:
                # Released - reset timing and velocity
                self._start_time[direction] = 0
                self._last_repeat[direction] = 0
                self._velocity[direction] = 0

    def is_pressed(self, direction: str) -> bool:
        """Check if a direction is currently pressed."""
        return self._state.get(direction, False)

    def is_held(self, direction: str) -> bool:
        """Check if a direction is being held (for continuous navigation)."""
        return (
            self._state.get(direction, False) and self._start_time.get(direction, 0) > 0
        )

    def should_navigate(self, direction: str) -> bool:
        """
        Check if navigation should be triggered for held direction.

        Uses progressive acceleration - starts slow and speeds up
        the longer the button is held.

        Args:
            direction: Direction to check

        Returns:
            True if navigation should trigger this frame
        """
        if not self._state[direction]:
            return False

        current_time = pygame.time.get_ticks()
        start_time = self._start_time[direction]
        last_repeat = self._last_repeat[direction]
        current_velocity = self._velocity[direction]

        # Don't trigger before initial delay
        if current_time - start_time < NAVIGATION_INITIAL_DELAY:
            return False

        # Check if enough time has passed for the next repeat
        time_since_last = current_time - last_repeat
        if time_since_last >= current_velocity:
            self._last_repeat[direction] = current_time

            # Accelerate for next repeat (but don't go below minimum rate)
            new_velocity = current_velocity * NAVIGATION_ACCELERATION
            self._velocity[direction] = max(new_velocity, NAVIGATION_MAX_RATE)

            return True

        return False

    def get_hat_value(self, direction: str) -> tuple:
        """
        Convert direction string to hat coordinate tuple.

        Args:
            direction: Direction string ('up', 'down', 'left', 'right')

        Returns:
            Tuple (x, y) for hat coordinates
        """
        mapping = {
            "up": (0, 1),
            "down": (0, -1),
            "left": (-1, 0),
            "right": (1, 0),
        }
        return mapping.get(direction, (0, 0))

    def handle_continuous(self, on_navigate: Callable[[str, tuple], None]) -> None:
        """
        Handle continuous navigation for all held directions.

        Args:
            on_navigate: Callback function(direction, hat_value) for navigation
        """
        for direction in self.DIRECTIONS:
            if self.should_navigate(direction):
                hat = self.get_hat_value(direction)
                on_navigate(direction, hat)
                break  # Only process one direction per frame

    def reset(self) -> None:
        """Reset all navigation state."""
        for direction in self.DIRECTIONS:
            self._state[direction] = False
            self._start_time[direction] = 0
            self._last_repeat[direction] = 0
            self._velocity[direction] = 0
