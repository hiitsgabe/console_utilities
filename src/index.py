import os
import sys
import json
import shutil
import pygame
import requests
import traceback
import re
import time
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime
from urllib.parse import urljoin, unquote
import html
from threading import Thread
from queue import Queue
from nsz import decompress as nsz_decompress

#-------------------------------------------------------------------------------------#
#
#                 Variables        
##-------------------------------------------------------------------------------------#
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'
NSZ_AVAILABLE = False
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = None  
if DEV_MODE:
    TEMP_LOG_DIR = os.path.join(SCRIPT_DIR, "..", "py_downloads")
else:
    TEMP_LOG_DIR = os.path.join(SCRIPT_DIR, "py_downloads")
os.makedirs(TEMP_LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(TEMP_LOG_DIR, "error.log")
if DEV_MODE:
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "added_systems.json")
else:
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "added_systems.json")

#-------------------------------------------------------------------------------------#
#
#                 Constants        
##-------------------------------------------------------------------------------------#
FPS = 30
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
BASE_FONT_SIZE = 28 
BACKGROUND = (18, 20, 24)        # Dark background
SURFACE = (30, 34, 40)           # Card/surface background
SURFACE_HOVER = (40, 44, 50)     # Card hover state
SURFACE_SELECTED = (45, 50, 60)  # Card selected state
PRIMARY = (66, 165, 245)         # Primary accent (blue)
PRIMARY_DARK = (48, 123, 184)    # Darker primary
PRIMARY_LIGHT = (100, 181, 246)  # Lighter primary
SECONDARY = (102, 187, 106)      # Secondary accent (green)
SECONDARY_DARK = (76, 140, 79)   # Darker secondary
SECONDARY_LIGHT = (129, 199, 132) # Lighter secondary
TEXT_PRIMARY = (255, 255, 255)   # Primary text (white)
TEXT_SECONDARY = (189, 189, 189) # Secondary text (light gray)
TEXT_DISABLED = (117, 117, 117)  # Disabled text (darker gray)
WARNING = (255, 193, 7)          # Warning color (amber)
ERROR = (244, 67, 54)            # Error color (red)
SUCCESS = (76, 175, 80)          # Success color (green)
SHADOW_COLOR = (0, 0, 0, 60)     # Shadow color with alpha
GLOW_COLOR = (66, 165, 245, 40)  # Glow color for highlights
BORDER_RADIUS = 12               # Default border radius
CARD_PADDING = 8                 # Card padding
THUMBNAIL_BORDER_RADIUS = 8      # Thumbnail border radius
WHITE = TEXT_PRIMARY
BLACK = BACKGROUND
GREEN = SECONDARY
GRAY = TEXT_SECONDARY
FONT_SIZE = BASE_FONT_SIZE
NAVIGATION_INITIAL_DELAY = 100     # ms before repeating starts (much longer delay)
NAVIGATION_START_RATE = 400        # ms between repeats when starting (slow)
NAVIGATION_MAX_RATE = 100          # ms between repeats at maximum speed (fast)
NAVIGATION_ACCELERATION = 0.90     # rate multiplier each repeat (smaller = faster acceleration)
THUMBNAIL_SIZE = (96, 96)
DPAD_DEBOUNCE_MS = 100  # Minimum time between D-pad navigation actions
HIRES_IMAGE_SIZE = (400, 400) 

#-------------------------------------------------------------------------------------#
#
#                 LOG START        
##-------------------------------------------------------------------------------------#

