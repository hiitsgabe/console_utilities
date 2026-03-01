"""
Action handler for Web Companion.

Processes actions received from the phone browser and translates them
into state mutations or synthetic pygame events.
"""

import pygame


# Map direction strings to pygame key constants
KEY_MAP = {
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "select": pygame.K_RETURN,
    "back": pygame.K_ESCAPE,
}


def handle_action(state, action_data):
    """
    Process a single action from the web companion.

    Args:
        state: AppState instance
        action_data: dict with "action" key and action-specific fields
    """
    action = action_data.get("action", "")

    if action == "set_text":
        text = action_data.get("text", "")
        _handle_set_text(state, text)

    elif action == "submit_text":
        _handle_submit_text(state)

    elif action == "search":
        # Combined search: set query + submit in one action
        text = action_data.get("text", "")
        _handle_search(state, text)

    elif action == "select_index":
        index = action_data.get("index", 0)
        _handle_select_index(state, index)

    elif action == "select":
        _post_key(pygame.K_RETURN)

    elif action == "back":
        _post_key(pygame.K_ESCAPE)

    elif action == "start":
        _post_key(pygame.K_SPACE)

    elif action == "navigate":
        direction = action_data.get("direction", "")
        key = KEY_MAP.get(direction)
        if key:
            _post_key(key)

    elif action == "browse_into":
        index = action_data.get("index", 0)
        if state.folder_browser.show:
            state.folder_browser.focus_area = "list"
            state.folder_browser.highlighted = index
            _post_key(pygame.K_RETURN)
        elif state.scraper_wizard.show and state.scraper_wizard.step in (
            "rom_select", "folder_select",
        ):
            state.scraper_wizard.folder_highlighted = index
            _post_key(pygame.K_RETURN)

    elif action == "select_folder":
        # Confirm current folder in folder browser
        if state.folder_browser.show and state.folder_browser.selected_system_to_add:
            state.folder_browser.focus_area = "buttons"
            state.folder_browser.button_index = 0  # Select
            _post_key(pygame.K_RETURN)
        elif state.scraper_wizard.show and state.scraper_wizard.step == "folder_select":
            # Trigger Start action to select folder for batch scraping
            _post_key(pygame.K_SPACE)

    elif action == "cycle_field":
        # Cycle a patcher form field left/right (season, language, etc.)
        index = action_data.get("index", 0)
        direction = action_data.get("direction", "right")
        state.highlighted = index
        key = pygame.K_RIGHT if direction == "right" else pygame.K_LEFT
        _post_key(key)

    elif action == "pick_color":
        # Pick a specific color in the color picker
        color_index = action_data.get("color_index", 0)
        patcher = state.active_patcher
        if patcher and hasattr(patcher, "color_picker"):
            patcher.color_picker.color_index = color_index
            _post_key(pygame.K_RETURN)

    elif action == "confirm_button":
        index = action_data.get("index", 0)
        if state.confirm_modal.show:
            state.confirm_modal.button_index = index
            _post_key(pygame.K_RETURN)
        elif index == 0:
            # For wizard confirm/error screens (not the real confirm_modal),
            # button 0 = primary action (OK/Retry/Create) → just press Enter
            _post_key(pygame.K_RETURN)
        else:
            # button 1 = Cancel/Back → press Escape
            _post_key(pygame.K_ESCAPE)


def _post_key(key):
    """Post a synthetic KEYDOWN event, tagged as from web companion."""
    try:
        evt = pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, web_companion=True)
        pygame.event.post(evt)
    except Exception:
        pass


