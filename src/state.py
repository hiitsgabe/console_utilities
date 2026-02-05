"""
Application state management for Console Utilities.
Centralizes all global state into a single AppState class for better maintainability.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Any, Tuple
import pygame


@dataclass
class NavigationState:
    """State for navigation input handling."""

    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False

    def reset(self):
        """Reset all navigation states."""
        self.up = False
        self.down = False
        self.left = False
        self.right = False


@dataclass
class NavigationTiming:
    """Timing data for navigation repeat acceleration."""

    start_time: Dict[str, int] = field(
        default_factory=lambda: {"up": 0, "down": 0, "left": 0, "right": 0}
    )
    last_repeat: Dict[str, int] = field(
        default_factory=lambda: {"up": 0, "down": 0, "left": 0, "right": 0}
    )
    velocity: Dict[str, int] = field(
        default_factory=lambda: {"up": 0, "down": 0, "left": 0, "right": 0}
    )


@dataclass
class TouchState:
    """State for touch/mouse input handling."""

    start_pos: Optional[Tuple[int, int]] = None
    last_pos: Optional[Tuple[int, int]] = None
    start_time: int = 0
    is_scrolling: bool = False
    scroll_accumulated: float = 0
    last_click_time: int = 0
    last_clicked_item: int = -1


@dataclass
class SearchState:
    """State for search functionality."""

    mode: bool = False
    query: str = ""
    input_text: str = ""
    cursor_position: int = 0
    cursor_blink_time: int = 0
    filtered_list: List[Any] = field(default_factory=list)


@dataclass
class CharSelectorState:
    """State for character selector UI."""

    active: bool = False
    x: int = 0
    y: int = 0


@dataclass
class FolderBrowserState:
    """State for folder browser modal."""

    show: bool = False
    current_path: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    highlighted: int = 0
    scroll_offset: int = 0
    item_rects: List[Any] = field(default_factory=list)
    selected_system_to_add: Optional[Dict[str, Any]] = None
    focus_area: str = "list"  # "list" or "buttons"
    button_index: int = 0  # 0 = Select, 1 = Cancel


@dataclass
class FolderNameInputState:
    """State for folder name input modal."""

    show: bool = False
    input_text: str = ""
    cursor_position: int = 0
    char_index: int = 0


@dataclass
class UrlInputState:
    """State for URL input modal."""

    show: bool = False
    input_text: str = ""
    cursor_position: int = 0
    context: str = "archive_json"  # "archive_json" or "direct_download"


@dataclass
class GameDetailsState:
    """State for game details modal."""

    show: bool = False
    current_game: Optional[Any] = None
    button_focused: bool = True  # Download button is focused by default
    loading_size: bool = False  # True while fetching file size


@dataclass
class LoadingState:
    """State for loading/download progress."""

    show: bool = False
    message: str = ""
    progress: int = 0


@dataclass
class DownloadQueueItem:
    """State for a single download queue item."""

    game: Any  # Game dict/object
    system_data: Dict[str, Any]  # System config (for URL, auth, formats, etc.)
    system_name: str  # Display name
    status: str = (
        "waiting"  # "waiting" | "downloading" | "extracting" | "moving" | "completed" | "failed" | "cancelled"
    )
    progress: float = 0.0  # 0.0 to 1.0
    downloaded: int = 0
    total_size: int = 0
    speed: float = 0.0
    error: str = ""


@dataclass
class DownloadQueueState:
    """State for download queue."""

    items: List[DownloadQueueItem] = field(default_factory=list)
    active: bool = False  # True when download thread is running
    highlighted: int = 0  # Currently highlighted item in downloads screen


@dataclass
class ConfirmModalState:
    """State for confirmation modal."""

    show: bool = False
    title: str = ""
    message_lines: List[str] = field(default_factory=list)
    ok_label: str = "OK"
    cancel_label: str = "Cancel"
    button_index: int = 0  # 0 = OK, 1 = Cancel
    context: str = (
        ""  # Context for what action to take on confirm (e.g., "download_all")
    )
    data: Any = None  # Additional data needed for the action
    loading: bool = False  # True while loading data (e.g., calculating sizes)
    loading_current: int = 0  # Current item being processed
    loading_total: int = 0  # Total items to process
    total_size: int = 0  # Calculated total size in bytes


@dataclass
class UIRects:
    """Stores rectangles for clickable UI elements."""

    menu_items: List[pygame.Rect] = field(default_factory=list)
    back_button: Optional[pygame.Rect] = None
    search_button: Optional[pygame.Rect] = None
    download_button: Optional[pygame.Rect] = None
    close_button: Optional[pygame.Rect] = None
    folder_select_button: Optional[pygame.Rect] = None
    folder_cancel_button: Optional[pygame.Rect] = None
    confirm_ok_button: Optional[pygame.Rect] = None
    confirm_cancel_button: Optional[pygame.Rect] = None
    modal_char_rects: List[Any] = field(default_factory=list)
    modal_back_button: Optional[pygame.Rect] = None
    scroll_offset: int = 0  # Current scroll offset for item index calculation


class AppState:
    """
    Centralized application state for Console Utilities.

    This class replaces all global variables with organized state management.
    State is grouped by related functionality for better organization.
    """

    def __init__(self):
        # ---- Core Application Data ---- #
        self.data: List[Dict[str, Any]] = []  # System configurations
        self.available_systems: List[Dict[str, Any]] = []
        self.game_list: List[Any] = []

        # ---- Navigation State ---- #
        self.mode: str = (
            "systems"  # systems, games, settings, utils, credits, add_systems, systems_settings, system_settings
        )
        self.highlighted: int = 0
        self.selected_system: int = 0
        self.selected_games: Set[int] = set()
        self.current_page: int = 0
        self.total_pages: int = 1
        self.menu_scroll_offset: int = 0
        self.settings_scroll_offset: int = 0

        # ---- Mode-specific highlights ---- #
        self.add_systems_highlighted: int = 0
        self.systems_settings_highlighted: int = 0
        self.system_settings_highlighted: int = 0
        self.selected_system_for_settings: Optional[int] = None

        # ---- Input State ---- #
        self.navigation = NavigationState()
        self.navigation_timing = NavigationTiming()
        self.touch = TouchState()
        self.input_mode: str = "keyboard"  # "touch", "keyboard", or "gamepad"

        # ---- Search State ---- #
        self.search = SearchState()

        # ---- Character Selector ---- #
        self.char_selector = CharSelectorState()

        # ---- Modal States ---- #
        self.folder_browser = FolderBrowserState()
        self.folder_name_input = FolderNameInputState()
        self.url_input = UrlInputState()
        self.game_details = GameDetailsState()
        self.loading = LoadingState()
        self.confirm_modal = ConfirmModalState()
        self.show_search_input: bool = False
        self.show_controller_mapping: bool = False

        # ---- Download Queue ---- #
        self.download_queue = DownloadQueueState()

        # ---- UI Rectangles ---- #
        self.ui_rects = UIRects()

        # ---- Runtime Flags ---- #
        self.running: bool = True
        self.movement_occurred: bool = False

    def reset_navigation(self):
        """Reset navigation-related state."""
        self.highlighted = 0
        self.menu_scroll_offset = 0
        self.selected_games = set()

    def enter_mode(self, new_mode: str):
        """
        Transition to a new application mode.

        Args:
            new_mode: The mode to transition to
        """
        self.mode = new_mode
        self.highlighted = 0

        if new_mode == "settings":
            self.settings_scroll_offset = 0
        elif new_mode == "add_systems":
            self.add_systems_highlighted = 0
        elif new_mode == "systems_settings":
            self.systems_settings_highlighted = 0
        elif new_mode == "system_settings":
            self.system_settings_highlighted = 0

    def close_all_modals(self):
        """Close all modal dialogs."""
        self.folder_browser.show = False
        self.folder_name_input.show = False
        self.url_input.show = False
        self.game_details.show = False
        self.show_search_input = False
        self.char_selector.active = False

    def get_current_game_list(self) -> List[Any]:
        """Get the current game list (filtered or full)."""
        if self.search.mode and self.search.query:
            return self.search.filtered_list
        return self.game_list


# Legacy compatibility - allow direct attribute access for migration period
# This can be removed once all code is migrated to use AppState
def create_legacy_globals(state: AppState) -> Dict[str, Any]:
    """
    Create a dictionary mapping legacy global names to state attributes.
    Useful during migration period.
    """
    return {
        "data": state.data,
        "mode": state.mode,
        "highlighted": state.highlighted,
        "selected_system": state.selected_system,
        "selected_games": state.selected_games,
        "game_list": state.game_list,
        "available_systems": state.available_systems,
        "current_page": state.current_page,
        "total_pages": state.total_pages,
        "search_mode": state.search.mode,
        "search_query": state.search.query,
        "filtered_game_list": state.search.filtered_list,
        "show_folder_browser": state.folder_browser.show,
        "folder_browser_current_path": state.folder_browser.current_path,
        "folder_browser_items": state.folder_browser.items,
        "folder_browser_highlighted": state.folder_browser.highlighted,
        "show_game_details": state.game_details.show,
        "current_game_detail": state.game_details.current_game,
        "show_search_input": state.show_search_input,
        "char_selector_mode": state.char_selector.active,
    }