try:
    log_dir = os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else "."
    os.makedirs(log_dir, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        f.write(f"Error Log - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n")
        f.write(f"Script directory: {SCRIPT_DIR}\n")
        f.write("-" * 80 + "\n")
    print(f"Log file initialized: {LOG_FILE}")
except Exception as e:
    print(f"Failed to initialize log file: {e}")

#-------------------------------------------------------------------------------------#
#
#                 Utils        
##-------------------------------------------------------------------------------------#

def get_responsive_font_size(base_size=BASE_FONT_SIZE):
    """Calculate responsive font size based on screen dimensions"""
    screen_width, screen_height = screen.get_size()
    # Scale based on screen width, with minimum and maximum limits
    scale_factor = min(screen_width / 800, screen_height / 600)
    font_size = max(16, min(int(base_size * scale_factor), 48))
    return font_size

def get_responsive_margin():
    """Calculate responsive margin based on screen size"""
    screen_width, screen_height = screen.get_size()
    return max(10, min(int(screen_width * 0.03), 40))

def get_responsive_spacing():
    """Calculate responsive spacing between elements"""
    screen_width, screen_height = screen.get_size()
    return max(5, min(int(screen_width * 0.015), 20))

def update_log_file_path():
    """Update LOG_FILE path to use the configured work directory with py_downloads subdirectory"""
    global LOG_FILE
    work_dir = settings.get("work_dir", TEMP_LOG_DIR)
    # Create py_downloads subdirectory within the user's work directory
    py_downloads_dir = os.path.join(work_dir, "py_downloads")
    os.makedirs(py_downloads_dir, exist_ok=True)
    LOG_FILE = os.path.join(py_downloads_dir, "error.log")

def log_error(error_msg, error_type=None, traceback_str=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] ERROR: {error_msg}\n"
    if error_type:
        log_message += f"Type: {error_type}\n"
    if traceback_str:
        log_message += f"Traceback:\n{traceback_str}\n"
    log_message += "-" * 80 + "\n"
    
    with open(LOG_FILE, "a") as f:
        f.write(log_message)


def format_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def decompress_nsz_file(nsz_file_path, output_dir, keys_path=None, progress_callback=None):
    """
    Unified NSZ decompression method that tries multiple approaches
    
    Args:
        nsz_file_path: Path to the NSZ file to decompress
        output_dir: Directory to extract NSP file(s) to
        keys_path: Path to Nintendo Switch keys file
        progress_callback: Optional callback for progress updates
        
    Returns:
        bool: True if decompression was successful, False otherwise
    """
    import shutil
    from pathlib import Path
    
    filename = os.path.basename(nsz_file_path)
    
    def update_progress(message, progress):
        if progress_callback:
            progress_callback(message, progress)
        else:
            print(message)
    
    actual_keys_path = settings.get("nsz_keys_path", "")
    nsz_success = False
    
    if actual_keys_path is not None and nsz_decompress:
        try:
            update_progress(f"Decompressing {filename} using NSZ library...", 30)
            nsz_decompress(Path(nsz_file_path), Path(output_dir), True, None, keys_path=actual_keys_path)
            nsz_success = True
            update_progress("NSZ library decompression successful", 80)
            print("NSZ decompression successful using nsz library")
        except Exception as e:
            error_msg = f"NSZ library decompression failed: {e}"
            print(error_msg)
            log_error(f"NSZ library method failed for {filename}: {str(e)}")
    
    if nsz_success:
        update_progress(f"Decompressing {filename}... Complete", 100)
        return True
    else:
        log_error(f"NSZ decompression failed for {filename}: All methods failed")
        update_progress(f"NSZ decompression failed for {filename}", 0)
        return False

def load_settings():
    """Load settings from config file"""
    # Default paths based on environment
    # Note: py_downloads subdirectory will be created within work_dir automatically
    if DEV_MODE:
        # Development mode - use local directories since /userdata might not exist
        default_work_dir = os.path.join(SCRIPT_DIR, "..", "downloads")
        default_roms_dir = os.path.join(SCRIPT_DIR, "..", "roms")
    elif os.path.exists("/userdata") and os.access("/userdata", os.W_OK):
        # Console environment with writable /userdata
        default_work_dir = "/userdata/downloads"
        default_roms_dir = "/userdata/roms"
    else:
        # Fallback - use script directory
        default_work_dir = os.path.join(SCRIPT_DIR, "downloads")
        default_roms_dir = os.path.join(SCRIPT_DIR, "roms")
    
    default_settings = {
        "enable_boxart": True,
        "view_type": "list",
        "usa_only": False,
        "work_dir": default_work_dir,
        "roms_dir": default_roms_dir,
        "nsz_keys_path": "",
        "archive_json_path": "",
        "cache_enabled": True,
        "archive_json_url": ""
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_settings = json.load(f)
                # Merge with defaults to handle new settings
                default_settings.update(loaded_settings)
        else:
            # Create config file with defaults
            save_settings(default_settings)
    except Exception as e:
        log_error("Failed to load settings, using defaults", type(e).__name__, traceback.format_exc())
    
    return default_settings

def save_settings(settings_to_save):
        """Save settings to config file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(settings_to_save, f, indent=2)
        except Exception as e:
            log_error("Failed to save settings", type(e).__name__, traceback.format_exc())
#-------------------------------------------------------------------------------------#
#
#                 Pygame Init        
##-------------------------------------------------------------------------------------#
try:
    print("Initializing pygame...")
    pygame.init()
    print("Pygame initialized successfully")    
    print("Testing pygame display...")
    test_screen = pygame.display.set_mode((100, 100))
    print("Display test successful")
    pygame.display.quit()
    print("Display cleanup successful")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Console Utilities")
    clock = pygame.time.Clock()    
    responsive_font_size = get_responsive_font_size()
    font = pygame.font.Font(None, responsive_font_size)
    pygame.joystick.init()
    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
    else:
        print("No joystick detected, use keyboard: Arrow keys, Enter, Escape, Space")
    touchscreen_available = False
    mouse_available = True
    try:
        import pygame._sdl2.touch
        touch_device_count = pygame._sdl2.touch.get_num_devices()
        if touch_device_count > 0:
            touchscreen_available = True
            print(f"Touchscreen detected: {touch_device_count} touch device(s) available")
        else:
            print("No touchscreen detected")
    except ImportError:
        print("Touch support not available in this pygame version")
    
    print("Mouse navigation available")

#-------------------------------------------------------------------------------------#
#
#                 Pygame Required Variables       
##-------------------------------------------------------------------------------------#
    data = []
    selected_system = 0
    selected_games = set()
    game_list = []
    mode = "systems"  # systems, games, settings, utils, add_systems, systems_settings, or system_settings    
    available_systems = []
    add_systems_highlighted = 0
    systems_settings_highlighted = 0
    system_settings_highlighted = 0
    selected_system_for_settings = None
    current_page = 0
    total_pages = 1
    highlighted = 0
    settings_scroll_offset = 0
    search_mode = False
    search_query = ""
    url_input_context = "direct_download" 
    filtered_game_list = []
    char_selector_mode = False
    char_x = 0
    char_y = 0    
    show_search_input = False
    search_input_text = ""
    search_cursor_position = 0
    search_cursor_blink_time = 0    
    navigation_state = {
        'up': False,
        'down': False, 
        'left': False,
        'right': False
    }
    navigation_start_time = {
        'up': 0,
        'down': 0,
        'left': 0, 
        'right': 0
    }
    navigation_last_repeat = {
        'up': 0,
        'down': 0,
        'left': 0,
        'right': 0  
    }
    navigation_velocity = {
        'up': 0,
        'down': 0,
        'left': 0,
        'right': 0
    }
    menu_item_rects = []  # Store rectangles for clickable menu items
    menu_scroll_offset = 0  # Current scroll offset (start_idx) for click mapping
    scroll_accumulated = 0  # For smooth scrolling
    touch_start_pos = None  # Starting position of touch
    touch_start_time = 0  # Time when touch started
    touch_last_pos = None  # Last touch position for motion tracking
    is_scrolling = False  # Whether user is currently scrolling
    scroll_threshold = 15  # Pixels to move before it's considered scrolling
    tap_time_threshold = 500  # Max ms for a tap vs scroll
    scroll_sensitivity = 0.5  # Touch scroll sensitivity multiplier
    last_click_time = 0
    last_clicked_item = -1
    double_click_threshold = 500  # Max ms between clicks for double-click
    back_button_rect = None
    search_button_rect = None
    download_button_rect = None
    modal_char_rects = []  # For character selection modals
    modal_back_button_rect = None  # Back button for modals
    settings = {}    
    controller_mapping = {}
    settings_list = [
        "Select Archive Json",
        "Work Directory",
        "ROMs Directory",
        "NSZ Keys",
        "Remap Controller",
        "Add Systems",
        "Systems Settings",
        "--- VIEW OPTIONS ---",
        "Enable Box-art Display",
        "View Type",
        "USA Games Only"
    ]
    image_cache = {}
    image_queue = Queue()
    hires_image_cache = {}
    hires_image_queue = Queue()
    show_game_details = False
    current_game_detail = None
    close_button_rect = None    
    show_folder_browser = False
    folder_browser_current_path = "/"
    folder_browser_items = []
    folder_browser_highlighted = 0
    folder_browser_scroll_offset = 0
    folder_browser_item_rects = []
    folder_select_button_rect = None
    folder_cancel_button_rect = None
    show_system_input = False
    system_input_text = ""
    selected_system_to_add = None
    show_folder_name_input = False
    folder_name_input_text = ""
    folder_name_cursor_position = 0
    folder_name_char_index = 0  # Current character being selected (0-35 for A-Z, 0-9)
    show_url_input = False
    url_input_text = ""
    url_cursor_position = 0
    show_controller_mapping = False
    running = True
    button_delay = 0
    last_dpad_state = (0, 0)  # Track last D-pad state to detect actual changes
    last_dpad_time = 0  # Track when last D-pad navigation occurred
#-------------------------------------------------------------------------------------#
#
#                 Navigation handlers        
##-------------------------------------------------------------------------------------#
    
    def update_navigation_state():
        """Update navigation state based on current joystick/controller input"""
        global navigation_state, navigation_start_time, navigation_last_repeat, navigation_velocity
        
        current_time = pygame.time.get_ticks()
        
        # Reset all navigation states first
        for direction in ['up', 'down', 'left', 'right']:
            navigation_state[direction] = False
        
        # Check joystick state if available
        if joystick and joystick.get_init():
            # Check hat-based D-pad
            if joystick.get_numhats() > 0:
                hat = joystick.get_hat(0)
                if hat[1] > 0:  # Up
                    navigation_state['up'] = True
                elif hat[1] < 0:  # Down  
                    navigation_state['down'] = True
                if hat[0] < 0:  # Left
                    navigation_state['left'] = True
                elif hat[0] > 0:  # Right
                    navigation_state['right'] = True
            
            # Check button-based D-pad
            for direction in ['up', 'down', 'left', 'right']:
                button_info = get_controller_button(direction)
                if isinstance(button_info, int) and joystick.get_numbuttons() > button_info:
                    if joystick.get_button(button_info):
                        navigation_state[direction] = True
        
        # Check keyboard state as fallback
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            navigation_state['up'] = True
        if keys[pygame.K_DOWN]:
            navigation_state['down'] = True
        if keys[pygame.K_LEFT]:
            navigation_state['left'] = True
        if keys[pygame.K_RIGHT]:
            navigation_state['right'] = True
        
        # Update timing for newly pressed directions
        for direction in ['up', 'down', 'left', 'right']:
            if navigation_state[direction]:
                if navigation_start_time[direction] == 0:
                    # First press - record start time and reset velocity
                    navigation_start_time[direction] = current_time
                    navigation_last_repeat[direction] = current_time
                    navigation_velocity[direction] = NAVIGATION_START_RATE
            else:
                # Released - reset timing and velocity
                navigation_start_time[direction] = 0
                navigation_last_repeat[direction] = 0
                navigation_velocity[direction] = 0
    
    def should_navigate(direction):
        """Check if we should trigger navigation for a given direction with progressive acceleration"""
        if not navigation_state[direction]:
            return False
            
        current_time = pygame.time.get_ticks()
        start_time = navigation_start_time[direction]
        last_repeat = navigation_last_repeat[direction]
        current_velocity = navigation_velocity[direction]
        
        # Never allow navigation before the initial delay - let discrete events handle immediate response
        if current_time - start_time < NAVIGATION_INITIAL_DELAY:
            return False
            
        # Check if enough time has passed for the next repeat based on current velocity
        time_since_last = current_time - last_repeat
        if time_since_last >= current_velocity:
            navigation_last_repeat[direction] = current_time
            
            # Accelerate for next repeat (but don't go below minimum rate)
            new_velocity = current_velocity * NAVIGATION_ACCELERATION
            navigation_velocity[direction] = max(new_velocity, NAVIGATION_MAX_RATE)
            
            return True
            
        return False
    
    def is_direction_held(direction):
        """Check if a direction is currently being held"""
        return navigation_state.get(direction, False)
    
    def handle_continuous_navigation():
        """Handle continuous navigation by checking held directions"""
        global movement_occurred
        
        # Check each direction for continuous navigation
        for direction in ['up', 'down', 'left', 'right']:
            if should_navigate(direction):
                # Convert direction to hat coordinates
                if direction == 'up':
                    hat = (0, 1)
                elif direction == 'down':
                    hat = (0, -1) 
                elif direction == 'left':
                    hat = (-1, 0)
                elif direction == 'right':
                    hat = (1, 0)
                
                # Call simplified navigation logic directly
                handle_directional_navigation_continuous(direction, hat)
                break  # Only process one direction per frame to avoid conflicts
    
    def handle_directional_navigation_continuous(direction, hat):
        """Simplified navigation function for continuous navigation (no event needed)"""
        global movement_occurred, search_cursor_position, folder_name_char_index, folder_browser_highlighted
        global add_systems_highlighted, highlighted, systems_settings_highlighted, system_settings_highlighted, url_cursor_position
        
        movement_occurred = False
        
        if hat[1] != 0 and not show_game_details:  # Up or Down
            if show_search_input:
                # Navigate character selection up/down for search
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if direction == "up":
                    if search_cursor_position >= chars_per_row:
                        search_cursor_position -= chars_per_row
                        movement_occurred = True
                elif direction == "down":
                    if search_cursor_position + chars_per_row < total_chars:
                        search_cursor_position += chars_per_row
                        movement_occurred = True
            elif show_folder_name_input:
                # Navigate character selection up/down
                chars_per_row = 13
                total_chars = 36  # A-Z + 0-9
                if direction == "up":
                    if folder_name_char_index >= chars_per_row:
                        folder_name_char_index -= chars_per_row
                        movement_occurred = True
                elif direction == "down":
                    if folder_name_char_index + chars_per_row < total_chars:
                        folder_name_char_index += chars_per_row
                        movement_occurred = True
            elif show_folder_browser:
                # Folder browser navigation
                if direction == "up":
                    if folder_browser_items and folder_browser_highlighted > 0:
                        folder_browser_highlighted -= 1
                        movement_occurred = True
                elif direction == "down":
                    if folder_browser_items and folder_browser_highlighted < len(folder_browser_items) - 1:
                        folder_browser_highlighted += 1
                        movement_occurred = True
            elif mode == "add_systems":
                # Add systems navigation
                if direction == "up":
                    if available_systems and add_systems_highlighted > 0:
                        add_systems_highlighted -= 1
                        movement_occurred = True
                elif direction == "down":
                    if available_systems and add_systems_highlighted < len(available_systems) - 1:
                        add_systems_highlighted += 1
                        movement_occurred = True
            elif mode == "games" and settings["view_type"] == "grid":
                # Grid navigation: move up/down
                cols = 4
                if direction == "up":
                    if highlighted >= cols:
                        highlighted -= cols
                        movement_occurred = True
                elif direction == "down":
                    if highlighted + cols < len(game_list):
                        highlighted += cols
                        movement_occurred = True
            else:
                # Regular navigation for list view and other modes
                if mode == "games":
                    current_game_list = filtered_game_list if search_mode and search_query else game_list
                    max_items = len(current_game_list)
                elif mode == "settings":
                    max_items = len(settings_list)
                elif mode == "utils":
                    max_items = 2  # Download from URL and NSZ to NSP Converter
                elif mode == "credits":
                    max_items = 0  # No navigable items in credits
                elif mode == "add_systems":
                    max_items = len(available_systems)
                elif mode == "systems_settings":
                    configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                    max_items = len(configurable_systems)
                elif mode == "system_settings":
                    max_items = 2  # Hide from menu + Custom ROM folder
                else:  # systems
                    visible_systems = get_visible_systems()
                    max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                
                if max_items > 0:
                    if mode == "add_systems":
                        if direction == "up":
                            add_systems_highlighted = (add_systems_highlighted - 1) % max_items
                        elif direction == "down":
                            add_systems_highlighted = (add_systems_highlighted + 1) % max_items
                    elif mode == "systems_settings":
                        if direction == "up":
                            systems_settings_highlighted = (systems_settings_highlighted - 1) % max_items
                        elif direction == "down":
                            systems_settings_highlighted = (systems_settings_highlighted + 1) % max_items
                    elif mode == "system_settings":
                        if direction == "up":
                            system_settings_highlighted = (system_settings_highlighted - 1) % max_items
                        elif direction == "down":
                            system_settings_highlighted = (system_settings_highlighted + 1) % max_items
                    else:
                        if direction == "up":
                            highlighted = (highlighted - 1) % max_items
                        elif direction == "down":
                            highlighted = (highlighted + 1) % max_items
                    movement_occurred = True
        elif hat[0] != 0 and not show_game_details:  # Left or Right
            if show_search_input:
                # Navigate character selection left/right for search
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if direction == "left":
                    if search_cursor_position % chars_per_row > 0:
                        search_cursor_position -= 1
                        movement_occurred = True
                elif direction == "right":
                    if search_cursor_position % chars_per_row < chars_per_row - 1 and search_cursor_position < total_chars - 1:
                        search_cursor_position += 1
                        movement_occurred = True
            elif show_folder_name_input:
                # Navigate character selection left/right
                chars_per_row = 13
                total_chars = 36  # A-Z + 0-9
                if direction == "left":
                    if folder_name_char_index % chars_per_row > 0:
                        folder_name_char_index -= 1
                        movement_occurred = True
                elif direction == "right":
                    if folder_name_char_index % chars_per_row < chars_per_row - 1 and folder_name_char_index < total_chars - 1:
                        folder_name_char_index += 1
                        movement_occurred = True
            elif mode == "games" and settings["view_type"] == "grid":
                # Grid navigation: move left/right
                cols = 4
                if direction == "left":
                    if highlighted % cols > 0:
                        highlighted -= 1
                        movement_occurred = True
                elif direction == "right":
                    if highlighted % cols < cols - 1 and highlighted < len(game_list) - 1:
                        highlighted += 1
                        movement_occurred = True
            else:
                # List navigation: jump to different letter
                items = game_list
                old_highlighted = highlighted
                if direction == "left":
                    highlighted = find_next_letter_index(items, highlighted, -1)
                elif direction == "right":
                    highlighted = find_next_letter_index(items, highlighted, 1)
                if highlighted != old_highlighted:
                    movement_occurred = True
    
    def draw_background():
        """Draw the background image or solid color for all screens"""
        if background_image:
            # Scale and draw the background image to fill the screen
            screen_size = screen.get_size()
            scaled_bg = pygame.transform.scale(background_image, screen_size)
            screen.blit(scaled_bg, (0, 0))
            
            # Add semi-transparent overlay for better text readability
            overlay = pygame.Surface(screen_size)
            overlay.set_alpha(100)  # Adjust transparency as needed
            overlay.fill((0, 0, 0))  # Black overlay
            screen.blit(overlay, (0, 0))
        else:
            draw_background()

    def load_background_image():
        """Load the background image from assets"""
        try:
            # Try multiple possible paths for the background image
            possible_paths = [
                os.path.join(SCRIPT_DIR, "assets", "images", "background.png"),
                os.path.join(os.getcwd(), "assets", "images", "background.png"),
                os.path.join("assets", "images", "background.png"),
                "./assets/images/background.png"
            ]
            
            print(f"SCRIPT_DIR: {SCRIPT_DIR}")
            print(f"Current working directory: {os.getcwd()}")
            
            for background_path in possible_paths:
                print(f"Trying path: {background_path}")
                print(f"Path exists: {os.path.exists(background_path)}")
                
                if os.path.exists(background_path):
                    background_image = pygame.image.load(background_path)
                    print(f"Background image loaded successfully from: {background_path}")
                    print(f"Image size: {background_image.get_size()}")
                    return background_image
            
            print("Background image file not found in any location")
            
        except Exception as e:
            print(f"Failed to load background image: {e}")
            log_error(f"Failed to load background image", type(e).__name__, traceback.format_exc())
        return None

    def handle_touch_click_event(pos):
        """Handle touch/click events by checking if they hit any menu items or buttons"""
        global highlighted, mode, selected_system, show_game_details, current_game_detail
        global add_systems_highlighted, systems_settings_highlighted, system_settings_highlighted
        global show_search_input, show_url_input, show_folder_name_input, show_folder_browser
        global last_click_time, last_clicked_item
        
        x, y = pos
        
        # First check if we're in a modal and handle modal interactions
        if (show_search_input or show_url_input or show_folder_name_input or 
            show_folder_browser or show_game_details):
            if handle_modal_touch_click(pos):
                return True
        
        # Then check if touch/click hit any on-screen buttons
        if handle_touch_button_click(pos):
            return True
        
        # Check if click/touch hit any menu item rectangles
        for i, rect in enumerate(menu_item_rects):
            if rect.collidepoint(x, y):
                # Calculate actual item index accounting for scrolling
                actual_item_index = menu_scroll_offset + i
                
                # Update highlighted item and trigger selection
                if mode == "systems":
                    visible_systems = get_visible_systems()
                    regular_systems = [d['name'] for d in visible_systems]
                    systems_with_options = regular_systems + ["Utils", "Settings", "Credits"]
                    
                    if actual_item_index < len(systems_with_options):
                        highlighted = actual_item_index
                        # Simulate select button press to activate the item
                        handle_menu_selection()
                        return True
                        
                elif mode == "games":
                    current_game_list = filtered_game_list if search_mode and search_query else game_list
                    if actual_item_index < len(current_game_list):
                        # Check for double-click to select/deselect game
                        current_time = pygame.time.get_ticks()
                        if (actual_item_index == last_clicked_item and 
                            current_time - last_click_time < double_click_threshold):
                            # Double-click detected - toggle game selection
                            highlighted = actual_item_index
                            handle_menu_selection()  # This will toggle the game selection
                            last_clicked_item = -1  # Reset to prevent triple-click
                        else:
                            # Single click - just highlight
                            highlighted = actual_item_index
                            last_clicked_item = actual_item_index
                            last_click_time = current_time
                        return True
                        
                elif mode == "settings":
                    if actual_item_index < len(settings_list):
                        # Skip divider clicks
                        if actual_item_index == 7:  # Divider index (updated)
                            return True  # Do nothing for divider clicks
                        highlighted = actual_item_index
                        handle_menu_selection()
                        return True
                        
                elif mode == "utils":
                    utils_items = ["Download from URL", "NSZ to NSP Converter"]
                    if actual_item_index < len(utils_items):
                        highlighted = actual_item_index
                        handle_menu_selection()
                        return True
                        
        return False

    def handle_modal_touch_click(pos):
        """Handle touch/click events in modals"""
        global show_search_input, search_cursor_position, search_input_text
        global show_url_input, show_folder_name_input, show_folder_browser
        global search_query, search_mode, filtered_game_list, highlighted
        global show_game_details, current_game_detail, download_button_rect, close_button_rect
        global folder_select_button_rect, folder_cancel_button_rect, folder_browser_current_path
        global folder_browser_highlighted, folder_browser_items, selected_system_to_add, settings, mode
        
        x, y = pos
        
        # Handle game details modal
        if show_game_details:
            # Check download button
            if download_button_rect and download_button_rect.collidepoint(x, y):
                if current_game_detail is not None:
                    # Find the index of the current game detail in the game list
                    current_game_list = filtered_game_list if search_mode and search_query else game_list
                    try:
                        if isinstance(current_game_detail, dict):
                            game_index = next((i for i, game in enumerate(current_game_list) if game == current_game_detail), None)
                        else:
                            game_index = next((i for i, game in enumerate(current_game_list) if game == current_game_detail), None)
                        
                        if game_index is not None:
                            # Start download for this single game
                            download_files(selected_system, {game_index})
                            show_game_details = False
                            current_game_detail = None
                    except Exception as e:
                        print(f"Error starting download: {e}")
                return True
                
            # Check close button  
            if close_button_rect and close_button_rect.collidepoint(x, y):
                show_game_details = False
                current_game_detail = None
                return True
                
        # Handle search input modal
        if show_search_input:
            # Check back button
            if modal_back_button_rect and modal_back_button_rect.collidepoint(x, y):
                show_search_input = False
                return True
                
            # Check character buttons
            for char_rect, char_index, char in modal_char_rects:
                if char_rect.collidepoint(x, y):
                    # Simulate character selection
                    search_cursor_position = char_index
                    
                    # Execute the character action
                    if char == "DEL":
                        if search_input_text:
                            search_input_text = search_input_text[:-1]
                    elif char == "CLEAR":
                        search_input_text = ""
                    elif char == "DONE":
                        # Finish search input
                        show_search_input = False
                        search_query = search_input_text
                        if search_query:
                            search_mode = True
                            filtered_game_list = filter_games_by_search(game_list, search_query)
                            highlighted = 0
                        else:
                            search_mode = False
                            filtered_game_list = []
                    else:
                        # Add character to search query
                        search_input_text += char
                    return True
                    
        # Handle folder browser modal
        if show_folder_browser:
            # Check if click is on any folder browser item
            for item_rect, item_idx in folder_browser_item_rects:
                if item_rect.collidepoint(x, y):
                    # Update highlighted item and trigger selection
                    global folder_browser_highlighted
                    folder_browser_highlighted = item_idx
                    
                    # Simulate select action (same logic as keyboard/joystick)
                    if folder_browser_items and folder_browser_highlighted < len(folder_browser_items):
                        selected_item = folder_browser_items[folder_browser_highlighted]
                        
                        if selected_item["type"] == "parent":
                            # Go back to parent directory
                            global folder_browser_current_path
                            parent_path = os.path.dirname(folder_browser_current_path)
                            if parent_path != folder_browser_current_path:
                                folder_browser_current_path = parent_path
                                load_folder_contents(folder_browser_current_path)
                        elif selected_item["type"] == "folder":
                            # Enter folder
                            new_path = selected_item["path"]
                            folder_browser_current_path = new_path
                            load_folder_contents(folder_browser_current_path)
                        elif selected_item["type"] in ["keys_file", "json_file", "nsz_file"]:
                            # Select file - use same logic as keyboard handling
                            if selected_system_to_add and selected_system_to_add.get("type") == "nsz_keys":
                                global settings
                                settings["nsz_keys_path"] = selected_item["path"]
                                save_settings(settings)
                                show_folder_browser = False
                                selected_system_to_add = None
                                draw_loading_message("ROMs directory changed. Restarting...")
                                pygame.time.wait(2000)
                                restart_app()
                            elif selected_item["type"] == "nsz_file":
                                # Handle NSZ file conversion
                                if selected_system_to_add and selected_system_to_add.get("type") == "nsz_converter":
                                    convert_nsz_to_nsp(selected_item["path"])
                                    show_folder_browser = False
                                    selected_system_to_add = None
                            elif selected_item["type"] == "json_file":
                                # Handle archive JSON file selection  
                                if selected_system_to_add and selected_system_to_add.get("type") == "archive_json":
                                    settings["archive_json_path"] = selected_item["path"]
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                    return True
            
            # Check folder browser buttons
            if folder_select_button_rect and folder_select_button_rect.collidepoint(x, y):
                # Handle "Select Folder/File" button - same logic as detail/Y button press
                if selected_system_to_add is not None:
                    if selected_system_to_add.get("type") == "work_dir":
                        # Select current folder as work directory
                        settings["work_dir"] = folder_browser_current_path
                        save_settings(settings)
                        show_folder_browser = False
                        selected_system_to_add = None
                    elif selected_system_to_add.get("type") == "nsz_keys":
                        # Select current folder path for NSZ keys
                        settings["nsz_keys_path"] = folder_browser_current_path
                        save_settings(settings)
                        show_folder_browser = False
                        selected_system_to_add = None
                    elif selected_system_to_add.get("type") == "archive_json":
                        # Select current folder path for archive JSON
                        settings["archive_json_path"] = folder_browser_current_path
                        save_settings(settings)
                        show_folder_browser = False
                        selected_system_to_add = None
                    elif selected_system_to_add.get("type") == "system_folder":
                        # Select current folder for system ROM folder
                        system_name = selected_system_to_add.get("system_name", "")
                        if system_name:
                            if "system_settings" not in settings:
                                settings["system_settings"] = {}
                            if system_name not in settings["system_settings"]:
                                settings["system_settings"][system_name] = {}
                            settings["system_settings"][system_name]['custom_folder'] = folder_browser_current_path
                            save_settings(settings)
                            show_folder_browser = False
                            selected_system_to_add = None
                    else:
                        # ROMs directory selection
                        settings["roms_dir"] = folder_browser_current_path
                        save_settings(settings)
                        show_folder_browser = False
                        # Reset state
                        selected_system_to_add = None
                        show_folder_browser = False
                        mode = "systems"
                        highlighted = 0
                return True
                
            # Check folder browser cancel button
            if folder_cancel_button_rect and folder_cancel_button_rect.collidepoint(x, y):
                # Close folder browser without selecting
                show_folder_browser = False
                selected_system_to_add = None
                return True
        
        return False

    def handle_scroll_event(scroll_y):
        """Handle mouse wheel or touch scroll events"""
        global highlighted, scroll_accumulated
        global folder_browser_highlighted, search_cursor_position
        
        # Check if we're in a modal first
        if show_folder_browser:
            # Handle folder browser scrolling
            if scroll_y > 0:
                # Scroll up - move selection up
                if folder_browser_highlighted > 0:
                    folder_browser_highlighted -= 1
            elif scroll_y < 0:
                # Scroll down - move selection down
                if folder_browser_highlighted < len(folder_browser_items) - 1:
                    folder_browser_highlighted += 1
            return True
            
        elif show_search_input:
            # Handle search input character selection scrolling
            chars = "abcdefghijklmnopqrstuvwxyz0123456789 DEL CLEAR DONE"
            if scroll_y > 0:
                # Scroll up - move character selection up
                if search_cursor_position > 0:
                    search_cursor_position -= 1
            elif scroll_y < 0:
                # Scroll down - move character selection down
                if search_cursor_position < len(chars.split()) - 1:
                    search_cursor_position += 1
            return True
        
        # Handle main menu scrolling (existing logic)
        # Accumulate scroll for smooth scrolling
        scroll_accumulated += scroll_y
        
        # Convert accumulated scroll to navigation steps
        scroll_threshold = 3  # Adjust for scroll sensitivity
        if abs(scroll_accumulated) >= scroll_threshold:
            steps = int(scroll_accumulated / scroll_threshold)
            scroll_accumulated = scroll_accumulated % scroll_threshold
            
            # Navigate up or down based on scroll direction
            if steps > 0:
                # Scroll up - move selection up
                for _ in range(abs(steps)):
                    navigate_up()
            elif steps < 0:
                # Scroll down - move selection down  
                for _ in range(abs(steps)):
                    navigate_down()
                    
        return True

    def navigate_up():
        """Helper function to navigate up in current context"""
        global highlighted, add_systems_highlighted, systems_settings_highlighted, system_settings_highlighted
        
        if mode == "systems":
            visible_systems = get_visible_systems()
            systems_with_options = [d['name'] for d in visible_systems] + ["Utils", "Settings", "Credits"]
            if highlighted > 0:
                highlighted -= 1
                
        elif mode == "games":
            current_game_list = filtered_game_list if search_mode and search_query else game_list
            if settings["view_type"] == "grid":
                cols = 4
                if highlighted >= cols:
                    highlighted -= cols
            else:
                if highlighted > 0:
                    highlighted -= 1
                    
        elif mode == "settings":
            if highlighted > 0:
                highlighted -= 1
                # Skip over divider when navigating up
                if highlighted == 7:  # Divider index (updated)
                    highlighted -= 1
                
        elif mode == "add_systems":
            if add_systems_highlighted > 0:
                add_systems_highlighted -= 1

    def navigate_down():
        """Helper function to navigate down in current context"""
        global highlighted, add_systems_highlighted, systems_settings_highlighted, system_settings_highlighted
        
        if mode == "systems":
            visible_systems = get_visible_systems()
            systems_with_options = [d['name'] for d in visible_systems] + ["Utils", "Settings", "Credits"]
            if highlighted < len(systems_with_options) - 1:
                highlighted += 1
                
        elif mode == "games":
            current_game_list = filtered_game_list if search_mode and search_query else game_list
            if settings["view_type"] == "grid":
                cols = 4
                rows = (len(current_game_list) + cols - 1) // cols
                if highlighted + cols < len(current_game_list):
                    highlighted += cols
            else:
                if highlighted < len(current_game_list) - 1:
                    highlighted += 1
                    
        elif mode == "settings":
            if highlighted < len(settings_list) - 1:
                highlighted += 1
                # Skip over divider when navigating down
                if highlighted == 7:  # Divider index (updated)
                    highlighted += 1
                
        elif mode == "add_systems":
            if add_systems_highlighted < len(available_systems) - 1:
                add_systems_highlighted += 1

    def handle_menu_selection():
        """Handle menu item selection - simulate button press"""
        global mode, highlighted, selected_system, game_list, selected_games, current_page
        global add_systems_highlighted, systems_settings_highlighted, system_settings_highlighted
        global settings_scroll_offset, selected_system_for_settings
        global show_folder_browser, folder_browser_current_path, selected_system_to_add
        global show_url_input, url_input_context, show_controller_mapping, settings
        
        if mode == "systems":
            # Use helper function for consistent filtering
            visible_systems = get_visible_systems()
            systems_count = len(visible_systems)
            
            if highlighted == systems_count:  # Utils option
                mode = "utils"
                highlighted = 0
            elif highlighted == systems_count + 1:  # Settings option
                mode = "settings"
                highlighted = 0
                settings_scroll_offset = 0
            elif highlighted == systems_count + 2:  # Credits option (always at the end)
                mode = "credits"
                highlighted = 0
            elif highlighted < systems_count:
                # Map visible system index to original data index
                selected_visible_system = visible_systems[highlighted]
                selected_system = get_system_index_by_name(selected_visible_system['name'])
                current_page = 0
                game_list = list_files(selected_system, current_page)
                selected_games = set()
                mode = "games"
                highlighted = 0
                
        elif mode == "games":
            # Handle game selection with search mode support
            current_game_list = filtered_game_list if search_mode and search_query else game_list
            if highlighted < len(current_game_list):
                # Get the actual game from the current list
                selected_game = current_game_list[highlighted]
                # Find the original index in game_list for selected_games tracking
                if search_mode and search_query:
                    # In search mode, find original index
                    original_index = next((i for i, game in enumerate(game_list) if game == selected_game), None)
                    if original_index is not None:
                        if original_index in selected_games:
                            selected_games.remove(original_index)
                        else:
                            selected_games.add(original_index)
                else:
                    # Normal mode, use highlighted directly
                    if highlighted in selected_games:
                        selected_games.remove(highlighted)
                    else:
                        selected_games.add(highlighted)
                        
        elif mode == "settings":
            # Handle settings selection (updated for new organization without GitHub update)
            # Skip divider (index 7)
            if highlighted == 7:  # Divider - do nothing
                pass
            elif highlighted == 0:  # Select Archive Json
                # Open folder browser for JSON files
                show_folder_browser = True
                # Use current archive path or default to workdir where download.json is
                current_archive = settings.get("archive_json_path", "")
                if current_archive and os.path.exists(os.path.dirname(current_archive)):
                    folder_browser_current_path = os.path.dirname(current_archive)
                else:
                    # Default to workdir where download.json is located
                    workdir_path = os.path.join(SCRIPT_DIR, "..", "workdir")
                    if os.path.exists(workdir_path):
                        folder_browser_current_path = os.path.abspath(workdir_path)
                    else:
                        folder_browser_current_path = SCRIPT_DIR
                load_folder_contents(folder_browser_current_path)
                # Set a flag to indicate we're selecting archive JSON
                selected_system_to_add = {"name": "Archive JSON", "type": "archive_json"}
            elif highlighted == 1:  # Work Directory
                # Open folder browser for work directory selection
                show_folder_browser = True
                # Use current work_dir or fallback to a sensible default
                current_work = settings.get("work_dir", "")
                if not current_work or not os.path.exists(os.path.dirname(current_work)):
                    # Use a fallback based on environment
                    if os.path.exists("/userdata") and os.access("/userdata", os.R_OK):
                        folder_browser_current_path = "/userdata"
                    else:
                        folder_browser_current_path = SCRIPT_DIR  
                else:
                    folder_browser_current_path = current_work
                load_folder_contents(folder_browser_current_path)
                # Set a flag to indicate we're selecting work directory
                selected_system_to_add = {"name": "Work Directory", "type": "work_dir"}
            elif highlighted == 2:  # ROMs Directory
                # Open folder browser
                show_folder_browser = True
                # Use current roms_dir or fallback to a sensible default
                current_roms = settings.get("roms_dir", "")
                if not current_roms or not os.path.exists(os.path.dirname(current_roms)):
                    # Use a fallback based on environment
                    if os.path.exists("/userdata") and os.access("/userdata", os.R_OK):
                        folder_browser_current_path = "/userdata/roms"
                    else:
                        folder_browser_current_path = os.path.expanduser("~")  # Home directory
                else:
                    folder_browser_current_path = current_roms
                load_folder_contents(folder_browser_current_path)
            elif highlighted == 3:  # NSZ Keys
                # Open folder browser for .keys files
                show_folder_browser = True
                # Use current keys path or default to home directory
                current_keys = settings.get("nsz_keys_path", "")
                if current_keys and os.path.exists(os.path.dirname(current_keys)):
                    folder_browser_current_path = os.path.dirname(current_keys)
                else:
                   folder_browser_current_path = SCRIPT_DIR
                load_folder_contents(folder_browser_current_path)
                # Set a flag to indicate we're selecting NSZ keys
                selected_system_to_add = {"name": "NSZ Keys", "type": "nsz_keys"}
            elif highlighted == 4:  # Remap Controller
                # Trigger controller remapping
                show_controller_mapping = True
            elif highlighted == 5:  # Add Systems
                mode = "add_systems"
                highlighted = 0
                add_systems_highlighted = 0
                # Load available systems in background
                load_available_systems()
            elif highlighted == 6:  # Systems Settings
                mode = "systems_settings"
                systems_settings_highlighted = 0
                highlighted = 0
            elif highlighted == 8:  # Enable Box-art Display
                settings["enable_boxart"] = not settings["enable_boxart"]
                save_settings(settings)
            elif highlighted == 9:  # View Type
                settings["view_type"] = "grid" if settings["view_type"] == "list" else "list"
                save_settings(settings)
            elif highlighted == 10:  # USA Games Only
                settings["usa_only"] = not settings["usa_only"]
                save_settings(settings)
            
        elif mode == "utils":
            if highlighted == 0:  # Download from URL
                # Show URL input modal for direct download
                show_url_input_modal("direct_download")
            elif highlighted == 1:  # NSZ to NSP Converter
                # Start NSZ file browser
                show_folder_browser = True
                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                selected_system_to_add = {"name": "NSZ to NSP Converter", "type": "nsz_converter"}
                load_folder_contents(folder_browser_current_path)
                highlighted = 0

    def draw_touch_buttons():
        """Draw on-screen buttons when touch/mouse is available"""
        global back_button_rect, search_button_rect, download_button_rect
        
        if not touchscreen_available:
            return
            
        screen_width, screen_height = screen.get_size()
        button_height = 40
        button_width = 80
        button_margin = 10
        
        # Position buttons at bottom of screen
        button_y = screen_height - button_height - button_margin
        
        # Back button (always show except on systems screen)
        if mode != "systems":
            back_x = button_margin
            back_button_rect = pygame.Rect(back_x, button_y, button_width, button_height)
            
            # Draw back button background
            pygame.draw.rect(screen, SURFACE, back_button_rect, border_radius=8)
            pygame.draw.rect(screen, PRIMARY, back_button_rect, 2, border_radius=8)
            
            # Draw back button text
            back_text = font.render("Back", True, TEXT_PRIMARY)
            text_x = back_x + (button_width - back_text.get_width()) // 2
            text_y = button_y + (button_height - back_text.get_height()) // 2
            screen.blit(back_text, (text_x, text_y))
        
        # Download button (only show in games mode when games are selected)
        if mode == "games" and selected_games:
            download_width = 150  # Much wider button for "Start Download" text
            download_x = (screen_width - download_width) // 2  # Center the download button
            download_button_rect = pygame.Rect(download_x, button_y, download_width, button_height)
            
            # Draw download button background
            pygame.draw.rect(screen, SUCCESS, download_button_rect, border_radius=8)
            pygame.draw.rect(screen, TEXT_PRIMARY, download_button_rect, 2, border_radius=8)
            
            # Draw download button text
            download_text = font.render("Start Download", True, TEXT_PRIMARY)
            text_x = download_x + (download_width - download_text.get_width()) // 2
            text_y = button_y + (button_height - download_text.get_height()) // 2
            screen.blit(download_text, (text_x, text_y))
        
        # Search button (only show in games mode and when no games selected)
        elif mode == "games" and not show_search_input:
            search_x = screen_width - button_width - button_margin
            search_button_rect = pygame.Rect(search_x, button_y, button_width, button_height)
            
            # Draw search button background
            pygame.draw.rect(screen, SURFACE, search_button_rect, border_radius=8)
            pygame.draw.rect(screen, SECONDARY, search_button_rect, 2, border_radius=8)
            
            # Draw search button text
            search_text = font.render("Search", True, TEXT_PRIMARY)
            text_x = search_x + (button_width - search_text.get_width()) // 2
            text_y = button_y + (button_height - search_text.get_height()) // 2
            screen.blit(search_text, (text_x, text_y))
        
        # Add a subtle scroll hint for touch users
        if mode in ["games", "systems"] and (touchscreen_available or mouse_available):
            hint_text = "↕ Drag to scroll" if touchscreen_available else "↕ Wheel to scroll"
            hint_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            hint_surface = hint_font.render(hint_text, True, TEXT_DISABLED)
            hint_x = screen_width - hint_surface.get_width() - button_margin
            hint_y = button_margin
            screen.blit(hint_surface, (hint_x, hint_y))

    def handle_touch_button_click(pos):
        """Handle clicks on touch buttons"""
        global mode, highlighted, show_search_input, search_cursor_position, selected_system
        
        x, y = pos
        
        # Check back button
        if back_button_rect and back_button_rect.collidepoint(x, y):
            if mode == "games":
                mode = "systems"
                highlighted = selected_system if selected_system < len(get_visible_systems()) else 0
            elif mode == "settings":
                mode = "systems"
                highlighted = len(get_visible_systems()) + 1  # Settings option
            elif mode == "utils":
                mode = "systems"  
                highlighted = len(get_visible_systems())  # Utils option
            elif mode == "credits":
                mode = "systems"
                highlighted = len(get_visible_systems()) + 2  # Credits option
            elif mode == "add_systems":
                mode = "utils"
                highlighted = 1
            elif mode == "systems_settings":
                mode = "utils"
                highlighted = 0
            # Add more back navigation as needed
            return True
            
        # Check download button
        if download_button_rect and download_button_rect.collidepoint(x, y):
            if mode == "games" and selected_games:
                # Start download for selected games
                download_files(selected_system, selected_games)
                return True
                
        # Check search button  
        if search_button_rect and search_button_rect.collidepoint(x, y):
            if mode == "games":
                show_search_input = True
                search_cursor_position = len("abcdefghijklmnopqrstuvwxyz0123456789") + 3  # Start at DONE
                return True
                
        return False

    def convert_nsz_to_nsp(nsz_file_path):
        """Convert NSZ file to NSP in the same directory"""
        try:
            # Get the directory and filename info
            nsz_dir = os.path.dirname(nsz_file_path)
            nsz_filename = os.path.basename(nsz_file_path)
            nsp_filename = nsz_filename.replace('.nsz', '.nsp')
            
            def progress_callback(message, progress):
                draw_progress_bar(message, progress)
                pygame.display.flip()
            
            progress_callback(f"Converting {nsz_filename} to NSP...", 0)
            
            # Use the unified NSZ decompression method
            success = decompress_nsz_file(nsz_file_path, nsz_dir, progress_callback=progress_callback)
            
            if success:
                pygame.time.wait(1000)
                
                expected_nsp_path = os.path.join(nsz_dir, nsp_filename)
                if os.path.exists(expected_nsp_path):
                    draw_progress_bar(f"NSP file created: {nsp_filename}", 100)
                    print(f"NSZ conversion complete: {expected_nsp_path}")
                else:
                    nsp_files = [f for f in os.listdir(nsz_dir) if f.endswith('.nsp')]
                    if nsp_files:
                        draw_progress_bar(f"NSP file(s) created: {', '.join(nsp_files)}", 100)
                        print(f"NSZ conversion complete. Created NSP files: {', '.join(nsp_files)}")
                    else:
                        draw_progress_bar(f"Conversion completed but NSP file not found", 50)
                        print("NSZ conversion reported success but NSP file not found")
                
                pygame.time.wait(2000)
            else:
                draw_progress_bar(f"NSZ conversion failed - check logs", 0)
                pygame.time.wait(3000)
                
        except Exception as e:
            draw_progress_bar(f"NSZ conversion error: {str(e)}", 0)
            log_error(f"NSZ conversion error for {nsz_file_path}", type(e).__name__, traceback.format_exc())
            pygame.time.wait(3000)

    def update_json_file_path():
        """Update the global JSON_FILE variable based on archive_json_path setting"""
        global JSON_FILE
        archive_path = settings.get("archive_json_path", "")
        if archive_path and os.path.exists(archive_path):
            JSON_FILE = archive_path

    def load_controller_mapping():
        """Load controller mapping from file or create new mapping"""
        global controller_mapping
        
        mapping_file = os.path.join(os.path.dirname(CONFIG_FILE), "controller_mapping.json")
        
        try:
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r') as f:
                    controller_mapping = json.load(f)
                    print("Controller mapping loaded from file")
                    return True
            else:
                print("No controller mapping found, will need to create new mapping")
                controller_mapping = {}
                return False
        except Exception as e:
            log_error("Failed to load controller mapping", type(e).__name__, traceback.format_exc())
            controller_mapping = {}
            return False

    def save_controller_mapping():
        """Save controller mapping to file"""
        mapping_file = os.path.join(os.path.dirname(CONFIG_FILE), "controller_mapping.json")
        
        try:
            os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
            with open(mapping_file, 'w') as f:
                json.dump(controller_mapping, f, indent=2)
            print("Controller mapping saved")
        except Exception as e:
            log_error("Failed to save controller mapping", type(e).__name__, traceback.format_exc())

    def needs_controller_mapping():
        """Check if we need to collect controller mapping"""
        # If touchscreen mode is enabled, no controller mapping is needed
        if controller_mapping and controller_mapping.get("touchscreen_mode"):
            return False
        
        essential_buttons = ["select", "back", "start", "detail", "search", "up", "down", "left", "right"]
        return not controller_mapping or not all(button in controller_mapping for button in essential_buttons)

    def get_visible_systems():
        """Get list of systems that are not hidden and not list_systems"""
        system_settings = settings.get("system_settings", {})
        visible_systems = [d for d in data if not d.get('list_systems', False) and not system_settings.get(d['name'], {}).get('hidden', False)]
        # Remove the last system from the main menu
        if len(visible_systems) > 0:
            visible_systems = visible_systems[:-1]
        return visible_systems

    def get_system_index_by_name(system_name):
        """Get the original data array index for a system by name"""
        try:
            return next(i for i, d in enumerate(data) if d['name'] == system_name)
        except StopIteration:
            return -1

    def collect_controller_mapping():
        """Collect controller button mapping from user input"""
        global controller_mapping, show_controller_mapping, touchscreen_available
        
        # If already in touchscreen mode and user wants to remap, offer choice
        if controller_mapping and controller_mapping.get("touchscreen_mode"):
            # Show choice screen: Keep touchscreen mode or remap controller
            while True:
                draw_background()
                
                # Title
                title_text = "Controller Setup"
                title_surf = font.render(title_text, True, TEXT_PRIMARY)
                screen.blit(title_surf, (20, 20))
                
                # Current status
                status_text = "Currently using Touchscreen Mode"
                status_surf = font.render(status_text, True, TEXT_PRIMARY)
                screen.blit(status_surf, (20, 80))
                
                # Options
                if touchscreen_available:
                    option1_text = "Keep Touchscreen Mode"
                    option1_surf = font.render(option1_text, True, TEXT_PRIMARY)
                    screen.blit(option1_surf, (20, 140))
                
                option2_text = "Remap Physical Controller"
                option2_surf = font.render(option2_text, True, TEXT_PRIMARY)
                screen.blit(option2_surf, (20, 180))
                
                cancel_text = "ESC - Cancel"
                cancel_surf = font.render(cancel_text, True, GRAY)
                screen.blit(cancel_surf, (20, 240))
                
                # Draw touchscreen buttons if available
                keep_touchscreen_button_rect = None
                remap_controller_button_rect = None
                
                if touchscreen_available:
                    screen_width, screen_height = screen.get_size()
                    # Keep Touchscreen button
                    button_width = 250
                    button_height = 40
                    button_x = (screen_width - button_width) // 2
                    button_y = screen_height - 120
                    keep_touchscreen_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                    
                    pygame.draw.rect(screen, SUCCESS, keep_touchscreen_button_rect, border_radius=8)
                    pygame.draw.rect(screen, TEXT_PRIMARY, keep_touchscreen_button_rect, 2, border_radius=8)
                    
                    button_text = font.render("Keep Touchscreen", True, TEXT_PRIMARY)
                    text_x = button_x + (button_width - button_text.get_width()) // 2
                    text_y = button_y + (button_height - button_text.get_height()) // 2
                    screen.blit(button_text, (text_x, text_y))
                    
                    # Remap Controller button
                    button_y = screen_height - 70
                    remap_controller_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                    
                    pygame.draw.rect(screen, PRIMARY, remap_controller_button_rect, border_radius=8)
                    pygame.draw.rect(screen, TEXT_PRIMARY, remap_controller_button_rect, 2, border_radius=8)
                    
                    button_text = font.render("Remap Controller", True, TEXT_PRIMARY)
                    text_x = button_x + (button_width - button_text.get_width()) // 2
                    text_y = button_y + (button_height - button_text.get_height()) // 2
                    screen.blit(button_text, (text_x, text_y))
                
                pygame.display.flip()
                
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            return True  # Keep current setting
                        elif event.key == pygame.K_1 and touchscreen_available:
                            return True  # Keep touchscreen mode
                        elif event.key == pygame.K_2:
                            # Clear mapping and proceed to remap
                            controller_mapping = {}
                            break
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if touchscreen_available and keep_touchscreen_button_rect and keep_touchscreen_button_rect.collidepoint(event.pos):
                            return True  # Keep touchscreen mode
                        elif remap_controller_button_rect and remap_controller_button_rect.collidepoint(event.pos):
                            # Clear mapping and proceed to remap
                            controller_mapping = {}
                            break
                
                pygame.time.wait(16)
                
                # If we broke out of the choice loop, continue to controller mapping
                if not controller_mapping:
                    break
        
        essential_buttons = [
            ("up", "D-pad UP"),
            ("down", "D-pad DOWN"), 
            ("left", "D-pad LEFT"),
            ("right", "D-pad RIGHT"),
            ("select", "SELECT/CONFIRM button (usually A)"),
            ("back", "BACK/CANCEL button (usually B)"),
            ("start", "START/MENU button"),
            ("detail", "DETAIL/SECONDARY button (usually Y)"),
            ("search", "SEARCH button (for game search)"),
            ("left_shoulder", "Left Shoulder button (L/LB)"),
            ("right_shoulder", "Right Shoulder button (R/RB)")
        ]
        
        # Initialize mapping if empty
        if not controller_mapping:
            controller_mapping = {}
        current_button_index = 0
        collecting_input = True
        last_input_time = 0
        touchscreen_button_rect = None
        
        while collecting_input and current_button_index < len(essential_buttons):
            current_time = pygame.time.get_ticks()
            
            # Clear screen
            draw_background()
            
            # Title
            title_text = "Controller Setup"
            title_surf = font.render(title_text, True, TEXT_PRIMARY)
            screen.blit(title_surf, (20, 20))
            
            # Current button instruction
            button_key, button_description = essential_buttons[current_button_index]
            instruction_text = f"Press the {button_description}"
            instruction_surf = font.render(instruction_text, True, TEXT_PRIMARY)
            screen.blit(instruction_surf, (20, 80))
            
            # Progress
            progress_text = f"Button {current_button_index + 1} of {len(essential_buttons)}"
            progress_surf = font.render(progress_text, True, GRAY)
            screen.blit(progress_surf, (20, 120))
            
            # Show already mapped buttons
            y_offset = 160
            for i, (mapped_key, _) in enumerate(essential_buttons[:current_button_index]):
                if mapped_key in controller_mapping:
                    mapped_text = f"{mapped_key}: Button {controller_mapping[mapped_key]}"
                    mapped_surf = font.render(mapped_text, True, GREEN)
                    screen.blit(mapped_surf, (20, y_offset + i * 25))
            
            # Draw "Use Touchscreen" button if touchscreen is available
            if touchscreen_available:
                screen_width, screen_height = screen.get_size()
                button_width = 200
                button_height = 50
                button_x = (screen_width - button_width) // 2
                button_y = screen_height - 80
                touchscreen_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                
                # Draw button background
                pygame.draw.rect(screen, SUCCESS, touchscreen_button_rect, border_radius=8)
                pygame.draw.rect(screen, TEXT_PRIMARY, touchscreen_button_rect, 2, border_radius=8)
                
                # Draw button text
                button_text = font.render("Use Touchscreen", True, TEXT_PRIMARY)
                text_x = button_x + (button_width - button_text.get_width()) // 2
                text_y = button_y + (button_height - button_text.get_height()) // 2
                screen.blit(button_text, (text_x, text_y))
            
            pygame.display.flip()
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Handle touchscreen button
                    if touchscreen_available and touchscreen_button_rect and touchscreen_button_rect.collidepoint(event.pos):
                        # Skip controller mapping and use touchscreen mode
                        controller_mapping = {"touchscreen_mode": True}
                        save_controller_mapping()
                        return True
                elif event.type == pygame.JOYBUTTONDOWN:
                    # Debounce input (prevent double registration)
                    if current_time - last_input_time > 300:
                        controller_mapping[button_key] = event.button
                        print(f"Mapped {button_key} to button {event.button}")
                        current_button_index += 1
                        last_input_time = current_time
                elif event.type == pygame.JOYHATMOTION:
                    # Handle D-pad input
                    if current_time - last_input_time > 300:
                        hat_x, hat_y = event.value
                        if button_key == "up" and hat_y == 1:
                            controller_mapping[button_key] = ("hat", 0, 1)
                            current_button_index += 1
                            last_input_time = current_time
                        elif button_key == "down" and hat_y == -1:
                            controller_mapping[button_key] = ("hat", 0, -1)
                            current_button_index += 1
                            last_input_time = current_time
                        elif button_key == "left" and hat_x == -1:
                            controller_mapping[button_key] = ("hat", -1, 0)
                            current_button_index += 1
                            last_input_time = current_time
                        elif button_key == "right" and hat_x == 1:
                            controller_mapping[button_key] = ("hat", 1, 0)
                            current_button_index += 1
                            last_input_time = current_time
                elif event.type == pygame.KEYDOWN:
                    # Allow keyboard input for testing
                    if event.key == pygame.K_ESCAPE:
                        return False
            
            # Small delay to prevent CPU spinning
            pygame.time.wait(16)
        
        # Save the completed mapping
        save_controller_mapping()
        return True

    def get_game_initials(game_name):
        """Extract first 3 initials from game name"""
        if not game_name:
            return "GAM"
        
        # Remove file extension and common brackets/parentheses content
        clean_name = os.path.splitext(game_name)[0]
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', clean_name).strip()
        
        # Split into words and get initials
        words = clean_name.split()
        initials = ""
        
        for word in words:
            if word and word[0].isalpha():
                initials += word[0].upper()
                if len(initials) >= 3:
                    break
        
        # Pad with game name characters if not enough initials
        if len(initials) < 3:
            for char in clean_name:
                if char.isalpha() and char.upper() not in initials:
                    initials += char.upper()
                    if len(initials) >= 3:
                        break
        
        # Fallback if still not enough
        while len(initials) < 3:
            initials += "X"
        
        return initials[:3]

    def load_image_async(url, cache_key, game_name=None):
        """Load image in background thread"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Load image from bytes
            image_data = BytesIO(response.content)
            image = pygame.image.load(image_data)
            
            # Scale to thumbnail size
            scaled_image = pygame.transform.scale(image, THUMBNAIL_SIZE)
            
            # Add to queue for main thread to process
            image_queue.put((cache_key, scaled_image))
        except Exception as e:
            log_error(f"Failed to load image from {url}", type(e).__name__, traceback.format_exc())
            
            # Try placeholder image if game name is available
            if game_name:
                try:
                    initials = get_game_initials(game_name)
                    placeholder_url = f"https://placehold.co/50x50?text={initials}"
                    response = requests.get(placeholder_url, timeout=5)
                    response.raise_for_status()
                    
                    # Load placeholder image from bytes
                    image_data = BytesIO(response.content)
                    image = pygame.image.load(image_data)
                    
                    # Scale to thumbnail size
                    scaled_image = pygame.transform.scale(image, THUMBNAIL_SIZE)
                    
                    # Add to queue for main thread to process
                    image_queue.put((cache_key, scaled_image))
                    return
                except Exception:
                    pass  # Fallback to None if placeholder also fails
            
            # Put None to indicate failed load
            image_queue.put((cache_key, None))

    def load_hires_image_async(url, cache_key, game_name=None):
        """Load high-resolution image in background thread"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Load image from bytes
            image_data = BytesIO(response.content)
            image = pygame.image.load(image_data)
            
            # Scale to high-resolution size
            scaled_image = pygame.transform.scale(image, HIRES_IMAGE_SIZE)
            
            # Add to queue for main thread to process
            hires_image_queue.put((cache_key, scaled_image))
        except Exception as e:
            log_error(f"Failed to load high-res image from {url}", type(e).__name__, traceback.format_exc())
            
            # Try placeholder image if game name is available
            if game_name:
                try:
                    initials = get_game_initials(game_name)
                    placeholder_url = f"https://placehold.co/400x400?text={initials}"
                    response = requests.get(placeholder_url, timeout=5)
                    response.raise_for_status()
                    
                    # Load placeholder image from bytes
                    image_data = BytesIO(response.content)
                    image = pygame.image.load(image_data)
                    
                    # Scale to high-resolution size
                    scaled_image = pygame.transform.scale(image, HIRES_IMAGE_SIZE)
                    
                    # Add to queue for main thread to process
                    hires_image_queue.put((cache_key, scaled_image))
                    return
                except Exception:
                    pass  # Fallback to None if placeholder also fails
            
            # Put None to indicate failed load
            hires_image_queue.put((cache_key, None))

    def get_thumbnail(game_item, boxart_url):
        """Get thumbnail for game, loading async if not cached"""
        # Check if box-art is enabled
        if not settings["enable_boxart"]:
            return None
            
        # Handle game item formats
        if isinstance(game_item, str):
            game_name = game_item
        elif isinstance(game_item, dict):
            if 'name' in game_item:
                game_name = game_item.get('name', '')
            elif 'filename' in game_item:
                game_name = game_item.get('filename', '')
            else:
                game_name = str(game_item)
        else:
            game_name = str(game_item)
        
        # Handle different image URL formats
        if isinstance(game_item, dict) and ('banner_url' in game_item) and game_item.get('banner_url') is not None:
            # Direct URL format (e.g., Nintendo Switch API)
            image_url = game_item.get('banner_url') or game_item.get('icon_url')
            cache_key = f"direct_{image_url}_{game_name}"
        elif boxart_url:
            # Regular format - construct URL from boxart base + game name
            base_name = os.path.splitext(game_name)[0]
            image_url = urljoin(boxart_url, f"{base_name}.png")
            cache_key = f"{boxart_url}_{game_name}"
        else:
            return None
        
        # Return cached image if available and cache is enabled
        if settings["cache_enabled"] and cache_key in image_cache:
            return image_cache[cache_key]
        
        # If cache is disabled but we have the image, return it
        if not settings["cache_enabled"] and cache_key in image_cache:
            return image_cache[cache_key]
        
        # Start loading if not already in cache
        if cache_key not in image_cache:
            image_cache[cache_key] = "loading"  # Mark as loading
            
            if isinstance(game_item, dict) and ('banner_url' in game_item or 'icon_url' in game_item):
                # Direct URL format - use the URL as-is
                thread = Thread(target=load_image_async, args=(image_url, cache_key, game_name))
                thread.daemon = True
                thread.start()
            else:
                # Regular format - try multiple image formats
                base_name = os.path.splitext(game_name)[0]
                image_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
                thread = Thread(target=load_image_with_fallback, args=(boxart_url, base_name, image_formats, cache_key, game_name))
                thread.daemon = True
                thread.start()
        
        return None  # Not ready yet

    def load_image_with_fallback(base_url, base_name, formats, cache_key, game_name=None):
        """Try loading image with different format extensions"""
        for fmt in formats:
            try:
                image_url = urljoin(base_url, f"{base_name}{fmt}")
                response = requests.get(image_url, timeout=5)
                response.raise_for_status()
                
                # Load image from bytes
                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data)
                
                # Scale to thumbnail size
                scaled_image = pygame.transform.scale(image, THUMBNAIL_SIZE)
                
                # Add to queue for main thread to process
                image_queue.put((cache_key, scaled_image))
                return  # Success, exit
                
            except Exception:
                continue  # Try next format
        
        # All formats failed - try placeholder image
        if game_name:
            try:
                initials = get_game_initials(game_name)
                placeholder_url = f"https://placehold.co/50x50?text={initials}"
                response = requests.get(placeholder_url, timeout=5)
                response.raise_for_status()
                
                # Load placeholder image from bytes
                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data)
                
                # Scale to thumbnail size
                scaled_image = pygame.transform.scale(image, THUMBNAIL_SIZE)
                
                # Add to queue for main thread to process
                image_queue.put((cache_key, scaled_image))
                return
            except Exception:
                pass  # Fallback to None if placeholder also fails
        
        # All attempts failed
        image_queue.put((cache_key, None))

    def update_image_cache():
        """Process loaded images from background threads"""
        while not image_queue.empty():
            try:
                cache_key, image = image_queue.get_nowait()
                image_cache[cache_key] = image
            except:
                break

    def reset_image_cache():
        """Clear all cached images"""
        global image_cache, hires_image_cache
        image_cache.clear()
        hires_image_cache.clear()
        
        # Clear the queues as well
        while not image_queue.empty():
            try:
                image_queue.get_nowait()
            except:
                break
        while not hires_image_queue.empty():
            try:
                hires_image_queue.get_nowait()
            except:
                break

    def load_hires_image_with_fallback(base_url, base_name, formats, cache_key, game_name=None):
        """Try loading high-resolution image with different format extensions"""
        for fmt in formats:
            try:
                url = f"{base_url}/{base_name}{fmt}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data)
                
                # Keep original image for high quality, only scale if it's extremely large
                original_size = image.get_size()
                max_dimension = max(original_size[0], original_size[1])
                
                if max_dimension > 800:  # Only scale down if extremely large
                    scale_factor = 800 / max_dimension
                    new_width = int(original_size[0] * scale_factor)
                    new_height = int(original_size[1] * scale_factor)
                    scaled_image = pygame.transform.smoothscale(image, (new_width, new_height))
                else:
                    scaled_image = image  # Keep original size for better quality
                
                # Add to queue for main thread to process
                hires_image_queue.put((cache_key, scaled_image))
                return
                
            except:
                continue
        
        # Try to load from image_cache if available as fallback
        if cache_key in image_cache and image_cache[cache_key] != "loading":
            fallback_image = image_cache[cache_key]
            if fallback_image:
                # Scale up the thumbnail for better quality than nothing
                upscaled = pygame.transform.smoothscale(fallback_image, HIRES_IMAGE_SIZE)
                hires_image_queue.put((cache_key, upscaled))
                return
        
        hires_image_queue.put((cache_key, None))

    def update_hires_image_cache():
        """Process loaded high-resolution images from background threads"""
        while not hires_image_queue.empty():
            try:
                cache_key, image = hires_image_queue.get_nowait()
                hires_image_cache[cache_key] = image
            except:
                break

    def get_hires_thumbnail(game_item, boxart_url):
        """Get high-resolution thumbnail for detail modal, loading async if not cached"""
        if not settings["enable_boxart"]:
            return None
        
        # Handle game item formats
        if isinstance(game_item, str):
            game_name = game_item
        elif isinstance(game_item, dict):
            if 'name' in game_item:
                game_name = game_item.get('name', '')
            elif 'filename' in game_item:
                game_name = game_item.get('filename', '')
            else:
                game_name = str(game_item)
        else:
            game_name = str(game_item)
        
        # Handle different image URL formats
        if isinstance(game_item, dict) and ('banner_url' in game_item) and game_item.get('banner_url') is not None:
            # Direct URL format (e.g., Nintendo Switch API)
            image_url = game_item.get('banner_url') or game_item.get('icon_url')
            cache_key = f"hires_direct_{image_url}_{game_name}"
        elif boxart_url:
            cache_key = f"hires_{game_name}_{boxart_url}"
        else:
            return None
                
        # Return cached high-res image if available
        if cache_key in hires_image_cache:
            return hires_image_cache[cache_key]
        
        # Start loading high-res image if not already in cache
        if cache_key not in hires_image_cache:
            hires_image_cache[cache_key] = "loading"
            
            if isinstance(game_item, dict) and ('banner_url' in game_item) and game_item.get('banner_url') is not None:
                # Direct URL format - use the URL as-is
                thread = Thread(target=load_hires_image_async, args=(image_url, cache_key, game_name))
                thread.daemon = True
                thread.start()
            elif boxart_url:
                # Standard format - try different extensions
                base_name = os.path.splitext(game_name)[0]
                image_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
                thread = Thread(target=load_hires_image_with_fallback, args=(boxart_url, base_name, image_formats, cache_key, game_name))
                thread.daemon = True
                thread.start()
        
        return "loading"
        """Download and update download.json from remote URL"""
        try:
            # Validate URL format
            if not url or not url.strip():
                draw_loading_message("Error: No URL provided")
                pygame.time.wait(2000)
                return False
                
            if not (url.startswith('http://') or url.startswith('https://')):
                draw_loading_message("Error: URL must start with http:// or https://")
                pygame.time.wait(2000)
                return False
            
            draw_loading_message("Downloading archive configuration...")
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                # Try to parse as JSON to validate
                try:
                    json_data = response.json()
                    if not isinstance(json_data, list):
                        draw_loading_message("Error: Invalid JSON format (must be array)")
                        pygame.time.wait(2000)
                        return False
                except json.JSONDecodeError:
                    draw_loading_message("Error: Invalid JSON format")
                    pygame.time.wait(2000)
                    return False
                
                # Create backup of existing file
                backup_path = f"{JSON_FILE}.backup"
                if os.path.exists(JSON_FILE):
                    try:
                        with open(JSON_FILE, 'r') as original:
                            with open(backup_path, 'w') as backup:
                                backup.write(original.read())
                    except Exception as backup_error:
                        log_error(f"Failed to create backup for download.json", type(backup_error).__name__, traceback.format_exc())
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(JSON_FILE), exist_ok=True)
                
                # Write new content
                with open(JSON_FILE, 'w') as f:
                    json.dump(json_data, f, indent=2)
                
                draw_loading_message("Archive configuration updated successfully!")
                pygame.time.wait(2000)
                return True
                
            except requests.RequestException as req_error:
                error_msg = f"Failed to download from {url}"
                if hasattr(req_error, 'response') and req_error.response is not None:
                    error_msg += f" (HTTP {req_error.response.status_code})"
                log_error(error_msg, type(req_error).__name__, traceback.format_exc())
                draw_loading_message(f"Error: Network error - check URL")
                pygame.time.wait(2000)
                return False
                
        except Exception as e:
            log_error("Error downloading archive JSON", type(e).__name__, traceback.format_exc())
            draw_loading_message("Download failed. Check error log for details.")
            pygame.time.wait(2000)
            return False

    def download_direct_file(url):
        """Download a file directly to the work directory"""
        try:
            # Validate URL format
            if not url or not url.strip():
                draw_loading_message("Error: No URL provided")
                pygame.time.wait(2000)
                return False
                
            if not (url.startswith('http://') or url.startswith('https://')):
                draw_loading_message("Error: URL must start with http:// or https://")
                pygame.time.wait(2000)
                return False
            
            draw_loading_message("Starting download...")
            
            # Get work directory from settings and create py_downloads subdirectory
            work_dir = settings.get("work_dir", os.path.join(SCRIPT_DIR, "py_downloads"))
            py_downloads_dir = os.path.join(work_dir, "py_downloads")
            if not os.path.exists(py_downloads_dir):
                os.makedirs(py_downloads_dir, exist_ok=True)
            
            # Extract filename from URL
            parsed_url = url.rstrip('/')
            filename = parsed_url.split('/')[-1]
            if not filename or '.' not in filename:
                # Use a default filename if we can't extract one
                filename = "downloaded_file"
            
            file_path = os.path.join(py_downloads_dir, filename)
            
            # Start download
            try:
                response = requests.get(url, stream=True, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    start_time = time.time()
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Calculate speed and show progress
                            elapsed_time = time.time() - start_time
                            if elapsed_time > 0:
                                speed = downloaded / elapsed_time
                                
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                draw_progress_bar(f"Downloading {filename}", percent, downloaded, total_size, speed)
                            else:
                                draw_progress_bar(f"Downloading {filename}", 0, downloaded, 0, speed)
                
                draw_loading_message(f"Downloaded to work directory: {filename}")
                pygame.time.wait(2000)
                return True
                
            except requests.exceptions.RequestException as req_error:
                error_msg = "Network error downloading file"
                if hasattr(req_error, 'response') and req_error.response:
                    error_msg += f" (HTTP {req_error.response.status_code})"
                log_error(error_msg, type(req_error).__name__, traceback.format_exc())
                draw_loading_message(f"Error: Network error - check URL")
                pygame.time.wait(2000)
                return False
                
        except Exception as e:
            log_error("Error downloading file", type(e).__name__, traceback.format_exc())
            draw_loading_message("Download failed. Check error log for details.")
            pygame.time.wait(2000)
            return False

    def draw_progress_bar(text, percent, downloaded=0, total_size=0, speed=0):
        draw_background()
        
        # Draw title with modern styling
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.3))
        title_surf = title_font.render("Download Progress", True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, 20))
        
        # Draw subtle underline for title
        title_width = title_surf.get_width()
        pygame.draw.line(screen, PRIMARY, (20, 20 + title_surf.get_height() + 5), 
                        (20 + title_width, 20 + title_surf.get_height() + 5), 2)
        
        # Draw current operation with enhanced styling
        text_surf = font.render(text, True, TEXT_SECONDARY)
        screen.blit(text_surf, (20, 60))
        
        # Modern progress bar with rounded corners and shadow
        bar_height = 12
        bar_y = 90
        screen_width, screen_height = screen.get_size()
        bar_width = min(screen_width - 80, 600)
        bar_x = 20
        
        # Draw shadow
        shadow_rect = pygame.Rect(bar_x + 2, bar_y + 2, bar_width, bar_height)
        pygame.draw.rect(screen, (0, 0, 0, 50), shadow_rect, border_radius=6)
        
        # Draw background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(screen, SURFACE, bg_rect, border_radius=6)
        pygame.draw.rect(screen, TEXT_DISABLED, bg_rect, 1, border_radius=6)
        
        # Draw progress with gradient-like effect
        progress_width = int(bar_width * (percent / 100))
        if progress_width > 0:
            progress_rect = pygame.Rect(bar_x, bar_y, progress_width, bar_height)
            # Use different colors based on progress
            if percent < 30:
                progress_color = WARNING
            elif percent < 70:
                progress_color = PRIMARY
            else:
                progress_color = SUCCESS
            
            pygame.draw.rect(screen, progress_color, progress_rect, border_radius=6)
            
            # Add a highlight for better depth
            if progress_width > 4:
                highlight_rect = pygame.Rect(bar_x, bar_y, progress_width, bar_height // 3)
                highlight_color = tuple(min(255, c + 30) for c in progress_color)
                pygame.draw.rect(screen, highlight_color, highlight_rect, border_radius=6)
        
        # Draw percentage text with better positioning
        percent_text = f"{percent}%"
        percent_surf = font.render(percent_text, True, TEXT_PRIMARY)
        percent_x = bar_x + bar_width + 10  # Position to the right of the bar
        screen.blit(percent_surf, (percent_x, bar_y - 2))
        
        # Draw size and speed info
        if total_size > 0:
            size_text = f"{format_size(downloaded)} / {format_size(total_size)}"
            if speed > 0:
                size_text += f" - {format_size(speed)}/s"
            size_surf = font.render(size_text, True, TEXT_PRIMARY)
            size_x = bar_x + 5
            screen.blit(size_surf, (size_x, bar_y + bar_height + 10))
        
        # Draw instructions
        back_button_name = get_button_name("back")
        instructions = [
            f"Press {back_button_name} to cancel download",
            "Please wait while files are being downloaded..."
        ]
        
        y = bar_y + bar_height + 40
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 5
        
        pygame.display.flip()

    def draw_settings_menu():
        global settings_scroll_offset, menu_item_rects, menu_scroll_offset
        menu_item_rects.clear()
        menu_scroll_offset = 0  # Initialize scroll offset
        
        draw_background()
        y = 10
        
        # Draw title
        title_surf = font.render("Settings", True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, y))
        y += FONT_SIZE + 10
        
        # Draw instructions
        select_button_name = get_button_name("select")
        back_button_name = get_button_name("back")
        instructions = [
            "Use D-pad to navigate",
            f"Press {select_button_name} to toggle settings",
            f"Press {back_button_name} to go back"
        ]
        
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 5
        
        y += 20
        start_y = y
        
        # Calculate visible items based on screen height
        screen_width, screen_height = screen.get_size()
        row_height = FONT_SIZE + 10
        cache_info_height = FONT_SIZE + 25  # Space for cache info at bottom
        available_height = screen_height - start_y - cache_info_height - 50  # Leave space for debug controller
        items_per_screen = max(1, available_height // row_height)
        
        # Calculate scroll boundaries
        total_items = len(settings_list)
        max_scroll = max(0, total_items - items_per_screen)
        
        # Adjust scroll offset to keep highlighted item visible
        if highlighted < settings_scroll_offset:
            settings_scroll_offset = highlighted
        elif highlighted >= settings_scroll_offset + items_per_screen:
            settings_scroll_offset = highlighted - items_per_screen + 1
        
        # Clamp scroll offset
        settings_scroll_offset = max(0, min(settings_scroll_offset, max_scroll))
        
        # Calculate visible items
        start_idx = settings_scroll_offset
        end_idx = min(start_idx + items_per_screen, total_items)
        visible_settings = settings_list[start_idx:end_idx]
        
        # Store scroll offset for click handling
        menu_scroll_offset = start_idx
        
        # Draw settings items
        for i, setting_name in enumerate(visible_settings):
            actual_idx = start_idx + i
            color = PRIMARY if actual_idx == highlighted else TEXT_PRIMARY
            
            # Handle divider differently
            if setting_name == "--- VIEW OPTIONS ---":
                # Draw divider
                setting_surf = font.render(setting_name, True, TEXT_DISABLED)
                screen.blit(setting_surf, (20, y))
                
                # Draw a line under the divider
                line_y = y + FONT_SIZE + 2
                pygame.draw.line(screen, TEXT_DISABLED, (20, line_y), (screen_width - 40, line_y), 1)
                
                # Store a non-clickable rectangle (negative index to indicate non-selectable)
                item_rect = pygame.Rect(0, y, screen.get_width(), row_height)
                menu_item_rects.append(item_rect)
                
                y += row_height
                continue
            
            # Get current setting value based on new indices
            setting_value = ""
            if actual_idx == 0:  # Select Archive Json
                archive_path = settings.get("archive_json_path", "")
                if archive_path and os.path.exists(archive_path):
                    setting_value = archive_path[-30:] + "..." if len(archive_path) > 30 else archive_path
                else:
                    setting_value = "Not configured"
            elif actual_idx == 1:  # Work Directory
                work_dir = settings.get("work_dir", "")
                setting_value = work_dir[-30:] + "..." if len(work_dir) > 30 else work_dir
            elif actual_idx == 2:  # ROMs Directory
                roms_dir = settings.get("roms_dir", "")
                setting_value = roms_dir[-30:] + "..." if len(roms_dir) > 30 else roms_dir
            elif actual_idx == 3:  # NSZ Keys
                keys_path = settings.get("nsz_keys_path", "")
                if keys_path and os.path.exists(keys_path):
                    setting_value = keys_path[-30:] + "..." if len(keys_path) > 30 else keys_path
                else:
                    setting_value = "Not configured"
            elif actual_idx == 4:  # Remap Controller
                if controller_mapping:
                    if controller_mapping.get("touchscreen_mode"):
                        setting_value = "Touchscreen Mode"
                    else:
                        setting_value = f"{len(controller_mapping)} buttons mapped"
                else:
                    setting_value = "Not configured"
            elif actual_idx == 5:  # Add Systems
                select_button_name = get_button_name("select")
                setting_value = f"Press {select_button_name} to add"
            elif actual_idx == 6:  # Systems Settings
                select_button_name = get_button_name("select")
                setting_value = f"Press {select_button_name} to configure"
            elif actual_idx == 8:  # Enable Box-art Display (after divider)
                setting_value = "ON" if settings["enable_boxart"] else "OFF"
            elif actual_idx == 9:  # View Type
                setting_value = settings["view_type"].upper()
            elif actual_idx == 10:  # USA Games Only
                setting_value = "ON" if settings["usa_only"] else "OFF"
            
            setting_text = f"{setting_name}: {setting_value}"
            setting_surf = font.render(setting_text, True, color)
            screen.blit(setting_surf, (20, y))
            
            # Store clickable rectangle for touch/mouse support
            item_rect = pygame.Rect(0, y, screen.get_width(), row_height)
            menu_item_rects.append(item_rect)
            
            y += row_height
        
    def draw_add_systems_menu():
        draw_background()
        y = 10
        
        # Draw title
        title_surf = font.render("Add Systems", True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, y))
        y += FONT_SIZE + 10
        
        # Draw instructions
        select_button_name = get_button_name("select")
        back_button_name = get_button_name("back")
        instructions = [
            "Use D-pad to navigate",
            f"Press {select_button_name} to add system",
            f"Press {back_button_name} to go back"
        ]
        
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 5
        
        y += 20
        
        # Show loading message if no systems loaded yet
        if not available_systems:
            loading_surf = font.render("Loading available systems...", True, TEXT_PRIMARY)
            screen.blit(loading_surf, (20, y))
        else:
            # Calculate visible items for scrolling
            screen_width, screen_height = screen.get_size()
            available_height = screen_height - y - 50  # Leave space for debug info
            items_per_screen = available_height // (FONT_SIZE + 10)
            
            # Calculate scroll offset to keep highlighted item visible
            start_idx = max(0, add_systems_highlighted - items_per_screen // 2)
            end_idx = min(len(available_systems), start_idx + items_per_screen)
            
            # Draw available systems list with scrolling
            for i in range(start_idx, end_idx):
                system = available_systems[i]
                color = PRIMARY if i == add_systems_highlighted else TEXT_PRIMARY
                system_text = f"{system['name']} - {system.get('size', 'Unknown size')}"
                system_surf = font.render(system_text, True, color)
                screen.blit(system_surf, (20, y))
                y += FONT_SIZE + 10
            
            # Show scroll indicator if needed
            if len(available_systems) > items_per_screen:
                if start_idx > 0:
                    # Show up indicator
                    up_arrow = font.render("UP", True, GRAY)
                    screen.blit(up_arrow, (screen_width - 40, 10))
                if end_idx < len(available_systems):
                    # Show down indicator
                    down_arrow = font.render("DOWN", True, GRAY)
                    screen.blit(down_arrow, (screen_width - 50, screen_height - 30))
        
    def draw_systems_settings_menu():
        """Draw the systems settings menu that lists all systems"""
        draw_background()
        y = 10
        
        # Draw title
        title_surf = font.render("Systems Settings", True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, y))
        y += FONT_SIZE + 10
        
        # Draw instructions
        select_button_name = get_button_name("select")
        back_button_name = get_button_name("back")
        instructions = [
            "Use D-pad to navigate",
            f"Press {select_button_name} to configure system",
            f"Press {back_button_name} to go back"
        ]
        
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 5
        
        y += 20
        
        # Filter out 'Other Systems' and 'list_systems' entries
        configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
        
        # Calculate visible items
        screen_width, screen_height = screen.get_size()
        row_height = FONT_SIZE + 10
        available_height = screen_height - y - 50  # Leave space for debug controller
        items_per_screen = max(1, available_height // row_height)
        
        start_idx = max(0, systems_settings_highlighted - items_per_screen // 2)
        end_idx = min(start_idx + items_per_screen, len(configurable_systems))
        visible_systems = configurable_systems[start_idx:end_idx]
        
        # Draw systems list
        for i, system in enumerate(visible_systems):
            actual_idx = start_idx + i
            color = PRIMARY if actual_idx == systems_settings_highlighted else TEXT_PRIMARY
            
            # Get system status
            system_settings = settings.get("system_settings", {})
            system_name = system['name']
            is_hidden = system_settings.get(system_name, {}).get('hidden', False)
            custom_folder = system_settings.get(system_name, {}).get('custom_folder', '')
            
            status_parts = []
            if is_hidden:
                status_parts.append("HIDDEN")
            if custom_folder:
                status_parts.append(f"Custom: {os.path.basename(custom_folder)}")
            
            status = f" ({', '.join(status_parts)})" if status_parts else ""
            system_text = f"{system_name}{status}"
            
            system_surf = font.render(system_text, True, color)
            screen.blit(system_surf, (20, y))
            y += row_height
        
        # Show scroll indicator if needed
        if len(configurable_systems) > items_per_screen:
            if start_idx > 0:
                up_arrow = font.render("UP", True, GRAY)
                screen.blit(up_arrow, (screen_width - 40, 10))
            if end_idx < len(configurable_systems):
                down_arrow = font.render("DOWN", True, GRAY)
                screen.blit(down_arrow, (screen_width - 50, screen_height - 30))
        
    def draw_utils_menu():
        """Draw the utils menu for downloading files"""
        utils_options = [
            "Download from URL",
            "NSZ to NSP Converter"
        ]
        
        # Enhanced title
        title = "Utilities"
        
        draw_menu(title, utils_options, set())

    def draw_credits_menu():
        """Draw the credits menu"""
        draw_background()
        screen_width, screen_height = screen.get_size()
        
        # Title
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.5))
        title_surf = title_font.render("Credits", True, TEXT_PRIMARY)
        title_x = (screen_width - title_surf.get_width()) // 2
        y = 20
        screen.blit(title_surf, (title_x, y))
        y += title_surf.get_height() + 30
        
        # Credits content with your specified text
        credits_content = [
            "",
            "Developer: hiitsgabe @ github.",
            "",
            "Made with love in Toronto.",
            "",
            "DISCLAIMER:",
            "This app is meant to help you organize games that",
            "you legally own and to manage legally acquired copies",
            "of your games. We do not condone piracy or illegal",
            "distribution of copyrighted content in any form.",
            "Users are responsible for ensuring they comply with",
            "all applicable copyright laws in their jurisdiction.",
            "",
            "Made w/: Pygame+Buildozer, NSZ Library and Python.",
            ""
        ]
        
        # Center the credits content
        for line in credits_content:
            if line:  # Non-empty lines
                # Regular text line
                line_surf = font.render(line, True, TEXT_PRIMARY)
                line_x = (screen_width - line_surf.get_width()) // 2
                screen.blit(line_surf, (line_x, y))
            y += FONT_SIZE + 8
        
        # Instructions at the bottom
        back_button_name = get_button_name("back")
        instruction = f"Press {back_button_name} to go back"
        inst_surf = font.render(instruction, True, TEXT_DISABLED)
        inst_x = (screen_width - inst_surf.get_width()) // 2
        inst_y = screen_height - 50
        screen.blit(inst_surf, (inst_x, inst_y))

    def draw_system_settings_menu():
        """Draw the individual system settings menu"""
        if not selected_system_for_settings:
            return
            
        draw_background()
        y = 10
        
        # Draw title
        title_surf = font.render(f"Settings for {selected_system_for_settings['name']}", True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, y))
        y += FONT_SIZE + 10
        
        # Draw instructions
        select_button_name = get_button_name("select")
        back_button_name = get_button_name("back")
        instructions = [
            "Use D-pad to navigate",
            f"Press {select_button_name} to toggle/configure",
            f"Press {back_button_name} to go back"
        ]
        
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 5
        
        y += 20
        
        # Get current system settings
        system_settings = settings.get("system_settings", {})
        system_name = selected_system_for_settings['name']
        current_settings = system_settings.get(system_name, {})
        
        # Settings options
        settings_options = [
            "Hide from main menu",
            "Custom ROM folder"
        ]
        
        # Draw settings options
        for i, option in enumerate(settings_options):
            color = PRIMARY if i == system_settings_highlighted else TEXT_PRIMARY
            
            # Get current value
            if i == 0:  # Hide from main menu
                value = "ON" if current_settings.get('hidden', False) else "OFF"
            elif i == 1:  # Custom ROM folder
                custom_folder = current_settings.get('custom_folder', '')
                if custom_folder:
                    value = custom_folder[-40:] + "..." if len(custom_folder) > 40 else custom_folder
                else:
                    value = f"Default ({selected_system_for_settings.get('roms_folder', 'N/A')})"
            
            option_text = f"{option}: {value}"
            option_surf = font.render(option_text, True, color)
            screen.blit(option_surf, (20, y))
            y += FONT_SIZE + 10        

    def draw_grid_view(title, items, selected_indices):
        # Clear menu item rectangles for touch/click detection
        global menu_item_rects, menu_scroll_offset
        menu_item_rects.clear()
        menu_scroll_offset = 0  # Initialize scroll offset (will be updated with grid scrolling)
        
        draw_background()
        y = 20
        
        # Draw title with modern styling and gradient effect
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.4))
        title_surf = title_font.render(title, True, TEXT_PRIMARY)
        screen.blit(title_surf, (20, y))
        
        # Draw gradient underline for title
        title_width = title_surf.get_width()
        underline_y = y + title_surf.get_height() + 8
        for i in range(title_width):
            alpha = int(255 * (1 - i / title_width))
            color = (PRIMARY[0], PRIMARY[1], PRIMARY[2], alpha)
            pygame.draw.line(screen, color, (20 + i, underline_y), (20 + i, underline_y + 3), 1)
        
        y += title_surf.get_height() + 25
        
        # Draw download instruction if games are selected with enhanced styling
        if selected_indices:
            start_button_name = get_button_name("start")
            instruction = f"Press {start_button_name} to start downloading"
            
            # Create a modern notification box for the instruction
            inst_surf = font.render(instruction, True, TEXT_PRIMARY)
            inst_width = inst_surf.get_width()
            inst_height = inst_surf.get_height()
            
            # Draw modern notification box with gradient
            box_rect = pygame.Rect(15, y - 8, inst_width + 20, inst_height + 16)
            pygame.draw.rect(screen, SURFACE, box_rect, border_radius=BORDER_RADIUS)
            pygame.draw.rect(screen, PRIMARY, box_rect, 2, border_radius=BORDER_RADIUS)
            
            # Add subtle glow effect
            glow_rect = pygame.Rect(13, y - 10, inst_width + 24, inst_height + 20)
            pygame.draw.rect(screen, GLOW_COLOR, glow_rect, border_radius=BORDER_RADIUS + 2)
            
            screen.blit(inst_surf, (25, y))
            y += inst_height + 20
        
        y += 15
        
        # Grid layout parameters with improved spacing
        cols = 4  # Number of columns
        screen_width, screen_height = screen.get_size()
        cell_width = (screen_width - 60) // cols  # More padding
        cell_height = max(THUMBNAIL_SIZE[1] + 60, 120)  # Increased height for better spacing
        start_x = 30  # More padding from edges
        start_y = y
        
        # Calculate visible items (ensure at least 4 rows for better visibility)
        available_height = screen_height - start_y - 50
        if available_height > 0:
            calculated_rows = available_height // cell_height
            rows_per_screen = max(4, calculated_rows)  # Minimum 4 rows
        else:
            # Extremely small screen, fallback to minimum
            rows_per_screen = 4
        items_per_screen = cols * rows_per_screen
        
        # Calculate grid position of highlighted item
        highlighted_row = highlighted // cols
        highlighted_col = highlighted % cols
        
        # Calculate scroll offset to keep highlighted item in the second row (index 1)
        target_row = 1  # Second row (0-indexed)
        start_row = max(0, highlighted_row - target_row)
        visible_items = items[start_row * cols:(start_row + rows_per_screen) * cols]
        
        # Store scroll offset for click handling (grid uses row-based offset)
        menu_scroll_offset = start_row * cols
        
        # Draw grid items
        for i, item in enumerate(visible_items):
            actual_idx = start_row * cols + i
            if actual_idx >= len(items):
                break
                
            row = i // cols
            col = i % cols
            
            x = start_x + col * cell_width
            y = start_y + row * cell_height
            
            # Handle different item formats
            if isinstance(item, dict):
                if 'name' in item:
                    display_text = item['name']
                    original_name = item['name']
                elif 'filename' in item:
                    # New format with filename and href
                    display_text = os.path.splitext(item['filename'])[0]
                    original_name = item['filename']
                else:
                    display_text = str(item)
                    original_name = str(item)
            else:
                display_text = os.path.splitext(item)[0]
                original_name = item
            
            # Enhanced card-style background for each item
            is_highlighted = actual_idx == highlighted
            is_selected = actual_idx in selected_indices
            
            # Determine card background color based on state
            if is_highlighted:
                card_bg = SURFACE_HOVER
                border_color = PRIMARY
                border_width = 3
            elif is_selected:
                card_bg = SURFACE_SELECTED
                border_color = SECONDARY
                border_width = 2
            else:
                card_bg = SURFACE
                border_color = TEXT_DISABLED
                border_width = 1
            
            # Draw card background without shadows
            card_rect = pygame.Rect(x + CARD_PADDING, y + CARD_PADDING, 
                                  cell_width - (CARD_PADDING * 2), cell_height - (CARD_PADDING * 2))
            
            # Draw main card background
            pygame.draw.rect(screen, card_bg, card_rect, border_radius=BORDER_RADIUS)
            
            # Draw card border with enhanced styling
            pygame.draw.rect(screen, border_color, card_rect, border_width, border_radius=BORDER_RADIUS)
            
            # Simplified glow effect for highlighted items
            if is_highlighted:
                glow_rect = pygame.Rect(x + CARD_PADDING - 1, y + CARD_PADDING - 1, 
                                      cell_width - (CARD_PADDING * 2) + 2, cell_height - (CARD_PADDING * 2) + 2)
                pygame.draw.rect(screen, PRIMARY_LIGHT, glow_rect, 1, border_radius=BORDER_RADIUS + 1)
            
            # Draw thumbnail if available with enhanced styling
            thumb_y = y + 15  # Slightly more padding from top
            boxart_url = data[selected_system].get('boxarts', '') if selected_system < len(data) else ''
            thumbnail = get_thumbnail(item, boxart_url)
            
            if thumbnail and thumbnail != "loading":
                # Center thumbnail in cell
                thumb_x = x + (cell_width - THUMBNAIL_SIZE[0]) // 2
                thumb_rect = pygame.Rect(thumb_x, thumb_y, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1])
                
                # Draw thumbnail directly without shadows
                screen.blit(thumbnail, thumb_rect)
                
                # Simplified border styling to prevent flickering
                if is_highlighted:
                    pygame.draw.rect(screen, PRIMARY, thumb_rect, 3, border_radius=THUMBNAIL_BORDER_RADIUS)
                elif is_selected:
                    pygame.draw.rect(screen, SECONDARY, thumb_rect, 2, border_radius=THUMBNAIL_BORDER_RADIUS)
                else:
                    pygame.draw.rect(screen, TEXT_DISABLED, thumb_rect, 1, border_radius=THUMBNAIL_BORDER_RADIUS)
            
            # Simplified selection indicator to prevent flickering
            checkbox_size = 18
            checkbox_x = x + cell_width - checkbox_size - 10
            checkbox_y = y + 10
            checkbox_rect = pygame.Rect(checkbox_x, checkbox_y, checkbox_size, checkbox_size)
            
            if is_selected:
                # Simple filled checkbox for selected items
                pygame.draw.circle(screen, SECONDARY, (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size//2), checkbox_size//2)
                pygame.draw.circle(screen, SECONDARY_DARK, (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size//2), checkbox_size//2, 2)
                
                # Draw simple checkmark
                check_color = TEXT_PRIMARY
                pygame.draw.line(screen, check_color, 
                               (checkbox_x + 4, checkbox_y + checkbox_size//2), 
                               (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size - 4), 2)
                pygame.draw.line(screen, check_color, 
                               (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size - 4), 
                               (checkbox_x + checkbox_size - 4, checkbox_y + 4), 2)
            else:
                # Simple empty circle for unselected items
                circle_color = PRIMARY if is_highlighted else TEXT_DISABLED
                pygame.draw.circle(screen, SURFACE, (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size//2), checkbox_size//2 - 1)
                pygame.draw.circle(screen, circle_color, (checkbox_x + checkbox_size//2, checkbox_y + checkbox_size//2), checkbox_size//2, 2)
            
            # Draw enhanced text (truncated to fit cell width)
            text_y = thumb_y + THUMBNAIL_SIZE[1] + 15
            max_text_width = cell_width - 25
            
            # Enhanced text styling with better colors
            if is_highlighted:
                text_color = TEXT_PRIMARY
                text_shadow_color = (0, 0, 0, 100)
            elif is_selected:
                text_color = SECONDARY_LIGHT
                text_shadow_color = (0, 0, 0, 80)
            else:
                text_color = TEXT_SECONDARY
                text_shadow_color = (0, 0, 0, 60)
                
            test_surf = font.render(display_text, True, text_color)
            if test_surf.get_width() > max_text_width:
                # Truncate text
                for length in range(len(display_text), 0, -1):
                    truncated = display_text[:length] + "..."
                    test_surf = font.render(truncated, True, text_color)
                    if test_surf.get_width() <= max_text_width:
                        display_text = truncated
                        break
            
            text_surf = font.render(display_text, True, text_color)
            text_x = x + (cell_width - text_surf.get_width()) // 2  # Center text
            
            # Draw main text (removed shadow to prevent flickering)
            screen.blit(text_surf, (text_x, text_y))
            
            # Store clickable rectangle for touch/mouse support (using card bounds)
            grid_item_rect = pygame.Rect(x, y, cell_width, cell_height)
            menu_item_rects.append(grid_item_rect)
        
        # Draw bottom status message if games are selected
        if selected_indices:
            message = f"{len(selected_indices)} games selected"
            message_surf = font.render(message, True, SUCCESS)
            screen_width, screen_height = screen.get_size()
            message_y = screen_height - 35
            
            # Draw background for status message
            msg_width = message_surf.get_width()
            status_rect = pygame.Rect(15, message_y - 5, msg_width + 10, message_surf.get_height() + 10)
            pygame.draw.rect(screen, SURFACE, status_rect)
            pygame.draw.rect(screen, SUCCESS, status_rect, 1)
            
            screen.blit(message_surf, (20, message_y))
        
        
        # Display flip handled by main loop to prevent blinking

    def draw_menu(title, items, selected_indices):
        # Clear menu item rectangles for touch/click detection
        global menu_item_rects, menu_scroll_offset
        menu_item_rects.clear()
        menu_scroll_offset = 0  # Initialize scroll offset (will be updated if scrolling is used)
        
        # Use background image for all screens
        draw_background()
            
        y = 30  # Start with more margin
        
        # Simple title styling like other screens
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.5))
        title_surf = title_font.render(title, True, TEXT_PRIMARY)
        
        # Center the title horizontally
        screen_width = screen.get_width()
        title_x = (screen_width - title_surf.get_width()) // 2
        screen.blit(title_surf, (title_x, y))
        
        # Simple underline for title
        title_width = title_surf.get_width()
        underline_y = y + title_surf.get_height() + 8
        pygame.draw.line(screen, PRIMARY, (title_x, underline_y), 
                        (title_x + title_width, underline_y), 3)
        
        y += title_surf.get_height() + 35

        # Draw download instruction if in games mode and games are selected
        if mode == "games" and selected_games:
            start_button_name = get_button_name("start")
            instruction = f"Press {start_button_name} to start downloading"
            
            # Create a subtle background box for the instruction
            inst_surf = font.render(instruction, True, WARNING)
            inst_width = inst_surf.get_width()
            inst_height = inst_surf.get_height()
            
            # Draw background box
            box_rect = pygame.Rect(15, y - 5, inst_width + 10, inst_height + 10)
            pygame.draw.rect(screen, SURFACE, box_rect)
            pygame.draw.rect(screen, WARNING, box_rect, 1)
            
            screen.blit(inst_surf, (20, y))
            y += inst_height + 15
        
        # Draw search instruction if in games mode
        if mode == "games" and not char_selector_mode:
            search_button_name = get_button_name("search")
            search_instruction = f"Press {search_button_name} to search games"
            
            inst_surf = font.render(search_instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (20, y))
            y += FONT_SIZE + 8
        
        y += 10  # Add some space after instructions
        
        # Calculate visible items based on screen height (similar to grid mode)
        row_height = max(FONT_SIZE + 10, THUMBNAIL_SIZE[1] + 10) if mode == "games" else FONT_SIZE + 10
        screen_width, screen_height = screen.get_size()
        
        # Calculate how many items can fit, with a more generous approach like grid mode
        available_height = screen_height - y - 30  # Less bottom margin for more content
        if available_height > 0:
            calculated_items = available_height // row_height
            items_per_page = max(10, calculated_items)  # Minimum 10 items, similar to grid's min 4 rows
        else:
            items_per_page = 10  # Fallback minimum
            
        # Keep highlighted item in the upper third (like grid's second row)
        target_position = max(2, items_per_page // 4)  # Position highlighted item in upper quarter
        start_idx = max(0, highlighted - target_position)
        
        # Store scroll offset for click handling
        menu_scroll_offset = start_idx
        
        # Show more items by extending beyond the calculated page size when possible
        end_idx = min(len(items), start_idx + items_per_page)
        if end_idx < len(items) and (end_idx - start_idx) < items_per_page:
            # If we have room and more items available, extend the view
            additional_items = min(items_per_page - (end_idx - start_idx), len(items) - end_idx)
            end_idx += additional_items
            
        visible_items = items[start_idx:end_idx]
        
        # Draw items with enhanced styling
        for i, item in enumerate(visible_items):
            actual_idx = start_idx + i
            is_highlighted = actual_idx == highlighted
            is_selected = actual_idx in selected_indices
            
            # Enhanced background for items with subtle shadows and gradients
            item_margin = 15
            item_rect = pygame.Rect(item_margin, y - 5, screen.get_width() - (item_margin * 2), row_height)
            
            if is_highlighted:
                # Shadow effect for highlighted items
                shadow_rect = pygame.Rect(item_margin + 2, y - 3, screen.get_width() - (item_margin * 2), row_height)
                pygame.draw.rect(screen, (0, 0, 0, 30), shadow_rect)
                
                # Gradient-like background for highlighted items
                pygame.draw.rect(screen, SURFACE_HOVER, item_rect)
                pygame.draw.rect(screen, PRIMARY, item_rect, 3)
                
                # Add subtle inner glow
                inner_rect = pygame.Rect(item_margin + 3, y - 2, screen.get_width() - (item_margin * 2) - 6, row_height - 6)
                pygame.draw.rect(screen, PRIMARY_LIGHT, inner_rect, 1)
            elif mode == "systems":
                # For systems menu, use simple list style without borders
                pass
            
            # Determine text color and selection indicator
            if is_highlighted:
                text_color = TEXT_PRIMARY
            elif is_selected:
                text_color = SECONDARY
            else:
                text_color = TEXT_SECONDARY
                
            # Modern selection indicator for games
            if mode == "games":
                # Draw modern checkbox/selection indicator
                checkbox_x = 20
                checkbox_y = y + (row_height - 16) // 2
                checkbox_rect = pygame.Rect(checkbox_x, checkbox_y, 16, 16)
                
                if is_selected:
                    # Filled checkbox for selected items
                    pygame.draw.rect(screen, SECONDARY, checkbox_rect)
                    pygame.draw.rect(screen, SECONDARY_DARK, checkbox_rect, 2)
                    # Draw checkmark
                    pygame.draw.line(screen, TEXT_PRIMARY, 
                                   (checkbox_x + 3, checkbox_y + 8), 
                                   (checkbox_x + 7, checkbox_y + 12), 2)
                    pygame.draw.line(screen, TEXT_PRIMARY, 
                                   (checkbox_x + 7, checkbox_y + 12), 
                                   (checkbox_x + 13, checkbox_y + 4), 2)
                else:
                    # Empty checkbox for unselected items
                    pygame.draw.rect(screen, SURFACE, checkbox_rect)
                    border_color = PRIMARY if is_highlighted else TEXT_DISABLED
                    pygame.draw.rect(screen, border_color, checkbox_rect, 2)
            
            prefix = ""  # Remove old text prefix since we have visual indicators
            
            # Handle different item formats
            if isinstance(item, dict):
                if 'name' in item:
                    display_text = item['name']
                    original_name = item['name']
                elif 'filename' in item:
                    # New format with filename and href
                    display_text = os.path.splitext(item['filename'])[0]
                    original_name = item['filename']
                else:
                    display_text = str(item)
                    original_name = str(item)
            else:
                # Remove file extension for display
                display_text = os.path.splitext(item)[0]
                original_name = item
            
            # Determine text positioning
            if mode == "games":
                text_x = 45  # Start after checkbox
                boxart_url = data[selected_system].get('boxarts', '') if selected_system < len(data) else ''
                thumbnail = get_thumbnail(original_name, boxart_url)
                
                if thumbnail and thumbnail != "loading":
                    # Draw thumbnail with enhanced styling
                    thumb_x = text_x
                    thumb_y = y + (row_height - THUMBNAIL_SIZE[1]) // 2
                    thumb_rect = pygame.Rect(thumb_x, thumb_y, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1])
                    
                    # Draw shadow for thumbnail
                    shadow_rect = pygame.Rect(thumb_x + 2, thumb_y + 2, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1])
                    pygame.draw.rect(screen, (0, 0, 0, 50), shadow_rect)
                    
                    screen.blit(thumbnail, thumb_rect)
                    
                    # Enhanced border styling
                    if is_highlighted:
                        pygame.draw.rect(screen, PRIMARY, thumb_rect, 3)
                    elif is_selected:
                        pygame.draw.rect(screen, SECONDARY, thumb_rect, 2)
                    else:
                        pygame.draw.rect(screen, TEXT_DISABLED, thumb_rect, 1)
                    
                    text_x = thumb_x + THUMBNAIL_SIZE[0] + 15  # Move text after thumbnail
            else:
                text_x = 35  # Standard margin for non-games with more padding
                
                # Add geometric icons for system menu items
                if mode == "systems":
                    icon_x = item_margin + 12
                    icon_y = y + (row_height - 20) // 2
                    
                    # Geometric icons for different items
                    if item == "Settings":
                        # Gear icon
                        gear_color = SECONDARY if is_highlighted else TEXT_PRIMARY
                        pygame.draw.rect(screen, gear_color, (icon_x, icon_y, 16, 16), 2)
                        pygame.draw.rect(screen, gear_color, (icon_x + 4, icon_y + 4, 8, 8))
                    elif item == "Utils":
                        # Wrench icon
                        utils_color = SECONDARY if is_highlighted else TEXT_PRIMARY
                        pygame.draw.line(screen, utils_color, (icon_x + 2, icon_y + 2), (icon_x + 14, icon_y + 14), 2)
                        pygame.draw.line(screen, utils_color, (icon_x + 6, icon_y + 14), (icon_x + 14, icon_y + 6), 2)
                    elif item == "Credits":
                        # Heart icon
                        credits_color = SECONDARY if is_highlighted else TEXT_PRIMARY
                        center_x, center_y = icon_x + 8, icon_y + 8
                        heart_points = [(center_x, center_y - 4), (center_x + 4, center_y), (center_x, center_y + 4), (center_x - 4, center_y)]
                        pygame.draw.polygon(screen, credits_color, heart_points, 2)
                    else:
                        # Controller icon for game systems
                        controller_color = PRIMARY if is_highlighted else TEXT_PRIMARY
                        pygame.draw.rect(screen, controller_color, (icon_x, icon_y + 4, 16, 8), 2)
                        pygame.draw.rect(screen, controller_color, (icon_x + 2, icon_y + 2, 3, 3))
                        pygame.draw.rect(screen, controller_color, (icon_x + 11, icon_y + 2, 3, 3))
                    
                    text_x += 30  # Move text over to make room for icon
            
            # Draw text with enhanced styling
            text_y = y + (row_height - FONT_SIZE) // 2  # Center text vertically
            
            # For highlighted items in systems mode, use slightly larger font
            if mode == "systems" and is_highlighted:
                highlight_font = pygame.font.Font(None, int(FONT_SIZE * 1.1))
                item_surf = highlight_font.render(display_text, True, text_color)
            else:
                item_surf = font.render(display_text, True, text_color)
            
            screen.blit(item_surf, (text_x, text_y))
            
            # Store clickable rectangle for touch/mouse support (use current y position)
            item_rect = pygame.Rect(0, y, screen.get_width(), row_height)
            menu_item_rects.append(item_rect)
            
            y += row_height

        # Draw bottom status message if games are selected
        if mode == "games" and selected_games:
            message = f"{len(selected_games)} games selected"
            message_surf = font.render(message, True, SUCCESS)
            screen_width, screen_height = screen.get_size()
            message_y = screen_height - 35
            
            # Draw background for status message
            msg_width = message_surf.get_width()
            status_rect = pygame.Rect(15, message_y - 5, msg_width + 10, message_surf.get_height() + 10)
            pygame.draw.rect(screen, SURFACE, status_rect)
            pygame.draw.rect(screen, SUCCESS, status_rect, 1)
            
            screen.blit(message_surf, (20, message_y))
        
        # Draw pagination info if supported
        if mode == "games" and len(data) > 0 and selected_system < len(data) and data[selected_system].get('supports_pagination', False):
            page_message = f"Page {current_page + 1} - Use L/R to change page"
            page_surf = font.render(page_message, True, TEXT_DISABLED)
            screen_width, screen_height = screen.get_size()
            
            # Position pagination below status message if present
            page_y = screen_height - 20 if not selected_games else screen_height - 65
            screen.blit(page_surf, (20, page_y))


        # Display flip handled by main loop to prevent blinking

    def draw_game_details_modal(game_item):
        """Draw the game details modal overlay with enhanced styling"""
        # Get actual screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Enhanced semi-transparent background overlay with blur effect
        overlay = pygame.Surface((screen_width, screen_height))
        overlay.set_alpha(160)  # More opaque for better contrast
        overlay.fill(BACKGROUND)
        screen.blit(overlay, (0, 0))
        
        # Make modal much larger - prioritize the thumbnail display
        modal_width = min(int(screen_width * 0.95), max(500, screen_width - 50))
        modal_height = min(int(screen_height * 0.95), max(400, screen_height - 50))
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        
        # Draw main modal background
        modal_rect = pygame.Rect(modal_x, modal_y, modal_width, modal_height)
        pygame.draw.rect(screen, SURFACE, modal_rect, border_radius=BORDER_RADIUS)
        
        # Draw simple border styling
        pygame.draw.rect(screen, PRIMARY, modal_rect, 2, border_radius=BORDER_RADIUS)
        
        # Game name
        if isinstance(game_item, dict):
            if 'name' in game_item:
                game_name = game_item.get('name', 'Unknown Game')
            elif 'filename' in game_item:
                game_name = os.path.splitext(game_item['filename'])[0]
            else:
                game_name = 'Unknown Game'
        else:
            game_name = os.path.splitext(game_item)[0] if isinstance(game_item, str) else 'Unknown Game'
        
        # Minimize title to prioritize image space
        responsive_font_size = get_responsive_font_size()
        title_font = pygame.font.Font(None, int(responsive_font_size * 1.0))  # Smaller title
        title_surf = title_font.render("Game Details", True, TEXT_PRIMARY)
        
        responsive_margin = get_responsive_margin()
        title_x = modal_x + responsive_margin
        title_y = modal_y + responsive_margin
        screen.blit(title_surf, (title_x, title_y))
        
        # Draw title underline
        title_width = title_surf.get_width()
        pygame.draw.line(screen, PRIMARY, (title_x, title_y + title_surf.get_height() + 5), 
                        (title_x + title_width, title_y + title_surf.get_height() + 5), 2)
        
        # Minimize spacing to maximize image area
        margin = responsive_margin  # Use consistent responsive margin
        spacing = get_responsive_spacing()
        name_y = title_y + title_surf.get_height() + spacing  # Reduced spacing
        max_name_width = modal_width - (margin * 2)
        
        # Simple text wrapping
        words = game_name.split()
        lines = []
        current_line = []
        
        # Use responsive font for text wrapping calculations
        responsive_text_font = pygame.font.Font(None, responsive_font_size)
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_surf = responsive_text_font.render(test_line, True, TEXT_PRIMARY)
            if test_surf.get_width() <= max_name_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Single word too long
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Minimize text - only show 1-2 lines maximum to prioritize image space
        max_lines = min(2, len(lines))  # Maximum 2 lines to save space for big image
        for i, line in enumerate(lines[:max_lines]):
            name_surf = responsive_text_font.render(line, True, GREEN)
            screen.blit(name_surf, (modal_x + margin, name_y + i * (responsive_font_size + spacing//2)))
        
        # Compact file size display - smaller font to save space
        size_y = name_y + len(lines[:max_lines]) * (responsive_font_size + spacing//2) + spacing//2
        if isinstance(game_item, dict) and game_item.get('size'):
            size_font = pygame.font.Font(None, int(responsive_font_size * 0.75))  # Smaller size text
            size_text = f"Size: {game_item['size']}"
            size_surf = size_font.render(size_text, True, TEXT_PRIMARY)
            screen.blit(size_surf, (modal_x + margin, size_y))
            size_y += int(responsive_font_size * 0.75) + spacing
        
        # Draw large image if available with enhanced styling
        image_y = size_y
        boxart_url = data[selected_system].get('boxarts', '') if selected_system < len(data) else ''
        
        # Try to get high-resolution image first, fallback to thumbnail
        hires_image = get_hires_thumbnail(game_item, boxart_url)
        thumbnail = hires_image if hires_image and hires_image != "loading" else get_thumbnail(game_item, boxart_url)
        
        if thumbnail and thumbnail != "loading":
            # THE IMAGE IS THE MAIN FOCUS - use almost all modal space
            available_width = modal_width - (margin * 2)
            # Reserve minimal space only for close button and very basic text
            reserved_space = responsive_font_size * 3  # Minimal space reservation
            available_height = modal_height - (image_y - modal_y) - reserved_space
            
            # Use 95% of available space for the image - make it HUGE and dominant!
            max_image_size = min(available_width * 0.95, available_height * 0.95)
            
            try:
                # Scale image proportionally to fit within the available space with better quality
                original_size = thumbnail.get_size()
                scale_factor = min(max_image_size / original_size[0], max_image_size / original_size[1])
                new_width = int(original_size[0] * scale_factor)
                new_height = int(original_size[1] * scale_factor)
                large_size = (new_width, new_height)
                
                # Enhanced scaling with multiple quality approaches
                large_image = None
                
                # Try multiple scaling methods for best quality
                try:
                    # Method 1: Multi-step scaling for very large scale factors (better quality)
                    if scale_factor < 0.5:
                        # For significant downscaling, do it in steps for better quality
                        temp_image = thumbnail
                        current_factor = 1.0
                        
                        while current_factor > scale_factor * 2:
                            current_factor *= 0.75  # Scale down by 75% each step
                            temp_size = (int(original_size[0] * current_factor), int(original_size[1] * current_factor))
                            temp_image = pygame.transform.smoothscale(temp_image, temp_size)
                        
                        # Final scaling to exact target size
                        large_image = pygame.transform.smoothscale(temp_image, large_size)
                    else:
                        # For moderate scaling, use direct smoothscale
                        large_image = pygame.transform.smoothscale(thumbnail, large_size)
                        
                except Exception as e:
                    # Method 2: Fallback to direct smoothscale
                    try:
                        large_image = pygame.transform.smoothscale(thumbnail, large_size)
                    except:
                        # Method 3: Last resort - regular scale with post-processing
                        large_image = pygame.transform.scale(thumbnail, large_size)
                        
                        # Apply simple sharpening filter by blending with a slightly scaled version
                        try:
                            # Create a slightly smaller version and blend for sharpening effect
                            sharp_size = (max(1, new_width - 2), max(1, new_height - 2))
                            sharp_image = pygame.transform.scale(thumbnail, sharp_size)
                            sharp_image = pygame.transform.scale(sharp_image, large_size)
                            
                            # Blend original and sharpened (simple sharpening)
                            large_image.set_alpha(200)
                            sharp_image.set_alpha(55)
                            temp_surface = pygame.Surface(large_size, pygame.SRCALPHA)
                            temp_surface.blit(large_image, (0, 0))
                            temp_surface.blit(sharp_image, (0, 0), special_flags=pygame.BLEND_ADD)
                            large_image = temp_surface
                        except:
                            pass  # Use basic scaled image if sharpening fails
                
                if large_image:
                    image_x = modal_x + (modal_width - large_size[0]) // 2
                    
                    # Add subtle drop shadow for better visual separation
                    shadow_offset = 3
                    shadow_rect = pygame.Rect(image_x + shadow_offset, image_y + shadow_offset, large_size[0], large_size[1])
                    shadow_surface = pygame.Surface((large_size[0], large_size[1]), pygame.SRCALPHA)
                    shadow_surface.fill((0, 0, 0, 40))  # Semi-transparent black
                    screen.blit(shadow_surface, (image_x + shadow_offset, image_y + shadow_offset))
                    
                    # Draw the enhanced scaled image
                    screen.blit(large_image, (image_x, image_y))
                    
                    # Draw enhanced border with subtle glow effect
                    image_rect = pygame.Rect(image_x, image_y, large_size[0], large_size[1])
                    # Outer glow
                    glow_rect = pygame.Rect(image_x - 1, image_y - 1, large_size[0] + 2, large_size[1] + 2)
                    pygame.draw.rect(screen, PRIMARY_LIGHT, glow_rect, 1, border_radius=THUMBNAIL_BORDER_RADIUS + 1)
                    # Main border
                    pygame.draw.rect(screen, PRIMARY, image_rect, 2, border_radius=THUMBNAIL_BORDER_RADIUS)
                
            except:
                # Fallback to original thumbnail with enhanced styling
                image_x = modal_x + (modal_width - THUMBNAIL_SIZE[0]) // 2
                
                screen.blit(thumbnail, (image_x, image_y))
                pygame.draw.rect(screen, PRIMARY, (image_x, image_y, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1]), 2, border_radius=THUMBNAIL_BORDER_RADIUS)
        else:
            # Enhanced "No image available" display
            no_image_text = "No image available"
            no_image_surf = font.render(no_image_text, True, TEXT_SECONDARY)
            no_image_x = modal_x + (modal_width - no_image_surf.get_width()) // 2
            
            # Draw placeholder box
            placeholder_rect = pygame.Rect(no_image_x - 20, image_y - 10, no_image_surf.get_width() + 40, no_image_surf.get_height() + 20)
            pygame.draw.rect(screen, SURFACE_HOVER, placeholder_rect, border_radius=BORDER_RADIUS)
            pygame.draw.rect(screen, TEXT_DISABLED, placeholder_rect, 1, border_radius=BORDER_RADIUS)
            
            screen.blit(no_image_surf, (no_image_x, image_y))
        
        # Add download and close buttons (only for touchscreen)
        global download_button_rect, close_button_rect
        if touchscreen_available:
            # Responsive button sizing
            button_height = max(35, int(responsive_font_size * 1.5))
            button_width = max(100, int(screen_width * 0.15))
            button_spacing = spacing * 2
            
            # Ensure buttons fit within modal by positioning them with adequate margin
            download_button_x = modal_x + (modal_width - (button_width * 2 + button_spacing)) // 2
            download_button_y = modal_y + modal_height - button_height - 20  # Fixed 20px margin from bottom
            
            # Download button
            download_button_rect = pygame.Rect(download_button_x, download_button_y, button_width, button_height)
            pygame.draw.rect(screen, SUCCESS, download_button_rect, border_radius=BORDER_RADIUS)
            pygame.draw.rect(screen, TEXT_PRIMARY, download_button_rect, 2, border_radius=BORDER_RADIUS)
            
            # Use responsive font for button text
            button_font = pygame.font.Font(None, int(responsive_font_size * 0.9))
            download_text = button_font.render("Download", True, TEXT_PRIMARY)
            download_text_x = download_button_x + (button_width - download_text.get_width()) // 2
            download_text_y = download_button_y + (button_height - download_text.get_height()) // 2
            screen.blit(download_text, (download_text_x, download_text_y))
            
            # Close button  
            close_button_x = download_button_x + button_width + button_spacing
            close_button_y = download_button_y
            
            close_button_rect = pygame.Rect(close_button_x, close_button_y, button_width, button_height)
            pygame.draw.rect(screen, SURFACE_HOVER, close_button_rect, border_radius=BORDER_RADIUS)
            pygame.draw.rect(screen, TEXT_PRIMARY, close_button_rect, 2, border_radius=BORDER_RADIUS)
            
            close_text = button_font.render("Close", True, TEXT_PRIMARY)
            close_text_x = close_button_x + (button_width - close_text.get_width()) // 2
            close_text_y = close_button_y + (button_height - close_text.get_height()) // 2
            screen.blit(close_text, (close_text_x, close_text_y))
        else:
            # Reset button rects when not showing touchscreen buttons
            download_button_rect = None
            close_button_rect = None
        
        # Enhanced instructions with responsive positioning and fonts
        back_button_name = get_button_name("back")
        instruction_text = f"Press {back_button_name} to close or tap buttons"
        instruction_font = pygame.font.Font(None, int(responsive_font_size * 0.8))
        instruction_surf = instruction_font.render(instruction_text, True, TEXT_PRIMARY)
        instruction_x = modal_x + (modal_width - instruction_surf.get_width()) // 2
        
        # Position instructions above the buttons with responsive spacing
        instruction_y = download_button_y - instruction_surf.get_height() - spacing * 2 if 'download_button_y' in locals() else modal_y + modal_height - responsive_font_size * 3
        
        # Draw enhanced instruction background
        inst_width = instruction_surf.get_width()
        inst_height = instruction_surf.get_height()
        inst_rect = pygame.Rect(instruction_x - 15, instruction_y - 8, inst_width + 30, inst_height + 16)
        pygame.draw.rect(screen, SURFACE, inst_rect, border_radius=BORDER_RADIUS)
        pygame.draw.rect(screen, PRIMARY, inst_rect, 2, border_radius=BORDER_RADIUS)
        
        # Simple instruction styling without glow
        
        screen.blit(instruction_surf, (instruction_x, instruction_y))

    def draw_folder_browser_modal():
        """Draw the folder browser modal overlay"""
        global folder_browser_scroll_offset, folder_browser_item_rects
        folder_browser_item_rects = []  # Clear previous rects
        
        # Get actual screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Semi-transparent background overlay
        overlay = pygame.Surface((screen_width, screen_height))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))
        
        # Modal sizing
        modal_width = min(int(screen_width * 0.9), 600)
        modal_height = min(int(screen_height * 0.8), 500)
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        
        modal_rect = pygame.Rect(modal_x, modal_y, modal_width, modal_height)
        pygame.draw.rect(screen, WHITE, modal_rect)
        pygame.draw.rect(screen, BLACK, modal_rect, 3)
        
        # Title
        if selected_system_to_add is not None:
            if selected_system_to_add.get("type") == "work_dir":
                title_text = f"Select Work Directory"
            elif selected_system_to_add.get("type") == "nsz_keys":
                title_text = f"Select NSZ Keys File"
            elif selected_system_to_add.get("type") == "archive_json":
                title_text = f"Select Archive JSON File"
            else:
                title_text = f"Select ROM Folder for {selected_system_to_add['name']}"
        else:
            title_text = "Select Folder"
        title_surf = font.render(title_text, True, TEXT_PRIMARY)
        title_x = modal_x + 20
        title_y = modal_y + 20
        screen.blit(title_surf, (title_x, title_y))
        
        # Current path
        current_path_display = folder_browser_current_path
        if len(current_path_display) > 50:
            current_path_display = "..." + current_path_display[-47:]
        
        path_surf = font.render(f"Path: {current_path_display}", True, GRAY)
        path_y = title_y + 35
        screen.blit(path_surf, (title_x, path_y))
        
        # Instructions
        select_button_name = get_button_name("select")
        back_button_name = get_button_name("back")
        detail_button_name = get_button_name("detail")
        create_folder_button_name = get_button_name("create_folder")
        
        if selected_system_to_add is not None:
            if selected_system_to_add.get("type") == "work_dir":
                instructions = [
                    f"Use D-pad to navigate",
                    f"Press {select_button_name} to enter folder or create new folder",
                    f"Press {detail_button_name} to select this folder as work directory",
                    f"Press {back_button_name} to cancel"
                ]
            elif selected_system_to_add.get("type") == "nsz_keys":
                instructions = [
                    f"Use D-pad to navigate",
                    f"Press {select_button_name} to enter [DIR] or select [KEY] file",
                    f"Press {detail_button_name} to select current folder path",
                    f"Press {back_button_name} to cancel"
                ]
            elif selected_system_to_add.get("type") == "archive_json":
                instructions = [
                    f"Use D-pad to navigate",
                    f"Press {select_button_name} to enter [DIR] or select [JSON] file",
                    f"Navigate to find JSON configuration files",
                    f"Press {back_button_name} to cancel"
                ]
            elif selected_system_to_add.get("type") == "nsz_converter":
                instructions = [
                    f"Use D-pad to navigate",
                    f"Press {select_button_name} to enter [DIR] or select [NSZ] file",
                    f"Navigate to find NSZ files to convert to NSP",
                    f"Press {back_button_name} to cancel"
                ]
            else:
                instructions = [
                    f"Use D-pad to navigate",
                    f"Press {select_button_name} to enter folder or create new folder",
                    f"Press {detail_button_name} to select this folder for {selected_system_to_add['name']}",
                    f"Press {back_button_name} to cancel"
                ]
        else:
            instructions = [
                f"Use D-pad to navigate",
                f"Press {select_button_name} to enter folder or create new folder",
                f"Press {detail_button_name} to select current folder",
                f"Press {back_button_name} to cancel"
            ]
        
        inst_y = path_y + 35
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (title_x, inst_y))
            inst_y += 20
        
        # Calculate list area
        list_y = inst_y + 20
        list_height = modal_height - (list_y - modal_y) - 20
        row_height = FONT_SIZE + 5
        items_per_screen = max(1, list_height // row_height)
        
        # Calculate scroll
        total_items = len(folder_browser_items)
        max_scroll = max(0, total_items - items_per_screen)
        
        # Auto-scroll to keep highlighted item visible
        if folder_browser_highlighted < folder_browser_scroll_offset:
            folder_browser_scroll_offset = folder_browser_highlighted
        elif folder_browser_highlighted >= folder_browser_scroll_offset + items_per_screen:
            folder_browser_scroll_offset = folder_browser_highlighted - items_per_screen + 1
        
        folder_browser_scroll_offset = max(0, min(folder_browser_scroll_offset, max_scroll))
        
        # Draw folder items
        start_idx = folder_browser_scroll_offset
        end_idx = min(start_idx + items_per_screen, total_items)
        visible_items = folder_browser_items[start_idx:end_idx]
        
        # Debug: Print folder browser items
        print(f"Folder browser items: {len(folder_browser_items)} total, highlighted: {folder_browser_highlighted}")
        for i, item in enumerate(folder_browser_items):
            print(f"  {i}: {item['name']} ({item['type']})")
        
        for i, item in enumerate(visible_items):
            actual_idx = start_idx + i
            is_highlighted = actual_idx == folder_browser_highlighted
            
            item_y = list_y + i * row_height
            color = PRIMARY if is_highlighted else BLACK
            
            # Prefix based on type
            if item["type"] == "parent":
                display_name = f"[DIR] {item['name']} (Go back)"
            elif item["type"] == "folder":
                display_name = f"[DIR] {item['name']}"
            elif item["type"] == "create_folder":
                display_name = f"[DIR] {item['name']}"
            elif item["type"] == "error":
                display_name = f"[ERR] {item['name']}"
                color = GRAY
            elif item["type"] == "keys_file":
                display_name = f"[KEY] {item['name']}"
            elif item["type"] == "json_file":
                display_name = f"[JSON] {item['name']}"
            elif item["type"] == "nsz_file":
                display_name = f"[NSZ] {item['name']}"
            else:
                display_name = item['name']
            
            # Truncate if too long
            max_width = modal_width - 60
            test_surf = font.render(display_name, True, color)
            if test_surf.get_width() > max_width:
                while len(display_name) > 5 and test_surf.get_width() > max_width:
                    display_name = display_name[:-4] + "..."
                    test_surf = font.render(display_name, True, color)
            
            # Highlight background
            if is_highlighted:
                highlight_rect = pygame.Rect(modal_x + 10, item_y - 2, modal_width - 20, row_height)
                pygame.draw.rect(screen, (240, 240, 240), highlight_rect)
            
            # Draw item
            item_surf = font.render(display_name, True, color)
            screen.blit(item_surf, (title_x, item_y))
            
            # Store clickable rectangle for touch/mouse support
            item_rect = pygame.Rect(modal_x + 10, item_y - 2, modal_width - 20, row_height)
            folder_browser_item_rects.append((item_rect, actual_idx))
        
        # Add selection buttons at the bottom of the modal (only for touchscreen)
        if touchscreen_available:
            button_height = 40
            button_width = 150  # Increased width to fit longer button text
            button_spacing = 20
            button_y = modal_y + modal_height - button_height - 15
            
            # Determine what type of selection is appropriate based on context and highlighted item
            select_button_text = "Select Folder"
            if selected_system_to_add:
                selection_type = selected_system_to_add.get("type", "")
                
                # Check what's currently highlighted
                highlighted_item_type = None
                if folder_browser_items and folder_browser_highlighted < len(folder_browser_items):
                    highlighted_item_type = folder_browser_items[folder_browser_highlighted]["type"]
                
                if selection_type == "nsz_keys":
                    if highlighted_item_type == "keys_file":
                        select_button_text = "Select Keys File"
                    else:
                        select_button_text = "Use This Folder"
                elif selection_type == "archive_json":
                    if highlighted_item_type == "json_file":
                        select_button_text = "Select JSON File"
                    else:
                        select_button_text = "Use This Folder"
                elif selection_type == "nsz_converter":
                    if highlighted_item_type == "nsz_file":
                        select_button_text = "Convert NSZ File"
                    else:
                        select_button_text = "Browse Here"
                elif selection_type == "work_dir":
                    select_button_text = "Set Work Dir"
                elif selection_type == "system_folder":
                    select_button_text = "Set ROM Folder"
                else:
                    select_button_text = "Set ROM Dir"
            
            # Select button (left)
            select_button_x = modal_x + (modal_width - (button_width * 2 + button_spacing)) // 2
            
            global folder_select_button_rect, folder_cancel_button_rect
            folder_select_button_rect = pygame.Rect(select_button_x, button_y, button_width, button_height)
            pygame.draw.rect(screen, SUCCESS, folder_select_button_rect, border_radius=8)
            pygame.draw.rect(screen, TEXT_PRIMARY, folder_select_button_rect, 2, border_radius=8)
            
            select_text = font.render(select_button_text, True, TEXT_PRIMARY)
            select_text_x = select_button_x + (button_width - select_text.get_width()) // 2
            select_text_y = button_y + (button_height - select_text.get_height()) // 2
            screen.blit(select_text, (select_text_x, select_text_y))
            
            # Cancel button (right)
            cancel_button_x = select_button_x + button_width + button_spacing
            folder_cancel_button_rect = pygame.Rect(cancel_button_x, button_y, button_width, button_height)
            pygame.draw.rect(screen, SURFACE_HOVER, folder_cancel_button_rect, border_radius=8)
            pygame.draw.rect(screen, TEXT_PRIMARY, folder_cancel_button_rect, 2, border_radius=8)
            
            cancel_text = font.render("Cancel", True, TEXT_PRIMARY)
            cancel_text_x = cancel_button_x + (button_width - cancel_text.get_width()) // 2
            cancel_text_y = button_y + (button_height - cancel_text.get_height()) // 2
            screen.blit(cancel_text, (cancel_text_x, cancel_text_y))
        else:
            # Reset button rects when not showing touchscreen buttons
            folder_select_button_rect = None
            folder_cancel_button_rect = None

    def draw_loading_message(message):
        draw_background()
        
        # Create centered layout
        screen_width, screen_height = screen.get_size()
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        # Draw modern card background
        card_width = min(screen_width - 80, 500)
        card_height = 200
        card_x = center_x - card_width // 2
        card_y = center_y - card_height // 2
        
        # Draw card shadow
        shadow_rect = pygame.Rect(card_x + 4, card_y + 4, card_width, card_height)
        pygame.draw.rect(screen, (0, 0, 0, 40), shadow_rect, border_radius=12)
        
        # Draw card background
        card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
        pygame.draw.rect(screen, SURFACE, card_rect, border_radius=12)
        pygame.draw.rect(screen, PRIMARY, card_rect, 2, border_radius=12)
        
        # Draw title with improved typography
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.4))
        title_surf = title_font.render("Loading", True, TEXT_PRIMARY)
        title_x = center_x - title_surf.get_width() // 2
        title_y = card_y + 30
        screen.blit(title_surf, (title_x, title_y))
        
        # Draw the actual loading message
        message_font = pygame.font.Font(None, FONT_SIZE)
        message_surf = message_font.render(message, True, TEXT_SECONDARY)
        message_x = center_x - message_surf.get_width() // 2
        message_y = card_y + 80
        screen.blit(message_surf, (message_x, message_y))
        
        # Draw loading animation (optional spinner or dots)
        dots = "..." if pygame.time.get_ticks() % 1500 < 500 else ".." if pygame.time.get_ticks() % 1500 < 1000 else "."
        dots_surf = message_font.render(dots, True, PRIMARY)
        dots_x = center_x - dots_surf.get_width() // 2
        dots_y = card_y + 120
        screen.blit(dots_surf, (dots_x, dots_y))
        
        # Update the display so the loading message is visible
        pygame.display.flip()
        
    def draw_error_message(title, error_lines, wait_time=5000):
        """Display detailed error message with multiple lines"""
        draw_background()
        
        # Create centered layout
        screen_width, screen_height = screen.get_size()
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        # Calculate required height based on number of lines
        line_height = FONT_SIZE + 4
        content_height = len(error_lines) * line_height + 120
        card_height = min(max(content_height, 250), screen_height - 60)
        
        # Draw modern card background
        card_width = min(screen_width - 60, 800)
        card_x = center_x - card_width // 2
        card_y = center_y - card_height // 2
        
        # Draw card shadow
        shadow_rect = pygame.Rect(card_x + 4, card_y + 4, card_width, card_height)
        pygame.draw.rect(screen, (0, 0, 0, 40), shadow_rect, border_radius=12)
        
        # Draw card background
        card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
        pygame.draw.rect(screen, SURFACE, card_rect, border_radius=12)
        pygame.draw.rect(screen, (220, 53, 69), card_rect, 2, border_radius=12)  # Red border for errors
        
        # Draw title
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.4))
        title_surf = title_font.render(title, True, (220, 53, 69))  # Red title
        title_x = center_x - title_surf.get_width() // 2
        title_y = card_y + 20
        screen.blit(title_surf, (title_x, title_y))
        
        # Draw accent line under title
        line_width = title_surf.get_width() // 2
        line_x = center_x - line_width // 2
        line_y = title_y + title_surf.get_height() + 8
        pygame.draw.line(screen, (220, 53, 69), (line_x, line_y), (line_x + line_width, line_y), 3)
        
        # Draw error lines with scrolling if needed
        start_y = line_y + 20
        max_display_lines = (card_height - 140) // line_height
        
        if len(error_lines) <= max_display_lines:
            # Show all lines
            for i, line in enumerate(error_lines):
                line_surf = font.render(line, True, TEXT_SECONDARY)
                line_x = card_x + 20
                line_y = start_y + i * line_height
                screen.blit(line_surf, (line_x, line_y))
        else:
            # Show first lines and indicate truncation
            for i in range(max_display_lines - 1):
                line = error_lines[i]
                line_surf = font.render(line, True, TEXT_SECONDARY)
                line_x = card_x + 20
                line_y = start_y + i * line_height
                screen.blit(line_surf, (line_x, line_y))
            
            # Show truncation indicator
            truncated_surf = font.render(f"... ({len(error_lines) - max_display_lines + 1} more lines)", True, TEXT_SECONDARY)
            line_x = card_x + 20
            line_y = start_y + (max_display_lines - 1) * line_height
            screen.blit(truncated_surf, (line_x, line_y))
        
        # Draw instructions
        back_button_name = get_button_name("back")
        instructions = [f"Press {back_button_name} to continue"]
        
        inst_y = card_y + card_height - 40
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_SECONDARY)
            inst_x = center_x - inst_surf.get_width() // 2
            screen.blit(inst_surf, (inst_x, inst_y))
            inst_y += inst_surf.get_height() + 5
        
        pygame.display.flip()
        
        # Wait for user input or timeout
        start_time = pygame.time.get_ticks()
        waiting = True
        while waiting and (pygame.time.get_ticks() - start_time) < wait_time:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or \
                     (event.type == pygame.JOYBUTTONDOWN and event.button == joystick_mapping.get("back", 1)):
                    waiting = False
                elif hasattr(pygame, '_sdl2') and hasattr(pygame._sdl2, 'touch') and touch_available:
                    if event.type == pygame.FINGERDOWN:
                        waiting = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    waiting = False
            pygame.time.wait(50)
        
        # Draw accent line under title
        line_width = title_surf.get_width() // 2
        line_x = center_x - line_width // 2
        line_y = title_y + title_surf.get_height() + 8
        pygame.draw.line(screen, PRIMARY, (line_x, line_y), (line_x + line_width, line_y), 3)
        
        # Draw message with better positioning
        message_surf = font.render(message, True, TEXT_SECONDARY)
        message_x = center_x - message_surf.get_width() // 2
        message_y = line_y + 25
        screen.blit(message_surf, (message_x, message_y))
        
        # Draw instructions centered
        back_button_name = get_button_name("back")
        instructions = [
            "Please wait...",
            f"Press {back_button_name} to cancel"
        ]
        
        inst_y = message_y + message_surf.get_height() + 25
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            inst_x = center_x - inst_surf.get_width() // 2
            screen.blit(inst_surf, (inst_x, inst_y))
            inst_y += FONT_SIZE + 8
        
        
        if not show_game_details:
            pygame.display.flip()

    def draw_character_selector():
        """Draw the character selector for search input"""
        draw_background()
        
        # Create centered layout
        screen_width, screen_height = screen.get_size()
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        # Character grid layout
        chars = [
            ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
            ['K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T'],
            ['U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3'],
            ['4', '5', '6', '7', '8', '9', ' ', 'DEL', 'CLEAR', 'DONE']
        ]
        
        # Draw title card
        title_card_height = 80
        title_y = 20
        card_rect = pygame.Rect(20, title_y, screen_width - 40, title_card_height)
        pygame.draw.rect(screen, SURFACE, card_rect, border_radius=8)
        pygame.draw.rect(screen, PRIMARY, card_rect, 2, border_radius=8)
        
        # Draw title
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.2))
        title_surf = title_font.render("Search Games", True, TEXT_PRIMARY)
        title_x = center_x - title_surf.get_width() // 2
        screen.blit(title_surf, (title_x, title_y + 10))
        
        # Draw current search query
        query_display = f"Search: {search_query}_" if len(search_query) < 30 else f"Search: {search_query[-27:]}..."
        query_surf = font.render(query_display, True, TEXT_SECONDARY)
        query_x = center_x - query_surf.get_width() // 2
        screen.blit(query_surf, (query_x, title_y + 45))
        
        # Character grid
        grid_start_y = title_y + title_card_height + 20
        cell_width = 45
        cell_height = 40
        grid_width = len(chars[0]) * cell_width
        grid_x = center_x - grid_width // 2
        
        for row_idx, row in enumerate(chars):
            for col_idx, char in enumerate(row):
                x = grid_x + col_idx * cell_width
                y = grid_start_y + row_idx * cell_height
                
                # Highlight selected character
                is_selected = (char_x == col_idx and char_y == row_idx)
                
                # Draw character cell
                cell_rect = pygame.Rect(x, y, cell_width - 2, cell_height - 2)
                if is_selected:
                    pygame.draw.rect(screen, PRIMARY, cell_rect, border_radius=6)
                    text_color = BACKGROUND
                else:
                    pygame.draw.rect(screen, SURFACE, cell_rect, border_radius=6)
                    pygame.draw.rect(screen, TEXT_DISABLED, cell_rect, 1, border_radius=6)
                    text_color = TEXT_PRIMARY
                
                # Draw character text
                char_font = pygame.font.Font(None, FONT_SIZE - 4) if len(char) > 1 else font
                char_surf = char_font.render(char, True, text_color)
                char_x_pos = x + (cell_width - char_surf.get_width()) // 2
                char_y_pos = y + (cell_height - char_surf.get_height()) // 2
                screen.blit(char_surf, (char_x_pos, char_y_pos))
        
        # Draw instructions
        instructions = [
            "Use D-pad to navigate, A button to select character",
            f"Press {get_button_name('back')} to cancel search"
        ]
        
        inst_y = grid_start_y + len(chars) * cell_height + 20
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            inst_x = center_x - inst_surf.get_width() // 2
            screen.blit(inst_surf, (inst_x, inst_y))
            inst_y += FONT_SIZE + 8
        
        pygame.display.flip()

    def decode_filename(raw_filename):
        """Properly decode URL-encoded and HTML entity-encoded filenames"""
        try:
            # First decode URL encoding (e.g., %20 -> space, %5B -> [)
            url_decoded = unquote(raw_filename)
            
            # Then decode HTML entities (e.g., &gt; -> >, &amp; -> &)
            html_decoded = html.unescape(url_decoded)
            
            # Handle any remaining character encoding issues
            # Try to encode as latin1 and decode as utf-8 if needed
            try:
                if html_decoded.encode('latin1').decode('utf-8') != html_decoded:
                    html_decoded = html_decoded.encode('latin1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass  # Keep original if encoding conversion fails
            
            return html_decoded
        except Exception:
            # If all decoding fails, return the original
            return raw_filename

    def filter_games_by_search(games, query):
        """Filter games list based on search query"""
        if not query.strip():
            return games
        
        query_lower = query.lower()
        filtered = []
        
        for game in games:
            if isinstance(game, dict):
                if 'name' in game:
                    game_name = game.get('name', '').lower()
                elif 'filename' in game:
                    # New format with filename and href
                    game_name = os.path.splitext(game.get('filename', ''))[0].lower()
                else:
                    game_name = str(game).lower()
            else:
                # Regular filename
                game_name = os.path.splitext(str(game))[0].lower()
            
            if query_lower in game_name:
                filtered.append(game)
        
        return filtered

    def process_downloaded_file(file_path, filename, sys_data, roms_folder, progress_callback=None):
        """
        Unified file processing for downloads.
        Handles ZIP extraction, NSZ decompression, and file organization.
        
        Args:
            file_path: Path to the downloaded file
            filename: Name of the file
            sys_data: System data configuration
            roms_folder: Target ROM folder
            progress_callback: Optional callback for progress updates (text, percent)
        
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            formats = sys_data.get('file_format', [])
            
            def update_progress(text, percent=0):
                if progress_callback:
                    progress_callback(text, percent)
                else:
                    print(f"{text} - {percent}%")
            
            # Handle ZIP extraction
            if filename.endswith(".zip") and sys_data.get('should_unzip', False):
                update_progress(f"Extracting {filename}...", 0)
                
                with ZipFile(file_path, 'r') as zip_ref:
                    total_files = len(zip_ref.namelist())
                    extracted_files = 0
                    
                    for file_info in zip_ref.infolist():
                        zip_ref.extract(file_info, WORK_DIR)
                        extracted_files += 1
                        
                        if extracted_files % 10 == 0 or file_info.file_size > 1024*1024:
                            progress = int((extracted_files / total_files) * 100)
                            update_progress(f"Extracting {filename}... ({extracted_files}/{total_files})", progress)
                    
                    update_progress(f"Extracting {filename}... Complete", 100)
                
                os.remove(file_path)
                
            elif filename.endswith(".nsz"):
                update_progress(f"Attempting NSZ decompression for {filename}...", 0)
                
                # Use the unified NSZ decompression method
                success = decompress_nsz_file(file_path, WORK_DIR, progress_callback=update_progress)
                
                if success:
                    # Find and move all NSP files in work directory to roms folder
                    for file in os.listdir(WORK_DIR):
                        if file.endswith('.nsp'):
                            src_path = os.path.join(WORK_DIR, file)
                            dst_path = os.path.join(roms_folder, file)
                            os.rename(src_path, dst_path)
                            print(f"Moved decompressed NSP: {file}")
                    
                    # Remove original NSZ file
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    return True
                else:
                    return False
            
            # Move all compatible files from work directory to ROMs folder
            update_progress(f"Moving files to ROMS folder...", 0)
            
            files_moved = 0
            for f in os.listdir(WORK_DIR):
                if any(f.endswith(ext) for ext in formats):
                    src_path = os.path.join(WORK_DIR, f)
                    dst_path = os.path.join(roms_folder, f)
                    os.rename(src_path, dst_path)
                    files_moved += 1
                    print(f"Moved file: {f}")
            
            # Clean up remaining files in work directory
            for f in os.listdir(WORK_DIR):
                file_to_remove = os.path.join(WORK_DIR, f)
                if os.path.isfile(file_to_remove):
                    os.remove(file_to_remove)
            
            update_progress(f"Processing complete", 100)
            return True
            
        except Exception as e:
            log_error(f"Error processing file {filename}: {e}")
            if progress_callback:
                progress_callback(f"Error processing {filename}: {e}", 0)
            return False


    def download_files(system, selected_game_indices):
        """Standard download implementation"""
        try:
            sys_data = data[system]
            formats = sys_data.get('file_format', [])
            
            # Check for custom ROM folder setting
            system_name = sys_data['name']
            system_settings = settings.get("system_settings", {})
            custom_folder = system_settings.get(system_name, {}).get('custom_folder', '')
            
            if custom_folder and os.path.exists(custom_folder):
                roms_folder = custom_folder
            else:
                roms_folder = os.path.join(ROMS_DIR, sys_data['roms_folder'])
            
            os.makedirs(roms_folder, exist_ok=True)

            selected_files = [game_list[i] for i in selected_game_indices]
            total = len(selected_files)
            cancelled = False

            for idx, game_item in enumerate(selected_files):
                if cancelled:
                    break
                log_error(f"Downloading game: {game_item}")
                # Handle different game formats
                if isinstance(game_item, dict):
                    if 'name' in game_item:
                        game_name = game_item['name']
                        filename = game_name
                    elif 'filename' in game_item:
                        # New format with filename and href
                        game_name = game_item['filename']
                        filename = game_item['filename']
                    else:
                        game_name = str(game_item)
                        filename = str(game_item)
                else:
                    # Regular filename
                    game_name = game_item
                    filename = game_item
                
                # Calculate overall progress
                overall_progress = int((idx / total) * 100)
                draw_progress_bar(f"Downloading {game_name} ({idx+1}/{total})", overall_progress)
                
                if 'download_url' in sys_data:
                    url = game_item['href']
                    if '.' not in filename:
                        format = sys_data.get('file_format', [])[0]
                        filename = filename + format
                elif 'url' in sys_data:
                    if isinstance(game_item, dict) and 'href' in game_item:
                        url = urljoin(sys_data['url'], game_item['href'])
                    else:
                        url = urljoin(sys_data['url'], filename)
                try:
                    # Prepare request headers and cookies for authentication
                    headers = {}
                    cookies = {}
                    
                    # Check if authentication is configured for this system
                    if 'auth' in sys_data:
                        auth_config = sys_data['auth']
                        if auth_config.get('cookies', False) and 'token' in auth_config:
                            # Use cookie-based authentication
                            cookie_name = auth_config.get('cookie_name', 'auth_token')
                            cookies[cookie_name] = auth_config['token']
                        elif 'token' in auth_config:
                            # Use header-based authentication (Bearer token)
                            headers['Authorization'] = f"Bearer {auth_config['token']}"
                    
                    r = requests.get(url, stream=True, timeout=10, headers=headers, cookies=cookies)
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = pygame.time.get_ticks()
                    last_update = start_time
                    last_downloaded = 0 
                    
                    file_path = os.path.join(WORK_DIR, filename)
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(1024):
                            # Check for cancel button
                            for event in pygame.event.get():
                                if event.type == pygame.JOYBUTTONDOWN and event.button == get_controller_button("back"):
                                    cancelled = True
                                    break
                            if cancelled:
                                break
                            
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Calculate speed every 500ms
                                current_time = pygame.time.get_ticks()
                                if current_time - last_update >= 500:
                                    speed = (downloaded - last_downloaded) * 2  # *2 because we update every 500ms
                                    last_downloaded = downloaded
                                    last_update = current_time
                                    
                                    # Calculate file progress
                                    file_progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
                                    # Calculate overall progress including current file
                                    current_progress = int(((idx + (file_progress / 100)) / total) * 100)
                                    draw_progress_bar(f"Downloading {filename} ({idx+1}/{total})", 
                                                    current_progress, downloaded, total_size, speed)

                    if cancelled:
                        # Clean up the current file if download was cancelled
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        break

                    # Use unified file processing method
                    if not cancelled:
                        def progress_callback(text, percent):
                            draw_progress_bar(text, percent)
                            # Check for cancel during processing
                            for event in pygame.event.get():
                                if event.type == pygame.JOYBUTTONDOWN and event.button == get_controller_button("back"):
                                    nonlocal cancelled
                                    cancelled = True
                                    return
                        
                        success = process_downloaded_file(file_path, filename, sys_data, roms_folder, progress_callback)
                        if not success and not cancelled:
                            # If processing failed, still try to move the original file
                            try:
                                if any(filename.endswith(ext) for ext in formats):
                                    dst_path = os.path.join(roms_folder, filename)
                                    os.rename(file_path, dst_path)
                                    print(f"Moved unprocessed file: {filename}")
                            except Exception as e:
                                print(f"Failed to move unprocessed file: {e}")
                        
                        # Skip the old individual file processing since unified method handles it
                        continue
                    

                except Exception as e:
                    log_error(f"Failed to download {filename}", type(e).__name__, traceback.format_exc())
                
            if cancelled:
                draw_loading_message("Download cancelled")
                pygame.time.wait(1000)  # Show the message for 1 second
        except Exception as e:
            log_error(f"Error in download_files for system {system}", type(e).__name__, traceback.format_exc())

    def list_files(system, page=0):
        try:
            draw_loading_message(f"Loading games for {data[system]['name']}...")
            sys_data = data[system]
            formats = sys_data.get('file_format', [])

            # Check if this is the old JSON API format
            if 'list_url' in sys_data:
                # Old format - JSON API
                list_url = sys_data['list_url']
                array_path = sys_data.get('list_json_file_location', "files")
                file_id = sys_data.get('list_item_id', "name")
                # Prepare request headers and cookies for authentication
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                cookies = {}
                
                # Check if authentication is configured for this system
                if 'auth' in sys_data:
                    auth_config = sys_data['auth']
                    if auth_config.get('cookies', False) and 'token' in auth_config:
                        # Use cookie-based authentication
                        cookie_name = auth_config.get('cookie_name', 'auth_token')
                        cookies[cookie_name] = auth_config['token']
                    elif 'token' in auth_config:
                        # Use header-based authentication (Bearer token)
                        headers['Authorization'] = f"Bearer {auth_config['token']}"
                
                r = requests.get(list_url, timeout=10, headers=headers, cookies=cookies)
                response = r.json()
                
                if isinstance(response, dict) and "files" in response:
                    files = response[array_path]
                    if isinstance(files, list):
                        filtered_files = [f[file_id] for f in files if any(f[file_id].lower().endswith(ext.lower()) for ext in formats)]
                        # Apply USA filter if enabled and system supports it
                        if settings.get("usa_only", False) and sys_data.get('should_filter_usa', True):
                            usa_regex = sys_data.get('usa_regex', '(USA)')
                            filtered_files = [f for f in filtered_files if re.search(usa_regex, f)]
                        return filtered_files
            
            elif 'url' in sys_data:
                url = sys_data['url']
                regex_pattern = sys_data.get('regex', '<a href="([^"]+)"[^>]*>([^<]+)</a>')
                # Prepare request headers and cookies for authentication
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                cookies = {}
                
                # Check if authentication is configured for this system
                if 'auth' in sys_data:
                    auth_config = sys_data['auth']
                    if auth_config.get('cookies', False) and 'token' in auth_config:
                        # Use cookie-based authentication
                        cookie_name = auth_config.get('cookie_name', 'auth_token')
                        cookies[cookie_name] = auth_config['token']
                    elif 'token' in auth_config:
                        # Use header-based authentication (Bearer token)
                        headers['Authorization'] = f"Bearer {auth_config['token']}"
                
                r = requests.get(url, timeout=10, headers=headers, cookies=cookies)
                r.raise_for_status()
                html_content = r.text
                
                
                # Extract file links using regex
                if 'regex' in sys_data:
        
                    # Use the provided named capture group regex
                    matches = re.finditer(regex_pattern, html_content)
                    files = []
                    for match in matches:
                        try:
                            # Try to get the filename and href from named groups
                            href = None
                            filename = None
                            bannerUrl = None
                            file_size = None

                            if 'id' in match.groupdict():
                                id_value = match.groupdict().get('id')
                                if 'download_url' in sys_data:
                                    download_url = sys_data['download_url']
                                    if '<id>' in download_url:
                                        href = download_url.replace('<id>', id_value)
                                    else:
                                        href = id_value
                                else:
                                    href = id_value
                            elif 'href' in match.groupdict():
                                href = match.groupdict().get('href')
                            if 'text' in match.groupdict():
                                filename = decode_filename(match.groupdict().get('text'))
                            else:
                                filename = decode_filename(match.group(1))

                            if 'banner_url' in match.groupdict():
                                bannerUrl = match.groupdict().get('banner_url')
                            if 'size' in match.groupdict():
                                file_size = match.groupdict().get('size')

                            if href and not filename:
                                filename = decode_filename(href)
                                                    # Filter out filenames that start with unknown/problematic characters
                            if filename and not filename[0].isascii():
                                continue
                            # Filter by file format
                            if any(filename.lower().endswith(ext.lower()) for ext in formats):
                                files.append({'filename': filename, 'href': href, 'banner_url': bannerUrl, 'size': file_size})
                            elif 'ignore_extension_filtering' in sys_data and sys_data['ignore_extension_filtering']:
                                files.append({'filename': filename, 'href': href, 'banner_url': bannerUrl, 'size': file_size})
                        except:
                            continue
                else:
                    # Simple regex for href links
                    matches = re.findall(regex_pattern, html_content)
                    files = []
                    for href, text in matches:
                        filename = decode_filename(text or href)
                        # Filter out filenames that start with unknown/problematic characters
                        if filename and not filename[0].isascii():
                            continue
                        if any(filename.lower().endswith(ext.lower()) for ext in formats):
                            files.append({'filename': filename, 'href': href, 'size': None})
                
                # Apply USA filter if enabled and system supports it
                if settings.get("usa_only", False) and sys_data.get('should_filter_usa', True):
                    usa_regex = sys_data.get('usa_regex', '(USA)')
                    files = [f for f in files if re.search(usa_regex, f['filename'])]
                
                return sorted(files, key=lambda x: x['filename'])
            
            return []
        except Exception as e:
            log_error(f"Failed to fetch list for system {system}", type(e).__name__, traceback.format_exc())
            return []

    def load_folder_contents(path):
        """Load folder contents for browser"""
        global folder_browser_items, folder_browser_highlighted, folder_browser_scroll_offset
        
        try:
            # Normalize path
            path = os.path.abspath(path)
            items = []
            
            # Add parent directory option unless we're at root
            if path != "/" and path != os.path.dirname(path):
                items.append({"name": "..", "type": "parent", "path": os.path.dirname(path)})
            
            # Add "Create New Folder" option
            items.append({"name": "[CREATE NEW FOLDER]", "type": "create_folder", "path": path})
            
            # Get directory contents
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    entries = os.listdir(path)
                    entries.sort()
                    
                    # Add directories first
                    for entry in entries:
                        entry_path = os.path.join(path, entry)
                        if os.path.isdir(entry_path) and not entry.startswith('.'):
                            items.append({"name": entry, "type": "folder", "path": entry_path})
                    
                    # Add .keys files if we're selecting NSZ keys, .json files if selecting archive JSON, or .nsz files if converting
                    if selected_system_to_add:
                        for entry in entries:
                            entry_path = os.path.join(path, entry)
                            if selected_system_to_add.get("type") == "nsz_keys" and os.path.isfile(entry_path) and entry.lower().endswith('.keys'):
                                items.append({"name": entry, "type": "keys_file", "path": entry_path})
                            elif selected_system_to_add.get("type") == "archive_json" and os.path.isfile(entry_path) and entry.lower().endswith('.json'):
                                items.append({"name": entry, "type": "json_file", "path": entry_path})
                            elif selected_system_to_add.get("type") == "nsz_converter" and os.path.isfile(entry_path) and entry.lower().endswith('.nsz'):
                                items.append({"name": entry, "type": "nsz_file", "path": entry_path})
                    
                except PermissionError:
                    items.append({"name": "Permission denied", "type": "error", "path": path})
            else:
                items.append({"name": "Path not found", "type": "error", "path": path})
            
            folder_browser_items = items
            folder_browser_highlighted = 0
            folder_browser_scroll_offset = 0
            
        except Exception as e:
            log_error(f"Failed to load folder contents for {path}", type(e).__name__, traceback.format_exc())
            folder_browser_items = [{"name": "Error loading folder", "type": "error", "path": path}]
            folder_browser_highlighted = 0
            folder_browser_scroll_offset = 0

    def load_available_systems():
        """Load available systems from list_systems entries"""
        global available_systems, add_systems_highlighted
        
        try:
            # Find entries with list_systems: true
            list_system_entries = [d for d in data if d.get('list_systems', False)]
            if not list_system_entries:
                available_systems = []
                return
            
            # Use the first list_systems entry (assuming there's only one)
            list_entry = list_system_entries[0]
            url = list_entry['url']
            regex_pattern = list_entry.get('regex', '')
            
            if not regex_pattern:
                log_error("No regex pattern found in list_systems entry")
                available_systems = []
                return
            
            # Prepare request headers and cookies for authentication
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            cookies = {}
            
            # Check if authentication is configured for this system
            if 'auth' in list_entry:
                auth_config = list_entry['auth']
                if auth_config.get('cookies', False) and 'token' in auth_config:
                    # Use cookie-based authentication
                    cookie_name = auth_config.get('cookie_name', 'auth_token')
                    cookies[cookie_name] = auth_config['token']
                elif 'token' in auth_config:
                    # Use header-based authentication (Bearer token)
                    headers['Authorization'] = f"Bearer {auth_config['token']}"
            
            response = requests.get(url, timeout=10, headers=headers, cookies=cookies)
            response.raise_for_status()
            html_content = response.text
            
            # Extract systems using regex
            systems = []
            matches = re.finditer(regex_pattern, html_content)
            
            for match in matches:
                try:
                    # Extract href, title, and other data from named groups
                    href = match.group('href') if 'href' in match.groupdict() else ''
                    title = match.group('title') if 'title' in match.groupdict() else ''
                    text = match.group('text') if 'text' in match.groupdict() else ''
                    size = match.group('size') if 'size' in match.groupdict() else ''
                    
                    # Use title as name, fallback to text
                    name = title if title else text
                    if name and href:
                        # Basic cleanup - just remove trailing slash and whitespace
                        name = name.strip().rstrip('/')
                        
                        # Skip if name is empty after cleaning or is navigation element
                        if not name or name in ['..', '.', 'Parent Directory']:
                            continue
                        
                        # Construct full URL
                        full_url = urljoin(url, href)
                        systems.append({
                            'name': name,
                            'href': href,
                            'url': full_url,
                            'size': size.strip() if size else ''
                        })
                except Exception as e:
                    log_error(f"Error processing regex match: {match.groups()}", type(e).__name__, traceback.format_exc())
                    continue
            
            available_systems = systems
            add_systems_highlighted = 0
            
        except Exception as e:
            log_error("Failed to load available systems", type(e).__name__, traceback.format_exc())
            available_systems = []

    def load_added_systems():
        """Load added systems from added_systems.json file"""
        try:
            if os.path.exists(ADDED_SYSTEMS_FILE):
                with open(ADDED_SYSTEMS_FILE, 'r') as f:
                    return json.load(f)
            else:
                # Create empty file
                save_added_systems([])
                return []
        except Exception as e:
            log_error("Failed to load added systems", type(e).__name__, traceback.format_exc())
            return []

    def save_added_systems(added_systems_list):
        """Save added systems to added_systems.json file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(ADDED_SYSTEMS_FILE), exist_ok=True)
            
            with open(ADDED_SYSTEMS_FILE, 'w') as f:
                json.dump(added_systems_list, f, indent=2)
        except Exception as e:
            log_error("Failed to save added systems", type(e).__name__, traceback.format_exc())

    def add_system_to_added_systems(system_name, rom_folder, system_url):
        """Add a new system to the added_systems.json file"""
        try:
            added_systems = load_added_systems()
            
            # Check if system already exists
            for system in added_systems:
                if system.get('name') == system_name:
                    log_error(f"System {system_name} already exists in added systems")
                    return False
            
            # Add new system
            new_system = {
                'name': system_name,
                'roms_folder': rom_folder,
                'url': system_url,
                'file_format': ['.zip', '.7z', '.rar'],  # Default formats
                'should_unzip': True,
                'should_filter_usa': False
            }
            
            added_systems.append(new_system)
            save_added_systems(added_systems)
            
            # Reload the main data to include the new system
            global data
            data = load_main_systems_data()
            
            return True
            
        except Exception as e:
            log_error(f"Failed to add system {system_name}", type(e).__name__, traceback.format_exc())
            return False

    def fix_added_systems_roms_folder():
        """Fix the roms_folder in added_systems.json if it's incorrect"""
        try:
            added_systems = load_added_systems()
            if not added_systems:
                return
            
            fixed = False
            for system in added_systems:
                # If roms_folder is "psx", it means the user selected a folder inside psx
                # We should use the system name as the folder instead
                if system.get('roms_folder') == 'psx':
                    system['roms_folder'] = system.get('name', 'unknown').lower().replace(' ', '_').replace('-', '_')
                    fixed = True
            
            if fixed:
                save_added_systems(added_systems)
                print("Fixed roms_folder in added_systems.json")
                
        except Exception as e:
            log_error("Failed to fix added systems roms_folder", type(e).__name__, traceback.format_exc())

    def load_main_systems_data():
        """Load main systems data including added systems"""
        try:
            # Load main systems (optional) - uses global JSON_FILE which may be archive or default
            main_data = []
            if JSON_FILE and os.path.exists(JSON_FILE):
                with open(JSON_FILE) as f:
                    main_data = json.load(f)
            else:
                print(f"Info: {JSON_FILE} not found, starting with empty main systems")
                main_data = []
            
            # Load added systems
            added_systems = load_added_systems()
            
            # Combine main data with added systems
            combined_data = main_data + added_systems
            
            # Debug: Log the merging process
            print(f"Loaded {len(main_data)} main systems")
            print(f"Loaded {len(added_systems)} added systems")
            print(f"Total systems: {len(combined_data)}")
            
            # Debug: Show system names
            if added_systems:
                print("Added systems:")
                for system in added_systems:
                    print(f"  - {system.get('name', 'Unknown')}")
            
            return combined_data
        except Exception as e:
            log_error("Failed to load main systems data", type(e).__name__, traceback.format_exc())
            return []

    def find_next_letter_index(items, current_index, direction):
        """Find the next item that starts with a different letter"""
        if not items:
            return current_index
        
        # Get display name for current item
        current_item = items[current_index]
        if isinstance(current_item, dict):
            if 'name' in current_item:
                current_name = current_item.get('name', '')
            elif 'filename' in current_item:
                current_name = os.path.splitext(current_item.get('filename', ''))[0]
            else:
                current_name = str(current_item)
        else:
            current_name = str(current_item)
        
        if not current_name:
            return current_index
        
        current_letter = current_name[0].upper()
        if direction > 0:  # Moving right/forward
            for i in range(current_index + 1, len(items)):
                item = items[i]
                if isinstance(item, dict):
                    if 'name' in item:
                        item_name = item.get('name', '')
                    elif 'filename' in item:
                        item_name = os.path.splitext(item.get('filename', ''))[0]
                    else:
                        item_name = str(item)
                else:
                    item_name = str(item)
                if item_name and item_name[0].upper() > current_letter:
                    return i
        else:  # Moving left/backward
            for i in range(current_index - 1, -1, -1):
                item = items[i]
                if isinstance(item, dict):
                    if 'name' in item:
                        item_name = item.get('name', '')
                    elif 'filename' in item:
                        item_name = os.path.splitext(item.get('filename', ''))[0]
                    else:
                        item_name = str(item)
                else:
                    item_name = str(item)
                if item_name and item_name[0].upper() < current_letter:
                    return i
        return current_index
    
    def get_controller_button(action):
        """Get the button number for a specific action based on dynamic controller mapping"""
        if action in controller_mapping:
            button_info = controller_mapping[action]
            print(f"get_controller_button({action}) - button_info: {button_info}")
            return button_info
        else:
            print(f"get_controller_button({action}) - not found in mapping")
            return None
    
    def get_button_name(action):
        """Get the display name for a button action based on dynamic controller mapping"""
        # Fallback to keyboard key names when no controller mapping exists
        keyboard_names = {
            "select": "A (X)",
            "back": "B (T)", 
            "up": "Up arrow",
            "down": "Down arrow",
            "left": "Left arrow", 
            "right": "Right arrow",
            "start": "Start",
            "search": "Select"
        }
        return keyboard_names.get(action.lower(), action.upper())
        
    def input_matches_action(event, action):
        """Check if the pygame event matches the mapped action"""
        button_info = get_controller_button(action)
        if button_info is None:
            return False
            
        if event.type == pygame.JOYBUTTONDOWN:
            # Check regular button press
            return isinstance(button_info, int) and event.button == button_info
        elif event.type == pygame.JOYHATMOTION:
            # Check D-pad/hat input (handle both tuples and lists from JSON)
            if ((isinstance(button_info, tuple) or isinstance(button_info, list)) and 
                len(button_info) >= 3 and button_info[0] == "hat"):
                _, expected_x, expected_y = button_info[0:3]
                return event.value == (expected_x, expected_y)
        
        return False

    def draw_folder_name_input_modal():
        """Draw the folder name input modal overlay"""
        # Get actual screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Semi-transparent background overlay
        overlay = pygame.Surface((screen_width, screen_height))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))
        
        # Modal sizing
        modal_width = min(int(screen_width * 0.8), 500)
        modal_height = min(int(screen_height * 0.6), 400)
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        
        modal_rect = pygame.Rect(modal_x, modal_y, modal_width, modal_height)
        pygame.draw.rect(screen, WHITE, modal_rect)
        pygame.draw.rect(screen, BLACK, modal_rect, 3)
        
        # Title
        title_surf = font.render("Enter Folder Name", True, TEXT_PRIMARY)
        title_x = modal_x + 20
        title_y = modal_y + 20
        screen.blit(title_surf, (title_x, title_y))
        
        # Current folder name display
        name_y = title_y + 50
        name_text = folder_name_input_text if folder_name_input_text else "Enter folder name..."
        name_surf = font.render(name_text, True, TEXT_PRIMARY)
        screen.blit(name_surf, (title_x, name_y))
        
        # Character selection area
        char_y = name_y + 60
        char_title_surf = font.render("Select Character:", True, TEXT_PRIMARY)
        screen.blit(char_title_surf, (title_x, char_y))
        
        # Character grid (A-Z, 0-9)
        chars = list("abcdefghijklmnopqrstuvwxyz0123456789")
        chars_per_row = 13
        char_size = 30
        char_spacing = 5
        
        char_start_x = title_x
        char_start_y = char_y + 40
        
        for i, char in enumerate(chars):
            row = i // chars_per_row
            col = i % chars_per_row
            
            char_x = char_start_x + col * (char_size + char_spacing)
            char_y_pos = char_start_y + row * (char_size + char_spacing)
            
            # Highlight current character
            if i == folder_name_char_index:
                char_rect = pygame.Rect(char_x - 2, char_y_pos - 2, char_size + 4, char_size + 4)
                pygame.draw.rect(screen, GREEN, char_rect)
            
            char_rect = pygame.Rect(char_x, char_y_pos, char_size, char_size)
            pygame.draw.rect(screen, WHITE, char_rect)
            pygame.draw.rect(screen, BLACK, char_rect, 1)
            
            char_surf = font.render(char, True, TEXT_PRIMARY)
            char_text_x = char_x + (char_size - char_surf.get_width()) // 2
            char_text_y = char_y_pos + (char_size - char_surf.get_height()) // 2
            screen.blit(char_surf, (char_text_x, char_text_y))
        
        # Instructions
        instructions = [
            "Use D-pad to select character",
            "Press Select to add character",
            "Press Back to delete character",
            "Press Start to finish",
            "Press any other button to finish"
        ]
        
        inst_y = char_start_y + 120
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            screen.blit(inst_surf, (title_x, inst_y))
            inst_y += 20

    def create_folder_in_browser():
        """Create a new folder in the current folder browser location"""
        global show_folder_name_input, folder_name_input_text, folder_name_cursor_position, folder_name_char_index
        
        # Open the folder name input modal
        show_folder_name_input = True
        folder_name_input_text = ""
        folder_name_cursor_position = 0
        folder_name_char_index = 0

    def show_url_input_modal(context="archive_json"):
        """Show the URL input modal for archive JSON URL or direct download"""
        global show_url_input, url_input_text, url_cursor_position, url_input_context
        
        # Set the context for URL input handling
        url_input_context = context
        
        # Open the URL input modal
        show_url_input = True
        if context == "archive_json":
            url_input_text = settings.get("archive_json_url", "")
        else:  # direct_download
            url_input_text = ""
        url_cursor_position = 0

    def restart_app():
        """Restart the application"""
        try:
            print("Restarting application...")
            pygame.quit()
            # Use os.execv to restart the script
            os.execv(sys.executable, ['python'] + sys.argv)
        except Exception as e:
            log_error("Failed to restart application", type(e).__name__, traceback.format_exc())
            # Fallback: just exit and let user restart manually
            sys.exit(0)

    def create_folder_with_name():
        """Create the folder with the custom name entered by user"""
        global show_folder_name_input, folder_browser_highlighted
        
        try:
            if not folder_name_input_text.strip():
                # Use default name if no name entered
                if selected_system_to_add is not None:
                    default_name = selected_system_to_add['name'].lower().replace(" ", "_").replace("-", "_")
                else:
                    default_name = "new_folder"
                folder_name = default_name
            else:
                folder_name = folder_name_input_text.strip()
            
            # Create the folder
            new_folder_path = os.path.join(folder_browser_current_path, folder_name)
            os.makedirs(new_folder_path, exist_ok=True)
            
            # Reload the folder contents to show the new folder
            load_folder_contents(folder_browser_current_path)
            
            # Highlight the newly created folder
            for i, item in enumerate(folder_browser_items):
                if item["type"] == "folder" and item["name"] == folder_name:
                    folder_browser_highlighted = i
                    break
            
            print(f"Created folder: {new_folder_path}")
            
            # Close the input modal
            show_folder_name_input = False
            
        except Exception as e:
            log_error(f"Failed to create folder in {folder_browser_current_path}", type(e).__name__, traceback.format_exc())
            show_folder_name_input = False

    def draw_search_input_modal():
        """Draw the search input modal overlay with modern styling"""
        global modal_char_rects, modal_back_button_rect
        modal_char_rects.clear()
        
        # Get actual screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Enhanced semi-transparent background overlay with blur effect
        overlay = pygame.Surface((screen_width, screen_height))
        overlay.set_alpha(180)  # More opaque for better contrast
        overlay.fill(BACKGROUND)
        screen.blit(overlay, (0, 0))
        
        # Responsive modal sizing with better proportions
        modal_width = min(max(int(screen_width * 0.85), 400), 700)
        modal_height = min(max(int(screen_height * 0.7), 350), 550)
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        
        # Draw modern modal background with shadow
        shadow_rect = pygame.Rect(modal_x + 4, modal_y + 4, modal_width, modal_height)
        pygame.draw.rect(screen, (0, 0, 0, 60), shadow_rect, border_radius=BORDER_RADIUS)
        
        modal_rect = pygame.Rect(modal_x, modal_y, modal_width, modal_height)
        pygame.draw.rect(screen, SURFACE, modal_rect, border_radius=BORDER_RADIUS)
        pygame.draw.rect(screen, PRIMARY, modal_rect, 3, border_radius=BORDER_RADIUS)
        
        # Enhanced title with styling
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.3))
        title_surf = title_font.render("Search Games", True, TEXT_PRIMARY)
        title_x = modal_x + 25
        title_y = modal_y + 25
        screen.blit(title_surf, (title_x, title_y))
        
        # Draw title underline with gradient effect
        title_width = title_surf.get_width()
        underline_y = title_y + title_surf.get_height() + 8
        pygame.draw.line(screen, PRIMARY, (title_x, underline_y), (title_x + title_width, underline_y), 3)
        
        # Enhanced search text display with modern input field styling
        search_y = title_y + title_surf.get_height() + 30
        search_input_height = 40
        search_input_rect = pygame.Rect(title_x, search_y, modal_width - 50, search_input_height)
        
        # Draw input field background
        pygame.draw.rect(screen, BACKGROUND, search_input_rect, border_radius=8)
        pygame.draw.rect(screen, PRIMARY, search_input_rect, 2, border_radius=8)
        
        # Search text with placeholder styling
        search_text_x = title_x + 15
        search_text_y = search_y + (search_input_height - FONT_SIZE) // 2
        
        if search_input_text:
            search_surf = font.render(search_input_text, True, TEXT_PRIMARY)
            screen.blit(search_surf, (search_text_x, search_text_y))
            
            # Draw blinking cursor
            current_time = pygame.time.get_ticks()
            if (current_time % 1000) < 500:  # Blink every 500ms
                cursor_x = search_text_x + search_surf.get_width() + 2
                cursor_rect = pygame.Rect(cursor_x, search_text_y, 2, FONT_SIZE)
                pygame.draw.rect(screen, PRIMARY, cursor_rect)
        else:
            # Placeholder text
            placeholder_surf = font.render("Enter search term...", True, TEXT_DISABLED)
            screen.blit(placeholder_surf, (search_text_x, search_text_y))
        
        # Character selection area with modern styling
        char_section_y = search_y + search_input_height + 25
        char_title_surf = font.render("Select Character:", True, TEXT_SECONDARY)
        screen.blit(char_title_surf, (title_x, char_section_y))
        
        # Enhanced character grid with modern button styling
        chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
        chars_per_row = 13
        char_size = 32
        char_spacing = 6
        
        char_start_x = title_x
        char_start_y = char_section_y + 35
        
        for i, char in enumerate(chars):
            row = i // chars_per_row
            col = i % chars_per_row
            
            char_x = char_start_x + col * (char_size + char_spacing)
            char_y_pos = char_start_y + row * (char_size + char_spacing)
            
            # Modern button styling
            is_selected = i == search_cursor_position
            is_special = char in ["DEL", "CLEAR", "DONE", " "]
            
            # Button background with different states
            char_rect = pygame.Rect(char_x, char_y_pos, char_size, char_size)
            
            if is_selected:
                # Selected state with glow effect
                glow_rect = pygame.Rect(char_x - 2, char_y_pos - 2, char_size + 4, char_size + 4)
                pygame.draw.rect(screen, PRIMARY_LIGHT, glow_rect, border_radius=8)
                pygame.draw.rect(screen, PRIMARY, char_rect, border_radius=6)
                text_color = BACKGROUND
            elif is_special:
                # Special buttons (DEL, CLEAR, DONE, SPACE) with accent color
                pygame.draw.rect(screen, SURFACE_HOVER, char_rect, border_radius=6)
                pygame.draw.rect(screen, SECONDARY, char_rect, 2, border_radius=6)
                text_color = TEXT_PRIMARY
            else:
                # Regular buttons
                pygame.draw.rect(screen, SURFACE_HOVER, char_rect, border_radius=6)
                pygame.draw.rect(screen, TEXT_DISABLED, char_rect, 1, border_radius=6)
                text_color = TEXT_PRIMARY
            
            # Enhanced character display
            if char == "DEL":
                char_display = "DEL"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            elif char == "CLEAR":
                char_display = "CLR"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            elif char == "DONE":
                char_display = "OK"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.8))
            elif char == " ":
                char_display = "SPC"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            else:
                char_display = char.upper()
                char_font = font
            
            char_surf = char_font.render(char_display, True, text_color)
            char_text_x = char_x + (char_size - char_surf.get_width()) // 2
            char_text_y = char_y_pos + (char_size - char_surf.get_height()) // 2
            screen.blit(char_surf, (char_text_x, char_text_y))
            
            # Store character rectangle for touch/click detection
            modal_char_rects.append((char_rect, i, char))
        
        # Enhanced instructions with modern layout
        instructions_y = char_start_y + (len(chars) // chars_per_row + 1) * (char_size + char_spacing) + 15
        
        # Create instruction cards
        instruction_sections = [
            ("Navigation", ["Use D-pad to select character"]),
            ("Actions", ["Select: Add character", "Back: Delete character", "Start: Finish search"])
        ]
        
        inst_x = title_x
        for section_title, section_instructions in instruction_sections:
            # Section title
            section_surf = font.render(section_title, True, SECONDARY)
            screen.blit(section_surf, (inst_x, instructions_y))
            
            # Section instructions
            inst_y = instructions_y + FONT_SIZE + 5
            for instruction in section_instructions:
                inst_surf = font.render(f"• {instruction}", True, TEXT_DISABLED)
                screen.blit(inst_surf, (inst_x + 10, inst_y))
                inst_y += FONT_SIZE + 3
            
            inst_x += modal_width // 2  # Move to next column
        
        # Add back button for touch/mouse users
        if touchscreen_available or mouse_available:
            back_button_width = 80
            back_button_height = 35
            back_button_x = modal_x + modal_width - back_button_width - 20
            back_button_y = modal_y + modal_height - back_button_height - 20
            modal_back_button_rect = pygame.Rect(back_button_x, back_button_y, back_button_width, back_button_height)
            
            # Draw back button
            pygame.draw.rect(screen, SURFACE_HOVER, modal_back_button_rect, border_radius=8)
            pygame.draw.rect(screen, TEXT_DISABLED, modal_back_button_rect, 2, border_radius=8)
            
            back_text = font.render("Back", True, TEXT_PRIMARY)
            text_x = back_button_x + (back_button_width - back_text.get_width()) // 2
            text_y = back_button_y + (back_button_height - back_text.get_height()) // 2
            screen.blit(back_text, (text_x, text_y))

    def draw_url_input_modal():
        """Draw the URL input modal overlay for archive JSON URL"""
        # Get actual screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Enhanced semi-transparent background overlay
        overlay = pygame.Surface((screen_width, screen_height))
        overlay.set_alpha(180)
        overlay.fill(BACKGROUND)
        screen.blit(overlay, (0, 0))
        
        # Responsive modal sizing
        modal_width = min(max(int(screen_width * 0.85), 400), 700)
        modal_height = min(max(int(screen_height * 0.7), 350), 550)
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        
        # Draw modern modal background with shadow
        shadow_rect = pygame.Rect(modal_x + 4, modal_y + 4, modal_width, modal_height)
        pygame.draw.rect(screen, (0, 0, 0, 60), shadow_rect, border_radius=BORDER_RADIUS)
        
        modal_rect = pygame.Rect(modal_x, modal_y, modal_width, modal_height)
        pygame.draw.rect(screen, SURFACE, modal_rect, border_radius=BORDER_RADIUS)
        pygame.draw.rect(screen, PRIMARY, modal_rect, 3, border_radius=BORDER_RADIUS)
        
        # Enhanced title with styling
        title_font = pygame.font.Font(None, int(FONT_SIZE * 1.3))
        if url_input_context == "direct_download":
            title_text = "Download File from URL"
        else:
            title_text = "Set Archive URL"
        title_surf = title_font.render(title_text, True, TEXT_PRIMARY)
        title_x = modal_x + 25
        title_y = modal_y + 25
        screen.blit(title_surf, (title_x, title_y))
        
        # Draw title underline
        title_width = title_surf.get_width()
        underline_y = title_y + title_surf.get_height() + 8
        pygame.draw.line(screen, PRIMARY, (title_x, underline_y), (title_x + title_width, underline_y), 3)
        
        # URL input field
        url_y = title_y + title_surf.get_height() + 30
        url_input_height = 40
        url_input_rect = pygame.Rect(title_x, url_y, modal_width - 50, url_input_height)
        
        # Draw input field background
        pygame.draw.rect(screen, BACKGROUND, url_input_rect, border_radius=8)
        pygame.draw.rect(screen, PRIMARY, url_input_rect, 2, border_radius=8)
        
        # URL text display
        url_text_x = title_x + 15
        url_text_y = url_y + (url_input_height - FONT_SIZE) // 2
        
        if url_input_text:
            url_surf = font.render(url_input_text, True, TEXT_PRIMARY)
        else:
            # Show placeholder
            url_surf = font.render("http://bit.ly/your-archive-url", True, TEXT_DISABLED)
        
        screen.blit(url_surf, (url_text_x, url_text_y))
        
        # Character selection keyboard (similar to search)
        chars = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-") + [" ", "DEL", "CLEAR", "DONE"]
        char_y_start = url_y + url_input_height + 30
        char_size = 35
        chars_per_row = 13
        
        # Draw character grid
        for i, char in enumerate(chars):
            row = i // chars_per_row
            col = i % chars_per_row
            char_x = title_x + col * (char_size + 8)
            char_y_pos = char_y_start + row * (char_size + 8)
            
            char_rect = pygame.Rect(char_x, char_y_pos, char_size, char_size)
            is_selected = i == url_cursor_position
            is_special = char in ["DEL", "CLEAR", "DONE", " "]
            
            if is_selected:
                # Selected state with glow effect
                glow_rect = pygame.Rect(char_x - 2, char_y_pos - 2, char_size + 4, char_size + 4)
                pygame.draw.rect(screen, PRIMARY_LIGHT, glow_rect, border_radius=8)
                pygame.draw.rect(screen, PRIMARY, char_rect, border_radius=6)
                text_color = BACKGROUND
            elif is_special:
                # Special buttons with accent color
                pygame.draw.rect(screen, SURFACE_HOVER, char_rect, border_radius=6)
                pygame.draw.rect(screen, SECONDARY, char_rect, 2, border_radius=6)
                text_color = TEXT_PRIMARY
            else:
                # Regular buttons
                pygame.draw.rect(screen, SURFACE_HOVER, char_rect, border_radius=6)
                pygame.draw.rect(screen, TEXT_DISABLED, char_rect, 1, border_radius=6)
                text_color = TEXT_PRIMARY
            
            # Character display
            if char == "DEL":
                char_display = "DEL"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            elif char == "CLEAR":
                char_display = "CLR"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            elif char == "DONE":
                char_display = "OK"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.8))
            elif char == " ":
                char_display = "SPC"
                char_font = pygame.font.Font(None, int(FONT_SIZE * 0.7))
            else:
                char_display = char.upper()
                char_font = pygame.font.Font(None, FONT_SIZE)
            
            char_surf = char_font.render(char_display, True, text_color)
            char_text_x = char_x + (char_size - char_surf.get_width()) // 2
            char_text_y = char_y_pos + (char_size - char_surf.get_height()) // 2
            screen.blit(char_surf, (char_text_x, char_text_y))
        
        # Instructions
        inst_y = char_y_start + 4 * (char_size + 8) + 20
        instructions = [
            "Navigate with D-pad, press A to select character",
            "Use DEL to delete, CLEAR to clear all, OK when done"
        ]
        
        for instruction in instructions:
            inst_surf = font.render(instruction, True, TEXT_DISABLED)
            inst_x = modal_x + (modal_width - inst_surf.get_width()) // 2
            screen.blit(inst_surf, (inst_x, inst_y))
            inst_y += 20

    def handle_directional_navigation(event, hat):
        """Unified function to handle directional navigation for both hat and button-based controllers"""
        global movement_occurred, search_cursor_position, folder_name_char_index, folder_browser_highlighted
        global add_systems_highlighted, highlighted, systems_settings_highlighted, system_settings_highlighted, url_cursor_position
        
        movement_occurred = False
        
        if hat[1] != 0 and not show_game_details:  # Up or Down
            if show_search_input:
                # Navigate character selection up/down for search
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if input_matches_action(event, "up"):
                    if search_cursor_position >= chars_per_row:
                        search_cursor_position -= chars_per_row
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if search_cursor_position + chars_per_row < total_chars:
                        search_cursor_position += chars_per_row
                        movement_occurred = True
            elif show_url_input:
                # Navigate character selection up/down for URL input
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if input_matches_action(event, "up"):
                    if url_cursor_position >= chars_per_row:
                        url_cursor_position -= chars_per_row
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if url_cursor_position + chars_per_row < total_chars:
                        url_cursor_position += chars_per_row
                        movement_occurred = True
            elif show_folder_name_input:
                # Navigate character selection up/down
                chars_per_row = 13
                total_chars = 36  # A-Z + 0-9
                if input_matches_action(event, "up"):
                    if folder_name_char_index >= chars_per_row:
                        folder_name_char_index -= chars_per_row
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if folder_name_char_index + chars_per_row < total_chars:
                        folder_name_char_index += chars_per_row
                        movement_occurred = True
            elif show_folder_browser:
                # Folder browser navigation
                if input_matches_action(event, "up"):
                    if folder_browser_items and folder_browser_highlighted > 0:
                        folder_browser_highlighted -= 1
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if folder_browser_items and folder_browser_highlighted < len(folder_browser_items) - 1:
                        folder_browser_highlighted += 1
                        movement_occurred = True
            elif mode == "add_systems":
                # Add systems navigation
                if input_matches_action(event, "up"):
                    if available_systems and add_systems_highlighted > 0:
                        add_systems_highlighted -= 1
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if available_systems and add_systems_highlighted < len(available_systems) - 1:
                        add_systems_highlighted += 1
                        movement_occurred = True
            elif mode == "games" and settings["view_type"] == "grid":
                # Grid navigation: move up/down
                cols = 4
                if input_matches_action(event, "up"):
                    if highlighted >= cols:
                        highlighted -= cols
                        movement_occurred = True
                elif input_matches_action(event, "down"):
                    if highlighted + cols < len(game_list):
                        highlighted += cols
                        movement_occurred = True
            else:
                # Regular navigation for list view and other modes
                if mode == "games":
                    current_game_list = filtered_game_list if search_mode and search_query else game_list
                    max_items = len(current_game_list)
                elif mode == "settings":
                    max_items = len(settings_list)
                elif mode == "utils":
                    max_items = 2  # Download from URL and NSZ to NSP Converter
                elif mode == "credits":
                    max_items = 0  # No navigable items in credits
                elif mode == "add_systems":
                    max_items = len(available_systems)
                elif mode == "systems_settings":
                    configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                    max_items = len(configurable_systems)
                elif mode == "system_settings":
                    max_items = 2  # Hide from menu + Custom ROM folder
                else:  # systems
                    visible_systems = get_visible_systems()
                    max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                
                if max_items > 0:
                    if mode == "add_systems":
                        if input_matches_action(event, "up"):
                            add_systems_highlighted = (add_systems_highlighted - 1) % max_items
                        elif input_matches_action(event, "down"):
                            add_systems_highlighted = (add_systems_highlighted + 1) % max_items
                    elif mode == "systems_settings":
                        if input_matches_action(event, "up"):
                            systems_settings_highlighted = (systems_settings_highlighted - 1) % max_items
                        elif input_matches_action(event, "down"):
                            systems_settings_highlighted = (systems_settings_highlighted + 1) % max_items
                    elif mode == "system_settings":
                        if input_matches_action(event, "up"):
                            system_settings_highlighted = (system_settings_highlighted - 1) % max_items
                        elif input_matches_action(event, "down"):
                            system_settings_highlighted = (system_settings_highlighted + 1) % max_items
                    else:
                        if input_matches_action(event, "up"):
                            highlighted = (highlighted - 1) % max_items
                        elif input_matches_action(event, "down"):
                            highlighted = (highlighted + 1) % max_items
                    movement_occurred = True
        elif hat[0] != 0 and not show_game_details:  # Left or Right
            if show_search_input:
                # Navigate character selection left/right for search
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if input_matches_action(event, "left"):
                    if search_cursor_position % chars_per_row > 0:
                        search_cursor_position -= 1
                        movement_occurred = True
                elif input_matches_action(event, "right"):
                    if search_cursor_position % chars_per_row < chars_per_row - 1 and search_cursor_position < total_chars - 1:
                        search_cursor_position += 1
                        movement_occurred = True
            elif show_url_input:
                # Navigate character selection left/right for URL input
                chars = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-") + [" ", "DEL", "CLEAR", "DONE"]
                chars_per_row = 13
                total_chars = len(chars)
                if input_matches_action(event, "left"):
                    if url_cursor_position % chars_per_row > 0:
                        url_cursor_position -= 1
                        movement_occurred = True
                elif input_matches_action(event, "right"):
                    if url_cursor_position % chars_per_row < chars_per_row - 1 and url_cursor_position < total_chars - 1:
                        url_cursor_position += 1
                        movement_occurred = True
            elif show_folder_name_input:
                # Navigate character selection left/right
                chars_per_row = 13
                total_chars = 36  # A-Z + 0-9
                if input_matches_action(event, "left"):
                    if folder_name_char_index % chars_per_row > 0:
                        folder_name_char_index -= 1
                        movement_occurred = True
                elif input_matches_action(event, "right"):
                    if folder_name_char_index % chars_per_row < chars_per_row - 1 and folder_name_char_index < total_chars - 1:
                        folder_name_char_index += 1
                        movement_occurred = True
            elif mode == "games" and settings["view_type"] == "grid":
                # Grid navigation: move left/right
                cols = 4
                if hat[0] < 0:  # Left
                    if highlighted % cols > 0:
                        highlighted -= 1
                        movement_occurred = True
                else:  # Right
                    if highlighted % cols < cols - 1 and highlighted < len(game_list) - 1:
                        highlighted += 1
                        movement_occurred = True
            else:
                # List navigation: jump to different letter
                items = game_list
                old_highlighted = highlighted
                if hat[0] < 0:  # Left
                    highlighted = find_next_letter_index(items, highlighted, -1)
                else:  # Right
                    highlighted = find_next_letter_index(items, highlighted, 1)
                if highlighted != old_highlighted:
                    movement_occurred = True