def _handle_set_text(state, text):
    """Set text directly in the active text input field."""
    if state.show_search_input:
        state.search.input_text = text
        state.search.query = text
        state.search.cursor_position = len(text)
    elif state.url_input.show:
        state.url_input.input_text = text
        state.url_input.cursor_position = len(text)
    elif state.folder_name_input.show:
        state.folder_name_input.input_text = text
        state.folder_name_input.cursor_position = len(text)
    elif state.ia_login.show:
        step = state.ia_login.step
        if step == "email":
            state.ia_login.email = text
            state.ia_login.cursor_position = len(text)
        elif step == "password":
            state.ia_login.password = text
            state.ia_login.cursor_position = len(text)
    elif state.ia_download_wizard.show and state.ia_download_wizard.step == "url":
        state.ia_download_wizard.url = text
        state.ia_download_wizard.cursor_position = len(text)
    elif state.ia_collection_wizard.show:
        step = state.ia_collection_wizard.step
        if step == "url":
            state.ia_collection_wizard.url = text
            state.ia_collection_wizard.cursor_position = len(text)
        elif step == "name":
            state.ia_collection_wizard.collection_name = text
            state.ia_collection_wizard.cursor_position = len(text)
        elif step == "folder":
            state.ia_collection_wizard.folder_name = text
            state.ia_collection_wizard.cursor_position = len(text)
    elif state.scraper_login.show:
        step = state.scraper_login.step
        if step == "username":
            state.scraper_login.username = text
            state.scraper_login.cursor_position = len(text)
        elif step == "password":
            state.scraper_login.password = text
            state.scraper_login.cursor_position = len(text)
        elif step == "api_key":
            state.scraper_login.api_key = text
            state.scraper_login.cursor_position = len(text)
    else:
        # Fallback: if we're on games/portmaster, activate search modal
        # so the subsequent submit_text will trigger _apply_search_filter
        if state.mode in ("games", "portmaster"):
            state.show_search_input = True
            state.search.mode = True
            state.search.input_text = text
            state.search.query = text
            state.search.cursor_position = len(text)

    # Patcher league search — set query regardless of on-screen keyboard state
    patcher = state.active_patcher
    if patcher and hasattr(patcher, "active_modal") and patcher.active_modal == "league_browser":
        patcher.league_search_query = text
        patcher.league_search_cursor = len(text)
        patcher.leagues_highlighted = 0


def _handle_search(state, text):
    """Handle combined search action: activate search, set text, submit."""
    # Activate search modal with the text
    state.show_search_input = True
    state.search.mode = True
    state.search.input_text = text
    state.search.query = text
    state.search.cursor_position = len(text)
    # Post Enter to trigger _apply_search_filter via _submit_search_keyboard_input
    _post_key(pygame.K_RETURN)


def _handle_submit_text(state):
    """Submit/confirm the current text input (press Enter)."""
    _post_key(pygame.K_RETURN)


def _handle_select_index(state, index):
    """Set highlighted index and press Enter to select."""
    # Determine which highlight to set based on active context
    # Check modals/wizards first (same priority as _select_item in app.py)
    if state.folder_browser.show:
        state.folder_browser.focus_area = "list"
        state.folder_browser.highlighted = index
    elif state.game_details.show:
        pass  # No list to select from
    elif state.ia_download_wizard.show:
        step = state.ia_download_wizard.step
        if step == "file_select":
            state.ia_download_wizard.selected_file_index = index
    elif state.ia_collection_wizard.show:
        step = state.ia_collection_wizard.step
        if step == "formats":
            state.ia_collection_wizard.format_highlighted = index
        elif step == "options":
            state.ia_collection_wizard.options_highlighted = index
    elif state.scraper_wizard.show:
        step = state.scraper_wizard.step
        if step in ("rom_select", "folder_select"):
            state.scraper_wizard.folder_highlighted = index
        elif step == "game_select":
            state.scraper_wizard.selected_game_index = index
        elif step == "image_select":
            state.scraper_wizard.image_highlighted = index
        elif step == "video_select":
            state.scraper_wizard.video_highlighted = index
        elif step == "rom_list":
            state.scraper_wizard.batch_current_index = index
        elif step == "batch_options":
            state.scraper_wizard.image_highlighted = index
    elif state.dedupe_wizard.show:
        step = state.dedupe_wizard.step
        if step == "mode_select":
            state.dedupe_wizard.mode_highlighted = index
        elif step == "review" and state.dedupe_wizard.mode == "manual":
            state.dedupe_wizard.selected_to_keep = index
    elif state.rename_wizard.show:
        step = state.rename_wizard.step
        if step == "mode_select":
            state.rename_wizard.mode_highlighted = index
        elif step == "review":
            state.rename_wizard.current_item_index = index
    elif state.active_patcher and hasattr(state.active_patcher, "active_modal") and state.active_patcher.active_modal:
        patcher = state.active_patcher
        modal = patcher.active_modal
        if modal == "league_browser":
            patcher.leagues_highlighted = index
        elif modal == "roster_preview":
            patcher.roster_preview_team_index = index
            patcher.roster_preview_player_index = 0
            return  # Don't post K_RETURN — just switch team
        elif modal == "color_picker":
            patcher.color_picker.team_index = index
            return  # Don't post K_RETURN — just switch team
    elif state.mode == "games":
        state.highlighted = index
    elif state.mode == "portmaster":
        state.portmaster.highlighted = index
    elif state.mode == "systems_list":
        state.systems_list_highlighted = index
    elif state.mode == "add_systems":
        state.add_systems_highlighted = index
    elif state.mode == "systems_settings":
        state.systems_settings_highlighted = index
    elif state.mode == "system_settings":
        state.system_settings_highlighted = index
    elif state.mode == "scraper_downloads":
        state.scraper_queue.highlighted = index
    else:
        state.highlighted = index

    _post_key(pygame.K_RETURN)
