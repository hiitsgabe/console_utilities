"""
Touch and mouse input handling for Console Utilities.
Manages touch gestures, clicks, and scrolling.
"""

import pygame
from typing import Optional, Tuple, Callable, Any
from dataclasses import dataclass

from constants import (
    SCROLL_THRESHOLD,
    TAP_TIME_THRESHOLD,
    SCROLL_SENSITIVITY,
    DOUBLE_CLICK_THRESHOLD,
)


@dataclass
class TouchState:
    """State for tracking touch/mouse input."""
    start_pos: Optional[Tuple[int, int]] = None
    last_pos: Optional[Tuple[int, int]] = None
    start_time: int = 0
    is_scrolling: bool = False
    scroll_accumulated: float = 0
    last_click_time: int = 0
    last_clicked_item: int = -1


class TouchHandler:
    """
    Handles touch and mouse input for touchscreen devices.

    Supports:
    - Tap detection (single and double tap)
    - Scroll gestures
    - Click detection
    """

    def __init__(self):
        self._state = TouchState()
        self._touchscreen_available = False

        # Try to detect touchscreen
        try:
            import pygame._sdl2.touch
            touch_device_count = pygame._sdl2.touch.get_num_devices()
            if touch_device_count > 0:
                self._touchscreen_available = True
                print(f"Touchscreen detected: {touch_device_count} touch device(s) available")
            else:
                print("No touchscreen detected")
        except ImportError:
            print("Touch support not available in this pygame version")

    @property
    def touchscreen_available(self) -> bool:
        """Check if touchscreen is available."""
        return self._touchscreen_available

    @property
    def is_scrolling(self) -> bool:
        """Check if currently in a scroll gesture."""
        return self._state.is_scrolling

    def handle_finger_down(
        self,
        event: pygame.event.Event,
        screen_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Handle touch start event.

        Args:
            event: FINGERDOWN event
            screen_size: (width, height) of screen

        Returns:
            Touch position in pixels
        """
        # Convert normalized coordinates to pixels
        x = int(event.x * screen_size[0])
        y = int(event.y * screen_size[1])

        self._state.start_pos = (x, y)
        self._state.last_pos = (x, y)
        self._state.start_time = pygame.time.get_ticks()
        self._state.is_scrolling = False

        return (x, y)

    def handle_finger_up(
        self,
        event: pygame.event.Event,
        screen_size: Tuple[int, int],
        on_tap: Optional[Callable[[Tuple[int, int]], None]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Handle touch end event.

        Args:
            event: FINGERUP event
            screen_size: (width, height) of screen
            on_tap: Optional callback for tap events

        Returns:
            Tap position if it was a tap, None otherwise
        """
        if not self._state.start_pos:
            return None

        # Convert normalized coordinates to pixels
        x = int(event.x * screen_size[0])
        y = int(event.y * screen_size[1])

        # Calculate distance and time
        dx = x - self._state.start_pos[0]
        dy = y - self._state.start_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5
        time_elapsed = pygame.time.get_ticks() - self._state.start_time

        tap_pos = None

        # Check if it was a tap (short time, small movement, not scrolling)
        if (distance < SCROLL_THRESHOLD and
            time_elapsed < TAP_TIME_THRESHOLD and
            not self._state.is_scrolling):
            tap_pos = self._state.start_pos
            if on_tap:
                on_tap(tap_pos)

        # Reset state
        self._state.start_pos = None
        self._state.last_pos = None
        self._state.is_scrolling = False

        return tap_pos

    def handle_finger_motion(
        self,
        event: pygame.event.Event,
        screen_size: Tuple[int, int],
        on_scroll: Optional[Callable[[float], None]] = None
    ) -> float:
        """
        Handle touch motion event.

        Args:
            event: FINGERMOTION event
            screen_size: (width, height) of screen
            on_scroll: Optional callback for scroll events

        Returns:
            Scroll amount (positive = up, negative = down)
        """
        if not self._state.start_pos or not self._state.last_pos:
            return 0

        # Convert normalized coordinates to pixels
        x = int(event.x * screen_size[0])
        y = int(event.y * screen_size[1])

        # Calculate total distance from start
        dx_total = x - self._state.start_pos[0]
        dy_total = y - self._state.start_pos[1]
        total_distance = (dx_total * dx_total + dy_total * dy_total) ** 0.5

        # Calculate motion from last position
        dy_motion = y - self._state.last_pos[1]

        # Mark as scrolling if moved enough
        if total_distance > SCROLL_THRESHOLD:
            self._state.is_scrolling = True

        scroll_amount = 0

        # Check if we should scroll
        should_scroll = (
            (self._state.is_scrolling and abs(dy_motion) > 1) or
            (not self._state.is_scrolling and abs(dy_motion) > 3 and total_distance > 4)
        )

        if should_scroll:
            scroll_amount = -dy_motion * SCROLL_SENSITIVITY
            if on_scroll:
                on_scroll(scroll_amount)

            if abs(dy_motion) > 3:
                self._state.is_scrolling = True

        # Update last position
        self._state.last_pos = (x, y)

        return scroll_amount

    def handle_mouse_down(self, event: pygame.event.Event) -> Tuple[int, int]:
        """
        Handle mouse button down event.

        Args:
            event: MOUSEBUTTONDOWN event

        Returns:
            Click position
        """
        if event.button == 1:  # Left mouse button
            self._state.start_pos = event.pos
            self._state.last_pos = event.pos
            self._state.start_time = pygame.time.get_ticks()
            self._state.is_scrolling = False

        return event.pos

    def handle_mouse_up(
        self,
        event: pygame.event.Event,
        on_click: Optional[Callable[[Tuple[int, int]], None]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Handle mouse button up event.

        Args:
            event: MOUSEBUTTONUP event
            on_click: Optional callback for click events

        Returns:
            Click position if it was a click, None otherwise
        """
        if event.button != 1 or not self._state.start_pos:
            return None

        x, y = event.pos

        # Calculate distance and time
        dx = x - self._state.start_pos[0]
        dy = y - self._state.start_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5
        time_elapsed = pygame.time.get_ticks() - self._state.start_time

        click_pos = None

        # Check if it was a click
        if (distance < SCROLL_THRESHOLD and
            time_elapsed < TAP_TIME_THRESHOLD and
            not self._state.is_scrolling):
            click_pos = self._state.start_pos
            if on_click:
                on_click(click_pos)

        # Reset state
        self._state.start_pos = None
        self._state.last_pos = None
        self._state.is_scrolling = False

        return click_pos

    def handle_mouse_motion(
        self,
        event: pygame.event.Event,
        on_scroll: Optional[Callable[[float], None]] = None
    ) -> float:
        """
        Handle mouse motion event (drag scrolling).

        Args:
            event: MOUSEMOTION event
            on_scroll: Optional callback for scroll events

        Returns:
            Scroll amount
        """
        if not self._state.start_pos or not self._state.last_pos:
            return 0

        x, y = event.pos

        # Calculate total distance from start
        dx_total = x - self._state.start_pos[0]
        dy_total = y - self._state.start_pos[1]
        total_distance = (dx_total * dx_total + dy_total * dy_total) ** 0.5

        # Calculate motion from last position
        dy_motion = y - self._state.last_pos[1]

        # Mark as scrolling if moved enough
        if total_distance > SCROLL_THRESHOLD:
            self._state.is_scrolling = True

        scroll_amount = 0

        # Check if we should scroll
        should_scroll = (
            (self._state.is_scrolling and abs(dy_motion) > 1) or
            (not self._state.is_scrolling and abs(dy_motion) > 3 and total_distance > 4)
        )

        if should_scroll:
            scroll_amount = -dy_motion * SCROLL_SENSITIVITY
            if on_scroll:
                on_scroll(scroll_amount)

            if abs(dy_motion) > 3:
                self._state.is_scrolling = True

        # Update last position
        self._state.last_pos = (x, y)

        return scroll_amount

    def handle_mouse_wheel(
        self,
        event: pygame.event.Event,
        on_scroll: Optional[Callable[[float], None]] = None
    ) -> float:
        """
        Handle mouse wheel event.

        Args:
            event: MOUSEWHEEL event
            on_scroll: Optional callback for scroll events

        Returns:
            Scroll amount
        """
        if on_scroll:
            on_scroll(event.y)
        return event.y

    def check_double_click(self, item_index: int) -> bool:
        """
        Check if this click constitutes a double-click on the same item.

        Args:
            item_index: Index of clicked item

        Returns:
            True if this is a double-click
        """
        current_time = pygame.time.get_ticks()
        is_double = (
            item_index == self._state.last_clicked_item and
            current_time - self._state.last_click_time < DOUBLE_CLICK_THRESHOLD
        )

        # Update tracking
        self._state.last_clicked_item = item_index
        self._state.last_click_time = current_time

        return is_double

    def reset_double_click(self) -> None:
        """Reset double-click tracking."""
        self._state.last_clicked_item = -1
        self._state.last_click_time = 0

    def reset(self) -> None:
        """Reset all touch state."""
        self._state = TouchState()