#-------------------------------------------------------------------------------------#
#
#                 Pygame Loop        
##-------------------------------------------------------------------------------------#
    settings = load_settings()
    update_log_file_path()    
    update_json_file_path()
    background_image = load_background_image()
    data[:] = load_main_systems_data()
    mapping_exists = load_controller_mapping()
    
    if not mapping_exists or needs_controller_mapping():
        print("Controller mapping needed - will be collected on startup")
        show_controller_mapping = True
    else:
        print("Controller mapping is complete")
        show_controller_mapping = False

    try:
        fix_added_systems_roms_folder()
        data = load_main_systems_data()
    except Exception as e:
        log_error("Failed to load main systems data", type(e).__name__, traceback.format_exc())

    base_work_dir = settings["work_dir"]
    WORK_DIR = os.path.join(base_work_dir, "py_downloads")
    ROMS_DIR = settings["roms_dir"]
    
    try:
        os.makedirs(WORK_DIR, exist_ok=True)
    except (OSError, PermissionError) as e:
        log_error(f"Could not create work directory {WORK_DIR}", type(e).__name__, traceback.format_exc())
        print(f"Warning: Could not create work directory {WORK_DIR}. Downloads may fail.")
    
    try:
        os.makedirs(ROMS_DIR, exist_ok=True)
    except (OSError, PermissionError) as e:
        log_error(f"Could not create ROMs directory {ROMS_DIR}", type(e).__name__, traceback.format_exc())
        print(f"Warning: Could not create ROMs directory {ROMS_DIR}. You may need to create it manually or select a different directory in settings.")

    # Check NSZ availability
    nsz_keys_path = settings.get("nsz_keys_path", "")
    if nsz_keys_path and os.path.isfile(nsz_keys_path):
        NSZ_AVAILABLE = True
        print(f"NSZ functionality enabled: Keys found at {nsz_keys_path}")
    else:
        NSZ_AVAILABLE = False
        if nsz_keys_path:
            print(f"NSZ functionality disabled: Keys file not found at {nsz_keys_path}")
        else:
            print("NSZ functionality disabled: No keys path configured")

    while running:
        try:
            clock.tick(FPS)
            current_time = pygame.time.get_ticks()
            
            # Update continuous navigation state
            update_navigation_state()
            
            # Handle continuous navigation (for held buttons/directions)
            if not show_controller_mapping:
                handle_continuous_navigation()
            
            # Check if we need to collect controller mapping first
            if show_controller_mapping:
                if collect_controller_mapping():
                    show_controller_mapping = False
                    print("Controller mapping completed successfully")
                else:
                    print("Controller mapping cancelled or failed")
                    running = False
                    break
            
            # Update image cache from background threads
            update_image_cache()
            update_hires_image_cache()
                
            if mode == "systems":
                # Get visible systems and add Settings/Add Systems options
                visible_systems = get_visible_systems()
                regular_systems = [d['name'] for d in visible_systems]
                
                # Always show Utils, Settings, and Credits, with systems if available
                systems_with_options = regular_systems + ["Utils", "Settings", "Credits"]
                
                # Enhanced title with system info if a system was previously selected
                title = "Console Utils"
                
                draw_menu(title, systems_with_options, set())
            elif mode == "games":
                if show_search_input:
                    draw_search_input_modal()
                elif show_url_input:
                    draw_url_input_modal()
                elif char_selector_mode:
                    draw_character_selector()
                elif game_list:  # Only draw if we have games
                    # Use filtered list if in search mode
                    current_game_list = filtered_game_list if search_mode and search_query else game_list
                    # Get the current system name for the title
                    system_name = data[selected_system]['name'] if selected_system < len(data) else "Unknown System"
                    base_title = f"{system_name} Games"
                    full_title = base_title + (f" (Search: {search_query})" if search_mode and search_query else "")
                    
                    if settings["view_type"] == "grid":
                        draw_grid_view(full_title, current_game_list, selected_games)
                    else:
                        draw_menu(full_title, current_game_list, selected_games)
                else:
                    draw_loading_message("No games found for this system")
            elif mode == "settings":
                draw_settings_menu()
            elif mode == "utils":
                draw_utils_menu()
            elif mode == "credits":
                draw_credits_menu()
            elif mode == "add_systems":
                draw_add_systems_menu()
            elif mode == "systems_settings":
                draw_systems_settings_menu()
            elif mode == "system_settings":
                draw_system_settings_menu()
            
            # Draw modals if they should be shown
            modal_drawn = False
            if show_search_input:
                draw_search_input_modal()
                modal_drawn = True
            elif show_url_input:
                draw_url_input_modal()
                modal_drawn = True
            elif show_folder_name_input:
                draw_folder_name_input_modal()
                modal_drawn = True
            elif show_game_details and current_game_detail is not None:
                draw_game_details_modal(current_game_detail)
                modal_drawn = True
            elif show_folder_browser:
                draw_folder_browser_modal()
                modal_drawn = True
            
            # Draw touch buttons if available
            if not modal_drawn:
                draw_touch_buttons()
                
            # Flip display once at the end
            if modal_drawn or not (show_game_details or show_folder_browser or show_folder_name_input):
                pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # Handle window resize - update fonts for new screen size
                    new_responsive_font_size = get_responsive_font_size()
                    if new_responsive_font_size != responsive_font_size:
                        responsive_font_size = new_responsive_font_size
                        font = pygame.font.Font(None, responsive_font_size)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Handle mouse clicks
                    if event.button == 1:  # Left mouse button
                        handle_touch_click_event(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    # Handle mouse wheel scrolling
                    handle_scroll_event(event.y)
                elif event.type == pygame.FINGERDOWN:
                    # Handle touchscreen press start
                    if touchscreen_available:
                        # Convert normalized coordinates (0.0-1.0) to pixel coordinates
                        screen_width, screen_height = screen.get_size()
                        x = int(event.x * screen_width)
                        y = int(event.y * screen_height)
                        
                        # Initialize touch tracking
                        touch_start_pos = (x, y)
                        touch_last_pos = (x, y)
                        touch_start_time = pygame.time.get_ticks()
                        is_scrolling = False
                        
                elif event.type == pygame.FINGERUP:
                    # Handle touchscreen release
                    if touchscreen_available and touch_start_pos:
                        # Convert normalized coordinates (0.0-1.0) to pixel coordinates
                        screen_width, screen_height = screen.get_size()
                        x = int(event.x * screen_width)
                        y = int(event.y * screen_height)
                        
                        # Calculate distance moved and time elapsed
                        dx = x - touch_start_pos[0]
                        dy = y - touch_start_pos[1]
                        distance = (dx * dx + dy * dy) ** 0.5
                        time_elapsed = pygame.time.get_ticks() - touch_start_time
                        
                        # If it was a short tap without much movement, treat as click
                        if distance < scroll_threshold and time_elapsed < tap_time_threshold and not is_scrolling:
                            handle_touch_click_event(touch_start_pos)
                        
                        # Reset touch state
                        touch_start_pos = None
                        touch_last_pos = None
                        is_scrolling = False
                        
                elif event.type == pygame.FINGERMOTION:
                    # Handle touch movement (scrolling)
                    if touchscreen_available and touch_start_pos and touch_last_pos:
                        # Convert normalized coordinates (0.0-1.0) to pixel coordinates
                        screen_width, screen_height = screen.get_size()
                        x = int(event.x * screen_width)
                        y = int(event.y * screen_height)
                        
                        # Calculate total distance from start
                        dx_total = x - touch_start_pos[0]
                        dy_total = y - touch_start_pos[1]
                        total_distance = (dx_total * dx_total + dy_total * dy_total) ** 0.5
                        
                        # Calculate motion from last position (for immediate scroll response)
                        dx_motion = x - touch_last_pos[0]
                        dy_motion = y - touch_last_pos[1]
                        
                        # If moved enough from start, mark as scrolling
                        if total_distance > scroll_threshold:
                            is_scrolling = True
                        
                        # If currently scrolling and there's vertical motion, scroll immediately
                        if is_scrolling and abs(dy_motion) > 2:  # Lower threshold for ongoing scroll
                            # Use motion delta for responsive scrolling
                            scroll_amount = -dy_motion * scroll_sensitivity
                            handle_scroll_event(scroll_amount)
                        
                        # Update last position for next motion event
                        touch_last_pos = (x, y)
                elif event.type == pygame.KEYDOWN:
                    # Handle character selector navigation first
                    if show_search_input:
                        chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                        chars_per_row = 13
                        total_chars = len(chars)
                        
                        if event.key == pygame.K_UP:
                            if search_cursor_position >= chars_per_row:
                                search_cursor_position -= chars_per_row
                            continue
                        elif event.key == pygame.K_DOWN:
                            if search_cursor_position + chars_per_row < total_chars:
                                search_cursor_position += chars_per_row
                            continue
                        elif event.key == pygame.K_LEFT:
                            if search_cursor_position % chars_per_row > 0:
                                search_cursor_position -= 1
                            continue
                        elif event.key == pygame.K_RIGHT:
                            if search_cursor_position % chars_per_row < chars_per_row - 1 and search_cursor_position < total_chars - 1:
                                search_cursor_position += 1
                            continue
                    elif char_selector_mode:
                        if event.key == pygame.K_UP:
                            if char_y > 0:
                                char_y -= 1
                            continue
                        elif event.key == pygame.K_DOWN:
                            if char_y < 3:  # 4 rows (0-3)
                                char_y += 1
                            continue
                        elif event.key == pygame.K_LEFT:
                            if char_x > 0:
                                char_x -= 1
                            continue
                        elif event.key == pygame.K_RIGHT:
                            chars = [
                                ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                                ['K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T'],
                                ['U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3'],
                                ['4', '5', '6', '7', '8', '9', ' ', 'DEL', 'CLEAR', 'DONE']
                            ]
                            if char_y < len(chars) and char_x < len(chars[char_y]) - 1:
                                char_x += 1
                            continue
                    
                    # Keyboard controls (same logic as joystick)
                    if event.key == pygame.K_RETURN:  # Enter = Select (Button 4)
                        if show_folder_browser:
                            # Navigate into folder or go back
                            if folder_browser_items and folder_browser_highlighted < len(folder_browser_items):
                                selected_item = folder_browser_items[folder_browser_highlighted]
                                print(f"Selected item: {selected_item['name']} (type: {selected_item['type']})")
                                if selected_item["type"] == "create_folder":
                                    # Create new folder
                                    print("Creating new folder...")
                                    create_folder_in_browser()
                                elif selected_item["type"] in ["folder", "parent"]:
                                    folder_browser_current_path = selected_item["path"]
                                    print(f"Navigating to folder: {folder_browser_current_path}")
                                    load_folder_contents(folder_browser_current_path)
                        elif mode == "systems":
                            # Use helper function for consistent filtering
                            visible_systems = get_visible_systems()
                            systems_count = len(visible_systems)
                            
                            if highlighted == systems_count:  # Utils option
                                mode = "utils"
                                highlighted = 0
                            elif highlighted == systems_count + 1:  # Settings option
                                mode = "settings"
                                highlighted = 0
                                settings_scroll_offset = 0
                            elif highlighted == systems_count + 2:  # Credits option (always at the end)
                                mode = "credits"
                                highlighted = 0
                            elif highlighted < systems_count:
                                # Map visible system index to original data index
                                selected_visible_system = visible_systems[highlighted]
                                selected_system = get_system_index_by_name(selected_visible_system['name'])
                                current_page = 0
                                game_list = list_files(selected_system, current_page)
                                selected_games = set()
                                mode = "games"
                                highlighted = 0
                        elif mode == "games":
                            # Handle game selection with search mode support
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                # Get the actual game from the current list
                                selected_game = current_game_list[highlighted]
                                # Find the original index in game_list for selected_games tracking
                                if search_mode and search_query:
                                    # In search mode, find original index
                                    original_index = next((i for i, game in enumerate(game_list) if game == selected_game), None)
                                    if original_index is not None:
                                        if original_index in selected_games:
                                            selected_games.remove(original_index)
                                        else:
                                            selected_games.add(original_index)
                                else:
                                    # Normal mode, use highlighted directly
                                    if highlighted in selected_games:
                                        selected_games.remove(highlighted)
                                    else:
                                        selected_games.add(highlighted)
                        elif mode == "settings":
                            # Settings are now handled by handle_menu_selection()
                            handle_menu_selection()
                        elif mode == "utils":
                            if highlighted == 0:  # Download from URL
                                # Show URL input modal for direct download
                                show_url_input_modal("direct_download")
                            elif highlighted == 1:  # NSZ to NSP Converter
                                # Start NSZ file browser
                                show_folder_browser = True
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                selected_system_to_add = {"name": "NSZ to NSP Converter", "type": "nsz_converter"}
                                load_folder_contents(folder_browser_current_path)
                                highlighted = 0
                        elif mode == "add_systems":
                            # Handle add systems selection
                            if available_systems and add_systems_highlighted < len(available_systems):
                                selected_system_to_add = available_systems[add_systems_highlighted]
                                # Open folder browser to select ROM folder
                                show_folder_browser = True
                                # Start in ROMs directory
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                load_folder_contents(folder_browser_current_path)
                        elif mode == "systems_settings":
                            # Handle systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if systems_settings_highlighted < len(configurable_systems):
                                selected_system_for_settings = configurable_systems[systems_settings_highlighted]
                                mode = "system_settings"
                                system_settings_highlighted = 0
                                highlighted = 0
                        elif mode == "system_settings":
                            # Handle individual system settings
                            if system_settings_highlighted == 0:  # Hide from main menu
                                system_name = selected_system_for_settings['name']
                                if "system_settings" not in settings:
                                    settings["system_settings"] = {}
                                if system_name not in settings["system_settings"]:
                                    settings["system_settings"][system_name] = {}
                                
                                current_hidden = settings["system_settings"][system_name].get('hidden', False)
                                settings["system_settings"][system_name]['hidden'] = not current_hidden
                                save_settings(settings)
                            elif system_settings_highlighted == 1:  # Custom ROM folder
                                # Open folder browser for custom ROM folder
                                show_folder_browser = True
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                load_folder_contents(folder_browser_current_path)
                                # Set flag to indicate we're selecting custom ROM folder
                                selected_system_to_add = {"name": f"Custom folder for {selected_system_for_settings['name']}", "type": "custom_rom_folder"}
                        elif mode == "games":
                            # Handle game selection with search mode support
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                # Get the actual game from the current list
                                selected_game = current_game_list[highlighted]
                                # Find the original index in game_list for selected_games tracking
                                if search_mode and search_query:
                                    # In search mode, find original index
                                    original_index = next((i for i, game in enumerate(game_list) if game == selected_game), None)
                                    if original_index is not None:
                                        if original_index in selected_games:
                                            selected_games.remove(original_index)
                                        else:
                                            selected_games.add(original_index)
                                else:
                                    # Normal mode, use highlighted directly
                                    if highlighted in selected_games:
                                        selected_games.remove(highlighted)
                                    else:
                                        selected_games.add(highlighted)
                    elif event.key == pygame.K_y:  # Y key = Detail view / Select folder
                        if show_folder_browser:
                            if selected_system_to_add is not None:
                                if selected_system_to_add.get("type") == "work_dir":
                                    # Set work directory
                                    settings["work_dir"] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                elif selected_system_to_add.get("type") == "nsz_keys":
                                    # Set NSZ keys path (for folder selection, not file)
                                    settings["nsz_keys_path"] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                    draw_loading_message("NSZ SELECTED. Restarting...")
                                    pygame.time.wait(2000)
                                    restart_app()
                                elif selected_system_to_add.get("type") == "custom_rom_folder":
                                    # Set custom ROM folder for the selected system
                                    system_name = selected_system_for_settings['name']
                                    if "system_settings" not in settings:
                                        settings["system_settings"] = {}
                                    if system_name not in settings["system_settings"]:
                                        settings["system_settings"][system_name] = {}
                                    
                                    settings["system_settings"][system_name]['custom_folder'] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                    draw_loading_message(f"Custom ROM folder set for {system_name}!")
                                    pygame.time.wait(1500)
                                else:
                                    # Add system with selected folder
                                    system_name = selected_system_to_add['name']
                                    # Calculate relative path from ROMs directory
                                    roms_dir = settings.get("roms_dir", "/userdata/roms")
                                    
                                    # Debug: Print the paths
                                    print(f"Selected folder path: {folder_browser_current_path}")
                                    print(f"ROMs directory: {roms_dir}")
                                    
                                    if folder_browser_current_path.startswith(roms_dir):
                                        rom_folder = os.path.relpath(folder_browser_current_path, roms_dir)
                                        # If the selected path is the ROMs directory itself, use a default folder name
                                        if rom_folder == ".":
                                            rom_folder = system_name.lower().replace(" ", "_").replace("-", "_")
                                    else:
                                        # If not starting with ROMs directory, use the basename of the selected path
                                        rom_folder = os.path.basename(folder_browser_current_path)
                                    
                                    # Ensure we have a valid folder name
                                    if not rom_folder or rom_folder == ".":
                                        rom_folder = system_name.lower().replace(" ", "_").replace("-", "_")
                                    
                                    print(f"Calculated roms_folder: {rom_folder}")
                                    
                                    system_url = selected_system_to_add['url']
                                    
                                    if add_system_to_added_systems(system_name, rom_folder, system_url):
                                        draw_loading_message(f"System '{system_name}' added successfully!")
                                        pygame.time.wait(2000)
                                    else:
                                        draw_loading_message(f"Failed to add system '{system_name}'")
                                        pygame.time.wait(2000)
                                    
                                    # Reset state
                                    selected_system_to_add = None
                                    show_folder_browser = False
                                    mode = "systems"
                                    highlighted = 0
                            else:
                                # Select current folder path for ROMs directory setting
                                settings["roms_dir"] = folder_browser_current_path
                                save_settings(settings)
                                show_folder_browser = False
                                # Restart app to apply ROMs directory change
                                draw_loading_message("ROMs directory changed. Restarting...")
                                pygame.time.wait(2000)
                                restart_app()
                        elif mode == "games" and not show_game_details and game_list:
                            # Show details modal for current game
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                current_game_detail = current_game_list[highlighted]
                                show_game_details = True
                    elif event.key == pygame.K_ESCAPE:  # Escape = Back (Button 3)
                        if show_search_input:
                            # Cancel search input
                            show_search_input = False
                            search_input_text = ""
                        elif char_selector_mode:
                            # Exit character selector and cancel search
                            char_selector_mode = False
                            search_mode = False
                            search_query = ""
                            filtered_game_list = []
                        elif show_folder_browser:
                            # Close folder browser
                            show_folder_browser = False
                        elif show_game_details:
                            # Close details modal
                            show_game_details = False
                            current_game_detail = None
                        elif show_folder_name_input:
                            # Close folder name input modal
                            show_folder_name_input = False
                        elif mode == "games":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "settings":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "utils":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "credits":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "add_systems":
                            mode = "settings"
                            highlighted = 8  # Return to Add Systems option
                        elif mode == "systems_settings":
                            mode = "settings"
                            highlighted = 0
                        elif mode == "system_settings":
                            mode = "systems_settings"
                            highlighted = systems_settings_highlighted
                    elif event.key == pygame.K_s:  # S key = Search
                        if mode == "games" and game_list and not char_selector_mode and not show_search_input:
                            # Enter search input modal
                            show_search_input = True
                            search_input_text = ""
                            search_cursor_position = 0
                            search_cursor_blink_time = pygame.time.get_ticks()
                    elif event.key == pygame.K_SPACE:  # Space = Start Download (Button 10)
                        if mode == "games" and selected_games:
                            draw_loading_message("Starting download...")
                            download_files(selected_system, selected_games)
                            mode = "systems"
                            highlighted = 0
                        elif show_folder_name_input:
                            # Finish folder name input
                            create_folder_with_name()
                    elif event.key == pygame.K_RETURN:  # Enter = Select
                        if show_search_input:
                            # Handle character selection for search
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                            if search_cursor_position < len(chars):
                                selected_char = chars[search_cursor_position]
                                if selected_char == "DEL":
                                    # Delete last character
                                    if search_input_text:
                                        search_input_text = search_input_text[:-1]
                                elif selected_char == "CLEAR":
                                    # Clear entire search query
                                    search_input_text = ""
                                elif selected_char == "DONE":
                                    # Finish search input
                                    show_search_input = False
                                    search_query = search_input_text
                                    if search_query:
                                        search_mode = True
                                        filtered_game_list = filter_games_by_search(game_list, search_query)
                                        highlighted = 0  # Reset selection to first filtered item
                                    else:
                                        search_mode = False
                                        filtered_game_list = []
                                else:
                                    # Add character to search query
                                    search_input_text += selected_char
                        elif show_url_input:
                            # Handle character selection for URL input
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-") + [" ", "DEL", "CLEAR", "DONE"]
                            if url_cursor_position < len(chars):
                                selected_char = chars[url_cursor_position]
                                if selected_char == "DEL":
                                    # Delete last character
                                    if url_input_text:
                                        url_input_text = url_input_text[:-1]
                                elif selected_char == "CLEAR":
                                    # Clear entire URL
                                    url_input_text = ""
                                elif selected_char == "DONE":
                                    # Finish URL input and save/download
                                    show_url_input = False
                                    url = url_input_text.strip()
                                    if url:
                                        if url_input_context == "archive_json":
                                            settings["archive_json_url"] = url
                                            save_settings(settings)
                                            # Download and update JSON
                                            download_archive_json(url)
                                        elif url_input_context == "direct_download":
                                            # Download file directly to work directory
                                            download_direct_file(url)
                                    else:
                                        if url_input_context == "archive_json":
                                            # Clear the setting if URL is empty
                                            settings["archive_json_url"] = ""
                                            save_settings(settings)
                                else:
                                    # Add character to URL
                                    url_input_text += selected_char
                        elif char_selector_mode:
                            # Handle character selection
                            chars = [
                                ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                                ['K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T'],
                                ['U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3'],
                                ['4', '5', '6', '7', '8', '9', ' ', 'DEL', 'CLEAR', 'DONE']
                            ]
                            if char_y < len(chars) and char_x < len(chars[char_y]):
                                selected_char = chars[char_y][char_x]
                                if selected_char == 'DEL':
                                    # Delete last character
                                    if search_query:
                                        search_query = search_query[:-1]
                                elif selected_char == 'CLEAR':
                                    # Clear entire search query
                                    search_query = ""
                                elif selected_char == 'DONE':
                                    # Finish search input
                                    char_selector_mode = False
                                    if search_query:
                                        filtered_game_list = filter_games_by_search(game_list, search_query)
                                        highlighted = 0  # Reset selection to first filtered item
                                    else:
                                        search_mode = False
                                        filtered_game_list = []
                                else:
                                    # Add character to search query
                                    search_query += selected_char
                                
                                # Update filtered list in real-time
                                if search_query:
                                    filtered_game_list = filter_games_by_search(game_list, search_query)
                        elif show_folder_name_input:
                            # Add selected character to folder name
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789")
                            if folder_name_char_index < len(chars):
                                selected_char = chars[folder_name_char_index]
                                folder_name_input_text += selected_char
                        elif show_folder_browser:
                            # Navigate into folder or go back
                            if folder_browser_items and folder_browser_highlighted < len(folder_browser_items):
                                selected_item = folder_browser_items[folder_browser_highlighted]
                                if selected_item["type"] == "create_folder":
                                    # Create new folder
                                    create_folder_in_browser()
                                elif selected_item["type"] in ["folder", "parent"]:
                                    folder_browser_current_path = selected_item["path"]
                                    print(f"Navigating to folder: {folder_browser_current_path}")
                                    load_folder_contents(folder_browser_current_path)
                                elif selected_item["type"] == "keys_file":
                                    # Select this .keys file for NSZ decompression
                                    if selected_system_to_add and selected_system_to_add.get("type") == "nsz_keys":
                                        settings["nsz_keys_path"] = selected_item["path"]
                                        save_settings(settings)
                                        show_folder_browser = False
                                        selected_system_to_add = None
                                        
                                        # Keys configured - NSZ will be imported when needed
                                        draw_loading_message("NSZ keys configured successfully! Restart the App")
                                        pygame.display.flip()
                                        pygame.time.wait(1500)
                                elif selected_item["type"] == "json_file":
                                    # Select this .json file for archive configuration
                                    if selected_system_to_add and selected_system_to_add.get("type") == "archive_json":
                                        # Save the archive JSON path (like NSZ Keys)
                                        settings["archive_json_path"] = selected_item["path"]
                                        save_settings(settings)
                                        
                                        # Update global JSON_FILE path
                                        update_json_file_path()
                                        
                                        # Validate the selected JSON file
                                        try:
                                            # Read and validate JSON file
                                            with open(selected_item["path"], 'r') as f:
                                                json_data = json.load(f)
                                            
                                            if not isinstance(json_data, list):
                                                draw_loading_message("Error: Invalid JSON format (must be array)")
                                                pygame.time.wait(2000)
                                            else:
                                                # Reload data from new JSON file (now uses updated JSON_FILE)
                                                data[:] = load_main_systems_data()
                                                
                                                draw_loading_message("Archive JSON updated successfully!")
                                                pygame.time.wait(1000)
                                        except Exception as e:
                                            draw_loading_message(f"Error loading JSON file: {str(e)}")
                                            pygame.time.wait(2000)
                                        
                                        show_folder_browser = False
                                        selected_system_to_add = None
                                elif selected_item["type"] == "nsz_file":
                                    # Convert this .nsz file to .nsp
                                    if selected_system_to_add and selected_system_to_add.get("type") == "nsz_converter":
                                        convert_nsz_to_nsp(selected_item["path"])
                                        show_folder_browser = False
                                        selected_system_to_add = None
                        elif mode == "add_systems":
                            # Add systems navigation
                            if available_systems and add_systems_highlighted > 0:
                                add_systems_highlighted -= 1
                        elif mode == "systems_settings":
                            # Systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if configurable_systems and systems_settings_highlighted > 0:
                                systems_settings_highlighted -= 1
                        elif mode == "system_settings":
                            # Individual system settings navigation
                            if system_settings_highlighted > 0:
                                system_settings_highlighted -= 1
                        elif mode == "games" and settings["view_type"] == "grid":
                            # Grid navigation: move up
                            cols = 4
                            if highlighted >= cols:
                                highlighted -= cols
                        else:
                            # Regular navigation for list view and other modes
                            if mode == "games":
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                max_items = len(current_game_list)
                            elif mode == "settings":
                                max_items = len(settings_list)
                            elif mode == "add_systems":
                                max_items = len(available_systems)
                            elif mode == "systems_settings":
                                configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                                max_items = len(configurable_systems)
                            elif mode == "system_settings":
                                max_items = 2  # Hide from menu + Custom ROM folder
                            else:  # systems
                                visible_systems = get_visible_systems()
                                max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                            
                            if max_items > 0:
                                if mode == "add_systems":
                                    add_systems_highlighted = (add_systems_highlighted - 1) % max_items
                                elif mode == "systems_settings":
                                    systems_settings_highlighted = (systems_settings_highlighted - 1) % max_items
                                elif mode == "system_settings":
                                    system_settings_highlighted = (system_settings_highlighted - 1) % max_items
                                else:
                                    highlighted = (highlighted - 1) % max_items
                    elif event.key == pygame.K_DOWN and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection down
                            chars_per_row = 13
                            total_chars = 36  # A-Z + 0-9
                            if folder_name_char_index + chars_per_row < total_chars:
                                folder_name_char_index += chars_per_row
                        elif show_folder_browser:
                            # Folder browser navigation
                            if folder_browser_items and folder_browser_highlighted < len(folder_browser_items) - 1:
                                folder_browser_highlighted += 1
                        elif mode == "add_systems":
                            # Add systems navigation
                            if available_systems and add_systems_highlighted < len(available_systems) - 1:
                                add_systems_highlighted += 1
                        elif mode == "systems_settings":
                            # Systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if configurable_systems and systems_settings_highlighted < len(configurable_systems) - 1:
                                systems_settings_highlighted += 1
                        elif mode == "system_settings":
                            # Individual system settings navigation
                            if system_settings_highlighted < 1:  # 0 or 1 (max index)
                                system_settings_highlighted += 1
                        elif mode == "games" and settings["view_type"] == "grid":
                            # Grid navigation: move down
                            cols = 4
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted + cols < len(current_game_list):
                                highlighted += cols
                        else:
                            # Regular navigation for list view and other modes
                            if mode == "games":
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                max_items = len(current_game_list)
                            elif mode == "settings":
                                max_items = len(settings_list)
                            elif mode == "add_systems":
                                max_items = len(available_systems)
                            elif mode == "systems_settings":
                                configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                                max_items = len(configurable_systems)
                            elif mode == "system_settings":
                                max_items = 2  # Hide from menu + Custom ROM folder
                            else:  # systems
                                visible_systems = get_visible_systems()
                                max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                            
                            if max_items > 0:
                                if mode == "add_systems":
                                    add_systems_highlighted = (add_systems_highlighted + 1) % max_items
                                else:
                                    highlighted = (highlighted + 1) % max_items
                    elif event.key == pygame.K_LEFT and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection left
                            chars_per_row = 13
                            if folder_name_char_index % chars_per_row > 0:
                                folder_name_char_index -= 1
                        elif mode == "games" and game_list:
                            if settings["view_type"] == "grid":
                                # Grid navigation: move left
                                cols = 4
                                if highlighted % cols > 0:
                                    highlighted -= 1
                            else:
                                # List navigation: jump to different letter
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                highlighted = find_next_letter_index(current_game_list, highlighted, -1)
                    elif event.key == pygame.K_RIGHT and mode == "games" and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection right
                            chars_per_row = 13
                            total_chars = 36  # A-Z + 0-9
                            if folder_name_char_index % chars_per_row < chars_per_row - 1 and folder_name_char_index < total_chars - 1:
                                folder_name_char_index += 1
                        elif game_list:
                            if settings["view_type"] == "grid":
                                # Grid navigation: move right
                                cols = 4
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                if highlighted % cols < cols - 1 and highlighted < len(current_game_list) - 1:
                                    highlighted += 1
                            else:
                                # List navigation: jump to different letter
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                highlighted = find_next_letter_index(current_game_list, highlighted, 1)
                    elif event.key == pygame.K_BACKSPACE:  # Backspace = Delete character
                        if show_search_input:
                            if search_input_text:
                                search_input_text = search_input_text[:-1]
                        elif show_folder_name_input:
                            if folder_name_input_text:
                                folder_name_input_text = folder_name_input_text[:-1]
                    elif event.type == pygame.TEXTINPUT and show_search_input:
                        # Handle text input for search
                        if len(search_input_text) < 50:  # Limit search length
                            search_input_text += event.text
                    elif event.key == pygame.K_UP and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection up
                            chars_per_row = 13
                            if folder_name_char_index >= chars_per_row:
                                folder_name_char_index -= chars_per_row
                        elif show_folder_browser:
                            # Folder browser navigation
                            if folder_browser_items and folder_browser_highlighted > 0:
                                folder_browser_highlighted -= 1
                        elif mode == "add_systems":
                            # Add systems navigation
                            if available_systems and add_systems_highlighted > 0:
                                add_systems_highlighted -= 1
                        elif mode == "systems_settings":
                            # Systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if configurable_systems and systems_settings_highlighted > 0:
                                systems_settings_highlighted -= 1
                        elif mode == "system_settings":
                            # Individual system settings navigation
                            if system_settings_highlighted > 0:
                                system_settings_highlighted -= 1
                        elif mode == "games" and settings["view_type"] == "grid":
                            # Grid navigation: move up
                            cols = 4
                            if highlighted >= cols:
                                highlighted -= cols
                        else:
                            # Regular navigation for list view and other modes
                            if mode == "games":
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                max_items = len(current_game_list)
                            elif mode == "settings":
                                max_items = len(settings_list)
                            elif mode == "add_systems":
                                max_items = len(available_systems)
                            elif mode == "systems_settings":
                                configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                                max_items = len(configurable_systems)
                            elif mode == "system_settings":
                                max_items = 2  # Hide from menu + Custom ROM folder
                            else:  # systems
                                visible_systems = get_visible_systems()
                                max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                            
                            if max_items > 0:
                                if mode == "add_systems":
                                    add_systems_highlighted = (add_systems_highlighted - 1) % max_items
                                elif mode == "systems_settings":
                                    systems_settings_highlighted = (systems_settings_highlighted - 1) % max_items
                                elif mode == "system_settings":
                                    system_settings_highlighted = (system_settings_highlighted - 1) % max_items
                                else:
                                    if input_matches_action(event, "up"):
                                        highlighted = (highlighted - 1) % max_items
                                    elif input_matches_action(event, "down"):
                                        highlighted = (highlighted + 1) % max_items
                                movement_occurred = True
                    elif event.key == pygame.K_DOWN and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection down
                            chars_per_row = 13
                            total_chars = 36  # A-Z + 0-9
                            if folder_name_char_index + chars_per_row < total_chars:
                                folder_name_char_index += chars_per_row
                        elif show_folder_browser:
                            # Folder browser navigation
                            if folder_browser_items and folder_browser_highlighted < len(folder_browser_items) - 1:
                                folder_browser_highlighted += 1
                        elif mode == "add_systems":
                            # Add systems navigation
                            if available_systems and add_systems_highlighted < len(available_systems) - 1:
                                add_systems_highlighted += 1
                        elif mode == "systems_settings":
                            # Systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if configurable_systems and systems_settings_highlighted < len(configurable_systems) - 1:
                                systems_settings_highlighted += 1
                        elif mode == "system_settings":
                            # Individual system settings navigation
                            if system_settings_highlighted < 1:  # 0 or 1 (max index)
                                system_settings_highlighted += 1
                        elif mode == "games" and settings["view_type"] == "grid":
                            # Grid navigation: move down
                            cols = 4
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted + cols < len(current_game_list):
                                highlighted += cols
                        else:
                            # Regular navigation for list view and other modes
                            if mode == "games":
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                max_items = len(current_game_list)
                            elif mode == "settings":
                                max_items = len(settings_list)
                            elif mode == "add_systems":
                                max_items = len(available_systems)
                            elif mode == "systems_settings":
                                configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                                max_items = len(configurable_systems)
                            elif mode == "system_settings":
                                max_items = 2  # Hide from menu + Custom ROM folder
                            else:  # systems
                                visible_systems = get_visible_systems()
                                max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                            
                            if max_items > 0:
                                if mode == "add_systems":
                                    add_systems_highlighted = (add_systems_highlighted + 1) % max_items
                                else:
                                    highlighted = (highlighted + 1) % max_items
                                movement_occurred = True
                    elif event.key == pygame.K_LEFT and mode == "games" and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection left
                            chars_per_row = 13
                            if folder_name_char_index % chars_per_row > 0:
                                folder_name_char_index -= 1
                        elif game_list:
                            if settings["view_type"] == "grid":
                                # Grid navigation: move left
                                cols = 4
                                if highlighted % cols > 0:
                                    highlighted -= 1
                            else:
                                # List navigation: jump to different letter
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                highlighted = find_next_letter_index(current_game_list, highlighted, -1)
                    elif event.key == pygame.K_RIGHT and mode == "games" and not show_game_details:
                        # Skip keyboard navigation if joystick is connected (prevents double input)
                        if joystick is not None:
                            continue
                        if show_folder_name_input:
                            # Navigate character selection right
                            chars_per_row = 13
                            total_chars = 36  # A-Z + 0-9
                            if folder_name_char_index % chars_per_row < chars_per_row - 1 and folder_name_char_index < total_chars - 1:
                                folder_name_char_index += 1
                        elif game_list:
                            if settings["view_type"] == "grid":
                                # Grid navigation: move right
                                cols = 4
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                if highlighted % cols < cols - 1 and highlighted < len(current_game_list) - 1:
                                    highlighted += 1
                            else:
                                # List navigation: jump to different letter
                                current_game_list = filtered_game_list if search_mode and search_query else game_list
                                highlighted = find_next_letter_index(current_game_list, highlighted, 1)
                elif event.type == pygame.JOYBUTTONDOWN:
                    # Debug: Show all button presses
                    print(f"Joystick button pressed: {event.button}")
                    
                    # Handle directional button inputs mapped as D-pad
                    hat = None
                    if input_matches_action(event, "up"):
                        hat = (0, 1)
                    elif input_matches_action(event, "down"):
                        hat = (0, -1)
                    elif input_matches_action(event, "left"):
                        hat = (-1, 0)
                    elif input_matches_action(event, "right"):
                        hat = (1, 0)
                    
                    left_shoulder_button = get_controller_button("left_shoulder")
                    right_shoulder_button = get_controller_button("right_shoulder")
                    
                    # Process as D-pad navigation if we matched a directional input
                    if hat is not None:
                        # Check if continuous navigation is active for this direction
                        direction_held = False
                        if hat[1] > 0 and is_direction_held('up'):
                            direction_held = True
                        elif hat[1] < 0 and is_direction_held('down'):
                            direction_held = True
                        elif hat[0] < 0 and is_direction_held('left'):
                            direction_held = True
                        elif hat[0] > 0 and is_direction_held('right'):
                            direction_held = True
                        
                        # Only process discrete event if continuous navigation isn't active
                        if not direction_held:
                            handle_directional_navigation(event, hat)
                        # Skip regular button processing for directional buttons
                        continue
                    
                    # Controller-aware button mapping
                    select_button = get_controller_button("select")
                    back_button = get_controller_button("back")
                    start_button = get_controller_button("start")
                    detail_button = get_controller_button("detail")
                    left_shoulder_button = get_controller_button("left_shoulder")
                    right_shoulder_button = get_controller_button("right_shoulder")
                    
                    # Process as D-pad navigation if we matched a directional input
                    if hat is not None:
                        movement_occurred = False
                        
                        if hat[1] != 0 and not show_game_details:  # Up or Down
                            if show_folder_name_input:
                                # Navigate character selection up/down
                                chars_per_row = 13
                                total_chars = 36  # A-Z + 0-9
                                if input_matches_action(event, "up"):
                                    if folder_name_char_index >= chars_per_row:
                                        folder_name_char_index -= chars_per_row
                                        movement_occurred = True
                                elif input_matches_action(event, "down"):
                                    if folder_name_char_index + chars_per_row < total_chars:
                                        folder_name_char_index += chars_per_row
                                        movement_occurred = True
                            elif show_folder_browser:
                                # Folder browser navigation
                                if input_matches_action(event, "up"):
                                    if folder_browser_items and folder_browser_highlighted > 0:
                                        folder_browser_highlighted -= 1
                                        movement_occurred = True
                                elif input_matches_action(event, "down"):
                                    if folder_browser_items and folder_browser_highlighted < len(folder_browser_items) - 1:
                                        folder_browser_highlighted += 1
                                        movement_occurred = True
                            elif mode == "add_systems":
                                # Add systems navigation
                                if input_matches_action(event, "up"):
                                    if available_systems and add_systems_highlighted > 0:
                                        add_systems_highlighted -= 1
                                        movement_occurred = True
                                elif input_matches_action(event, "down"):
                                    if available_systems and add_systems_highlighted < len(available_systems) - 1:
                                        add_systems_highlighted += 1
                                        movement_occurred = True
                            elif mode == "games" and settings["view_type"] == "grid":
                                # Grid navigation: move up/down
                                cols = 4
                                if input_matches_action(event, "up"):
                                    if highlighted >= cols:
                                        highlighted -= cols
                                        movement_occurred = True
                                elif input_matches_action(event, "down"):
                                    if highlighted + cols < len(game_list):
                                        highlighted += cols
                                        movement_occurred = True
                            else:
                                # Regular navigation for list view and other modes
                                if mode == "games":
                                    max_items = len(game_list)
                                elif mode == "settings":
                                    max_items = len(settings_list)
                                elif mode == "add_systems":
                                    max_items = len(available_systems)
                                else:  # systems
                                    visible_systems = get_visible_systems()
                                    max_items = len(visible_systems) + 3  # +3 for Utils, Settings, and Credits options
                                
                                if max_items > 0:
                                    if mode == "add_systems":
                                        if input_matches_action(event, "up"):
                                            add_systems_highlighted = (add_systems_highlighted - 1) % max_items
                                        elif input_matches_action(event, "down"):
                                            add_systems_highlighted = (add_systems_highlighted + 1) % max_items
                                    else:
                                        if input_matches_action(event, "up"):
                                            highlighted = (highlighted - 1) % max_items
                                        elif input_matches_action(event, "down"):
                                            highlighted = (highlighted + 1) % max_items
                                    movement_occurred = True
                        elif hat[0] != 0 and not show_game_details:  # Left or Right
                            if show_folder_name_input:
                                # Navigate character selection left/right
                                chars_per_row = 13
                                total_chars = 36  # A-Z + 0-9
                                if hat[0] < 0:  # Left
                                    if folder_name_char_index % chars_per_row > 0:
                                        folder_name_char_index -= 1
                                        movement_occurred = True
                                else:  # Right
                                    if folder_name_char_index % chars_per_row < chars_per_row - 1 and folder_name_char_index < total_chars - 1:
                                        folder_name_char_index += 1
                                        movement_occurred = True
                            elif mode == "games" and settings["view_type"] == "grid":
                                # Grid navigation: move left/right
                                cols = 4
                                if hat[0] < 0:  # Left
                                    if highlighted % cols > 0:
                                        highlighted -= 1
                                        movement_occurred = True
                                else:  # Right
                                    if highlighted % cols < cols - 1 and highlighted < len(game_list) - 1:
                                        highlighted += 1
                                        movement_occurred = True
                            else:
                                # List navigation: jump to different letter
                                items = game_list
                                old_highlighted = highlighted
                                if hat[0] < 0:  # Left
                                    highlighted = find_next_letter_index(items, highlighted, -1)
                                else:  # Right
                                    highlighted = find_next_letter_index(items, highlighted, 1)
                                if highlighted != old_highlighted:
                                    movement_occurred = True
                        
                        # Skip regular button processing for Odin directional buttons
                        continue
                    
                    # Note: Using input_matches_action() for dynamic button mapping
                    
                    if input_matches_action(event, "select"):  # Select
                        if show_search_input:
                            # Handle character selection for search
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789") + [" ", "DEL", "CLEAR", "DONE"]
                            if search_cursor_position < len(chars):
                                selected_char = chars[search_cursor_position]
                                if selected_char == "DEL":
                                    # Delete last character
                                    if search_input_text:
                                        search_input_text = search_input_text[:-1]
                                elif selected_char == "CLEAR":
                                    # Clear entire search query
                                    search_input_text = ""
                                elif selected_char == "DONE":
                                    # Finish search input
                                    show_search_input = False
                                    search_query = search_input_text
                                    if search_query:
                                        search_mode = True
                                        filtered_game_list = filter_games_by_search(game_list, search_query)
                                        highlighted = 0  # Reset selection to first filtered item
                                    else:
                                        search_mode = False
                                        filtered_game_list = []
                                else:
                                    # Add character to search query
                                    search_input_text += selected_char
                        elif show_url_input:
                            # Handle character selection for URL input
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-") + [" ", "DEL", "CLEAR", "DONE"]
                            if url_cursor_position < len(chars):
                                selected_char = chars[url_cursor_position]
                                if selected_char == "DEL":
                                    # Delete last character
                                    if url_input_text:
                                        url_input_text = url_input_text[:-1]
                                elif selected_char == "CLEAR":
                                    # Clear entire URL
                                    url_input_text = ""
                                elif selected_char == "DONE":
                                    # Finish URL input and save/download
                                    show_url_input = False
                                    url = url_input_text.strip()
                                    if url:
                                        if url_input_context == "archive_json":
                                            settings["archive_json_url"] = url
                                            save_settings(settings)
                                            # Download and update JSON
                                            download_archive_json(url)
                                        elif url_input_context == "direct_download":
                                            # Download file directly to work directory
                                            download_direct_file(url)
                                    else:
                                        if url_input_context == "archive_json":
                                            # Clear the setting if URL is empty
                                            settings["archive_json_url"] = ""
                                            save_settings(settings)
                                else:
                                    # Add character to URL
                                    url_input_text += selected_char
                        elif show_folder_name_input:
                            # Add selected character to folder name
                            chars = list("abcdefghijklmnopqrstuvwxyz0123456789")
                            if folder_name_char_index < len(chars):
                                selected_char = chars[folder_name_char_index]
                                folder_name_input_text += selected_char
                        elif show_folder_browser:
                            # Navigate into folder or go back
                            if folder_browser_items and folder_browser_highlighted < len(folder_browser_items):
                                selected_item = folder_browser_items[folder_browser_highlighted]
                                if selected_item["type"] == "create_folder":
                                    # Create new folder
                                    create_folder_in_browser()
                                elif selected_item["type"] in ["folder", "parent"]:
                                    folder_browser_current_path = selected_item["path"]
                                    print(f"Navigating to folder: {folder_browser_current_path}")
                                    load_folder_contents(folder_browser_current_path)
                                elif selected_item["type"] == "keys_file":
                                    # Select this .keys file for NSZ decompression
                                    if selected_system_to_add and selected_system_to_add.get("type") == "nsz_keys":
                                        settings["nsz_keys_path"] = selected_item["path"]
                                        save_settings(settings)
                                        show_folder_browser = False
                                        selected_system_to_add = None
                                        
                                        # Keys configured - NSZ will be imported when needed
                                        draw_loading_message("NSZ keys configured successfully!")
                                        pygame.display.flip()
                                        pygame.time.wait(1500)
                                elif selected_item["type"] == "json_file":
                                    # Select this .json file for archive configuration
                                    if selected_system_to_add and selected_system_to_add.get("type") == "archive_json":
                                        # Save the archive JSON path (like NSZ Keys)
                                        settings["archive_json_path"] = selected_item["path"]
                                        save_settings(settings)
                                        
                                        # Update global JSON_FILE path
                                        update_json_file_path()
                                        
                                        # Validate the selected JSON file
                                        try:
                                            # Read and validate JSON file
                                            with open(selected_item["path"], 'r') as f:
                                                json_data = json.load(f)
                                            
                                            if not isinstance(json_data, list):
                                                draw_loading_message("Error: Invalid JSON format (must be array)")
                                                pygame.time.wait(2000)
                                            else:
                                                # Reload data from new JSON file (now uses updated JSON_FILE)
                                                data[:] = load_main_systems_data()
                                                
                                                draw_loading_message("Archive JSON updated successfully!")
                                                pygame.time.wait(1000)
                                        except Exception as e:
                                            draw_loading_message(f"Error loading JSON file: {str(e)}")
                                            pygame.time.wait(2000)
                                        
                                        show_folder_browser = False
                                        selected_system_to_add = None
                                elif selected_item["type"] == "nsz_file":
                                    # Convert this .nsz file to .nsp
                                    if selected_system_to_add and selected_system_to_add.get("type") == "nsz_converter":
                                        convert_nsz_to_nsp(selected_item["path"])
                                        show_folder_browser = False
                                        selected_system_to_add = None
                        elif mode == "systems":
                            # Use helper function for consistent filtering
                            visible_systems = get_visible_systems()
                            systems_count = len(visible_systems)
                            
                            if highlighted == systems_count:  # Utils option
                                mode = "utils"
                                highlighted = 0
                            elif highlighted == systems_count + 1:  # Settings option
                                mode = "settings"
                                highlighted = 0
                                settings_scroll_offset = 0
                            elif highlighted == systems_count + 2:  # Credits option (always at the end)
                                mode = "credits"
                                highlighted = 0
                            elif highlighted < systems_count:
                                # Map visible system index to original data index
                                selected_visible_system = visible_systems[highlighted]
                                selected_system = get_system_index_by_name(selected_visible_system['name'])
                                current_page = 0
                                game_list = list_files(selected_system, current_page)
                                selected_games = set()
                                mode = "games"
                                highlighted = 0
                        elif mode == "games":
                            # Handle game selection with search mode support
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                # Get the actual game from the current list
                                selected_game = current_game_list[highlighted]
                                # Find the original index in game_list for selected_games tracking
                                if search_mode and search_query:
                                    # In search mode, find original index
                                    original_index = next((i for i, game in enumerate(game_list) if game == selected_game), None)
                                    if original_index is not None:
                                        if original_index in selected_games:
                                            selected_games.remove(original_index)
                                        else:
                                            selected_games.add(original_index)
                                else:
                                    # Normal mode, use highlighted directly
                                    if highlighted in selected_games:
                                        selected_games.remove(highlighted)
                                    else:
                                        selected_games.add(highlighted)
                        elif mode == "settings":
                            # Settings are now handled by handle_menu_selection()
                            handle_menu_selection()
                        elif mode == "utils":
                            if highlighted == 0:  # Download from URL
                                # Show URL input modal for direct download
                                show_url_input_modal("direct_download")
                            elif highlighted == 1:  # NSZ to NSP Converter
                                # Start NSZ file browser
                                show_folder_browser = True
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                selected_system_to_add = {"name": "NSZ to NSP Converter", "type": "nsz_converter"}
                                load_folder_contents(folder_browser_current_path)
                                highlighted = 0
                        elif mode == "add_systems":
                            # Handle add systems selection
                            if available_systems and add_systems_highlighted < len(available_systems):
                                selected_system_to_add = available_systems[add_systems_highlighted]
                                # Open folder browser to select ROM folder
                                show_folder_browser = True
                                # Start in ROMs directory
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                load_folder_contents(folder_browser_current_path)
                        elif mode == "systems_settings":
                            # Handle systems settings navigation
                            configurable_systems = [d for d in data if not d.get('list_systems', False) and d.get('name') != 'Other Systems']
                            if systems_settings_highlighted < len(configurable_systems):
                                selected_system_for_settings = configurable_systems[systems_settings_highlighted]
                                mode = "system_settings"
                                system_settings_highlighted = 0
                                highlighted = 0
                        elif mode == "system_settings":
                            # Handle individual system settings
                            if system_settings_highlighted == 0:  # Hide from main menu
                                system_name = selected_system_for_settings['name']
                                if "system_settings" not in settings:
                                    settings["system_settings"] = {}
                                if system_name not in settings["system_settings"]:
                                    settings["system_settings"][system_name] = {}
                                
                                current_hidden = settings["system_settings"][system_name].get('hidden', False)
                                settings["system_settings"][system_name]['hidden'] = not current_hidden
                                save_settings(settings)
                            elif system_settings_highlighted == 1:  # Custom ROM folder
                                # Open folder browser for custom ROM folder
                                show_folder_browser = True
                                folder_browser_current_path = settings.get("roms_dir", "/userdata/roms")
                                load_folder_contents(folder_browser_current_path)
                                # Set flag to indicate we're selecting custom ROM folder
                                selected_system_to_add = {"name": f"Custom folder for {selected_system_for_settings['name']}", "type": "custom_rom_folder"}
                        elif mode == "games":
                            # Handle game selection with search mode support
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                # Get the actual game from the current list
                                selected_game = current_game_list[highlighted]
                                # Find the original index in game_list for selected_games tracking
                                if search_mode and search_query:
                                    # In search mode, find original index
                                    original_index = next((i for i, game in enumerate(game_list) if game == selected_game), None)
                                    if original_index is not None:
                                        if original_index in selected_games:
                                            selected_games.remove(original_index)
                                        else:
                                            selected_games.add(original_index)
                                else:
                                    # Normal mode, use highlighted directly
                                    if highlighted in selected_games:
                                        selected_games.remove(highlighted)
                                    else:
                                        selected_games.add(highlighted)
                    elif input_matches_action(event, "detail"):  # Detail view / Select folder
                        if show_folder_browser:
                            print(f"Detail button pressed - Current folder: {folder_browser_current_path}")
                            if selected_system_to_add is not None:
                                if selected_system_to_add.get("type") == "work_dir":
                                    # Set work directory
                                    settings["work_dir"] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                elif selected_system_to_add.get("type") == "nsz_keys":
                                    # Set NSZ keys path (for folder selection, not file)
                                    settings["nsz_keys_path"] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                    draw_loading_message("NSZ keys path updated!")
                                    pygame.time.wait(1500)
                                elif selected_system_to_add.get("type") == "custom_rom_folder":
                                    # Set custom ROM folder for the selected system
                                    system_name = selected_system_for_settings['name']
                                    if "system_settings" not in settings:
                                        settings["system_settings"] = {}
                                    if system_name not in settings["system_settings"]:
                                        settings["system_settings"][system_name] = {}
                                    
                                    settings["system_settings"][system_name]['custom_folder'] = folder_browser_current_path
                                    save_settings(settings)
                                    show_folder_browser = False
                                    selected_system_to_add = None
                                    draw_loading_message(f"Custom ROM folder set for {system_name}!")
                                    pygame.time.wait(1500)
                                else:
                                    # Add system with selected folder
                                    system_name = selected_system_to_add['name']
                                    # Calculate relative path from ROMs directory
                                    roms_dir = settings.get("roms_dir", "/userdata/roms")
                                    
                                    # Debug: Print the paths
                                    print(f"Selected folder path: {folder_browser_current_path}")
                                    print(f"ROMs directory: {roms_dir}")
                                    
                                    if folder_browser_current_path.startswith(roms_dir):
                                        rom_folder = os.path.relpath(folder_browser_current_path, roms_dir)
                                        # If the selected path is the ROMs directory itself, use a default folder name
                                        if rom_folder == ".":
                                            rom_folder = system_name.lower().replace(" ", "_").replace("-", "_")
                                    else:
                                        # If not starting with ROMs directory, use the basename of the selected path
                                        rom_folder = os.path.basename(folder_browser_current_path)
                                    
                                    # Ensure we have a valid folder name
                                    if not rom_folder or rom_folder == ".":
                                        rom_folder = system_name.lower().replace(" ", "_").replace("-", "_")
                                    
                                    print(f"Calculated roms_folder: {rom_folder}")
                                    
                                    system_url = selected_system_to_add['url']
                                    
                                    if add_system_to_added_systems(system_name, rom_folder, system_url):
                                        draw_loading_message(f"System '{system_name}' added successfully!")
                                        pygame.time.wait(2000)
                                    else:
                                        draw_loading_message(f"Failed to add system '{system_name}'")
                                        pygame.time.wait(2000)
                                    
                                    # Reset state
                                    selected_system_to_add = None
                                show_folder_browser = False
                                mode = "systems"
                                highlighted = 0
                            else:
                                # Select current folder path for ROMs directory setting
                                settings["roms_dir"] = folder_browser_current_path
                                save_settings(settings)
                                show_folder_browser = False
                                # Restart app to apply ROMs directory change
                                draw_loading_message("ROMs directory changed. Restarting...")
                                pygame.time.wait(2000)
                                restart_app()
                        elif mode == "games" and not show_game_details and game_list:
                            # Show details modal for current game
                            current_game_list = filtered_game_list if search_mode and search_query else game_list
                            if highlighted < len(current_game_list):
                                current_game_detail = current_game_list[highlighted]
                                show_game_details = True
                    elif input_matches_action(event, "back"):  # Back
                        if show_search_input:
                            # Delete last character in search input
                            if search_input_text:
                                search_input_text = search_input_text[:-1]
                        elif show_folder_browser:
                            # Close folder browser
                            show_folder_browser = False
                        elif show_game_details:
                            # Close details modal
                            show_game_details = False
                            current_game_detail = None
                        elif show_folder_name_input:
                            # Close folder name input modal
                            show_folder_name_input = False
                        elif mode == "games":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "settings":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "utils":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "credits":
                            mode = "systems"
                            highlighted = 0
                        elif mode == "add_systems":
                            mode = "settings"
                            highlighted = 8  # Return to Add Systems option
                        elif mode == "systems_settings":
                            mode = "settings"
                            highlighted = 0
                        elif mode == "system_settings":
                            mode = "systems_settings"
                            highlighted = systems_settings_highlighted
                    elif input_matches_action(event, "left_shoulder"):  # Left shoulder - Previous page
                        if mode == "games" and selected_system < len(data) and data[selected_system].get('supports_pagination', False):
                            if current_page > 0:
                                current_page -= 1
                                game_list = list_files(selected_system, current_page)
                                highlighted = 0
                                selected_games = set()
                    elif input_matches_action(event, "right_shoulder"):  # Right shoulder - Next page
                        if mode == "games" and selected_system < len(data) and data[selected_system].get('supports_pagination', False):
                            current_page += 1
                            new_games = list_files(selected_system, current_page)
                            if new_games:  # Only move if there are games on next page
                                game_list = new_games
                                highlighted = 0
                                selected_games = set()
                            else:
                                current_page -= 1  # Revert if no games found
                    elif input_matches_action(event, "start"):  # Start Download
                        if show_search_input:
                            # Finish search input
                            show_search_input = False
                            search_query = search_input_text
                            if search_query:
                                search_mode = True
                                filtered_game_list = filter_games_by_search(game_list, search_query)
                                highlighted = 0  # Reset selection to first filtered item
                            else:
                                search_mode = False
                                filtered_game_list = []
                        elif mode == "games" and selected_games:
                            draw_loading_message("Starting download...")
                            download_files(selected_system, selected_games)
                            mode = "systems"
                            highlighted = 0
                        elif show_folder_name_input:
                            # Finish folder name input
                            create_folder_with_name()
                    elif input_matches_action(event, "search"):  # Search
                        if mode == "games" and game_list and not char_selector_mode and not show_search_input:
                            # Enter search input modal
                            show_search_input = True
                            search_input_text = ""
                            search_cursor_position = 0
                            search_cursor_blink_time = pygame.time.get_ticks()
                elif event.type == pygame.JOYHATMOTION:
                    hat = joystick.get_hat(0)
                    
                    # Only process if D-pad state actually changed
                    if hat == last_dpad_state:
                        continue
                    
                    # Ignore release events (0,0) - only process actual direction presses
                    if hat == (0, 0):
                        last_dpad_state = hat  # Update state but don't process navigation
                        continue
                    
                    # Update last state
                    last_dpad_state = hat
                    
                    # Check if continuous navigation is active for this direction
                    direction_held = False
                    if hat[1] > 0 and is_direction_held('up'):
                        direction_held = True
                    elif hat[1] < 0 and is_direction_held('down'):
                        direction_held = True
                    elif hat[0] < 0 and is_direction_held('left'):
                        direction_held = True
                    elif hat[0] > 0 and is_direction_held('right'):
                        direction_held = True
                    
                    # Only process discrete event if continuous navigation isn't active
                    if not direction_held:
                        handle_directional_navigation(event, hat)
                    
                    # Movement tracking complete


        except Exception as e:
            log_error("Error in main loop", type(e).__name__, traceback.format_exc())

except Exception as e:
    log_error("Fatal error during initialization", type(e).__name__, traceback.format_exc())
finally:
    pygame.quit()
    sys.exit()
