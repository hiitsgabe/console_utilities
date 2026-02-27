"""
State serializer for Web Companion.

Inspects AppState to determine the current screen context and
serializes relevant data as a JSON-friendly dict for the SPA client.
"""

import os
from urllib.parse import urljoin


def _get_game_name(game):
    """Extract display name from a game item (string or dict)."""
    if isinstance(game, dict):
        if game.get("_download_all"):
            return "[ Download All Games ]"
        name = game.get("filename", game.get("name", str(game)))
    else:
        name = str(game)
    # Remove file extension for display
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def _get_game_thumb_url(game, data, state):
    """Get the boxart/thumbnail URL for a game item."""
    # Direct banner_url in the game dict
    if isinstance(game, dict) and game.get("banner_url"):
        return game["banner_url"]
    # Build from system boxarts base URL
    if data and state.selected_system < len(data):
        system = data[state.selected_system]
        boxart_base = system.get("boxarts", "")
        if boxart_base:
            if isinstance(game, dict):
                raw = game.get("filename", game.get("name", ""))
            else:
                raw = str(game)
            base_name = os.path.splitext(raw)[0] if "." in raw else raw
            return urljoin(boxart_base, f"{base_name}.png")
    return None


def serialize_web_state(state, settings=None, data=None):
    """
    Serialize the current app state into a JSON-friendly dict.

    Follows the same modal priority cascade as screen_manager.render().

    Returns a dict with:
        - screen_type: str (text_input, list, file_browser, confirm, loading, form, details)
        - title: str
        - ... screen-type-specific fields
    """

    # --- Modal priority cascade (matches screen_manager.render) ---

    # Loading modal (highest priority)
    if state.loading.show:
        return {
            "screen_type": "loading",
            "title": "Loading",
            "message": state.loading.message,
            "progress": state.loading.progress,
        }

    # Confirm modal
    if state.confirm_modal.show:
        return {
            "screen_type": "confirm",
            "title": state.confirm_modal.title,
            "message": "\n".join(state.confirm_modal.message_lines),
            "buttons": [state.confirm_modal.ok_label, state.confirm_modal.cancel_label],
            "selected": state.confirm_modal.button_index,
        }

    # Search input
    if state.show_search_input:
        return {
            "screen_type": "text_input",
            "title": "Search",
            "text": state.search.input_text,
            "input_type": "search",
            "cursor": state.search.cursor_position,
        }

    # Folder name input (must be checked before folder_browser since both are .show=True)
    if state.folder_name_input.show:
        return {
            "screen_type": "text_input",
            "title": "Folder Name",
            "text": state.folder_name_input.input_text,
            "input_type": "text",
            "cursor": state.folder_name_input.cursor_position,
        }

    # Folder browser
    if state.folder_browser.show:
        entries = []
        for item in state.folder_browser.items:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                entries.append({
                    "name": item.get("name", ""),
                    "is_dir": item_type in ("folder", "parent"),
                    "type": item_type,
                    "size": item.get("size", 0),
                })
            else:
                entries.append({"name": str(item), "is_dir": True, "type": "folder"})
        # Determine selection type label
        sel_type = ""
        if state.folder_browser.selected_system_to_add:
            sel_type = state.folder_browser.selected_system_to_add.get("type", "folder")
        # File types show individual files to pick; folder types pick current dir
        is_file_select = sel_type in (
            "archive_json", "nsz_keys", "we_patcher_rom", "iss_patcher_rom",
            "nhl94_patcher_rom", "nhl94_gen_patcher_rom", "nhl07_patcher_rom",
            "extract_zip", "extract_rar", "extract_7z", "nsz_converter",
        )
        return {
            "screen_type": "file_browser",
            "title": "Select File" if is_file_select else "Select Folder",
            "current_path": state.folder_browser.current_path,
            "entries": entries,
            "highlighted": state.folder_browser.highlighted,
            "show_select_button": not is_file_select,
        }

    # Game details
    if state.game_details.show and state.game_details.current_game:
        game = state.game_details.current_game
        name = _get_game_name(game)
        thumb = _get_game_thumb_url(game, data, state)
        return {
            "screen_type": "details",
            "title": "Game Details",
            "name": name,
            "info": _game_info(game),
            "actions": ["Download"],
            "thumb_url": thumb,
        }

    # URL input
    if state.url_input.show:
        label = "Enter URL" if state.url_input.context == "direct_download" else "Archive JSON URL"
        return {
            "screen_type": "text_input",
            "title": label,
            "text": state.url_input.input_text,
            "input_type": "url",
            "cursor": state.url_input.cursor_position,
        }

    # Internet Archive login
    if state.ia_login.show:
        step = state.ia_login.step
        if step == "email":
            return {
                "screen_type": "text_input",
                "title": "Internet Archive - Email",
                "text": state.ia_login.email,
                "input_type": "email",
                "cursor": state.ia_login.cursor_position,
            }
        elif step == "password":
            return {
                "screen_type": "text_input",
                "title": "Internet Archive - Password",
                "text": state.ia_login.password,
                "input_type": "password",
                "cursor": state.ia_login.cursor_position,
            }
        else:
            return {
                "screen_type": "loading",
                "title": "Internet Archive",
                "message": f"Login: {step}",
                "progress": 0,
            }

    # IA download wizard
    if state.ia_download_wizard.show:
        step = state.ia_download_wizard.step
        if step == "url":
            return {
                "screen_type": "text_input",
                "title": "Internet Archive - Item URL",
                "text": state.ia_download_wizard.url,
                "input_type": "url",
                "cursor": state.ia_download_wizard.cursor_position,
            }
        elif step == "file_select":
            items = []
            for f in state.ia_download_wizard.display_items or state.ia_download_wizard.files_list:
                if isinstance(f, dict):
                    items.append({"name": f.get("name", f.get("filename", "")), "selected": False})
                else:
                    items.append({"name": str(f), "selected": False})
            return {
                "screen_type": "list",
                "title": "Select File to Download",
                "items": items,
                "highlighted": state.ia_download_wizard.selected_file_index,
            }
        elif step == "options":
            wiz = state.ia_download_wizard
            items = [
                {"name": f"Extract after download: {'ON' if wiz.should_extract else 'OFF'}", "selected": False},
            ]
            return {
                "screen_type": "list",
                "title": "Download Options",
                "items": items,
                "highlighted": 0,
                "wizard_action": "ia_download_options",
            }
        elif step == "error":
            return {
                "screen_type": "confirm",
                "title": "Download Error",
                "message": state.ia_download_wizard.error_message or "An error occurred",
                "buttons": ["Retry", ""],
                "selected": 0,
                "wizard_action": "ia_download_error",
            }
        elif step in ("validating", "downloading"):
            msg = "Validating URL..." if step == "validating" else "Downloading..."
            return {
                "screen_type": "loading",
                "title": "Internet Archive",
                "message": msg,
                "progress": 0,
            }
        else:
            return {
                "screen_type": "loading",
                "title": "Internet Archive",
                "message": f"Step: {step}",
                "progress": 0,
            }

    # IA collection wizard
    if state.ia_collection_wizard.show:
        step = state.ia_collection_wizard.step
        if step == "url":
            return {
                "screen_type": "text_input",
                "title": "Collection URL",
                "text": state.ia_collection_wizard.url,
                "input_type": "url",
                "cursor": state.ia_collection_wizard.cursor_position,
            }
        elif step == "name":
            return {
                "screen_type": "text_input",
                "title": "Collection Name",
                "text": state.ia_collection_wizard.collection_name,
                "input_type": "text",
                "cursor": state.ia_collection_wizard.cursor_position,
            }
        elif step == "folder":
            return {
                "screen_type": "text_input",
                "title": "Folder Name",
                "text": state.ia_collection_wizard.folder_name,
                "input_type": "text",
                "cursor": state.ia_collection_wizard.cursor_position,
            }
        elif step == "formats":
            items = []
            for i, fmt in enumerate(state.ia_collection_wizard.available_formats):
                items.append({
                    "name": fmt,
                    "selected": i in state.ia_collection_wizard.selected_formats,
                })
            return {
                "screen_type": "list",
                "title": "Select File Formats",
                "items": items,
                "highlighted": state.ia_collection_wizard.format_highlighted,
                "multi_select": True,
            }
        elif step == "options":
            wiz = state.ia_collection_wizard
            items = [
                {"name": f"Unzip files: {'ON' if wiz.should_unzip else 'OFF'}", "selected": False},
            ]
            if wiz.should_unzip:
                items.append({
                    "name": f"Extract contents only: {'ON' if wiz.extract_contents else 'OFF'}",
                    "selected": False,
                })
            return {
                "screen_type": "list",
                "title": "Collection Options",
                "items": items,
                "highlighted": wiz.options_highlighted,
                "wizard_action": "ia_collection_options",
            }
        elif step == "confirm":
            wiz = state.ia_collection_wizard
            fmts = [wiz.available_formats[i] for i in wiz.selected_formats
                     if i < len(wiz.available_formats)]
            return {
                "screen_type": "confirm",
                "title": "Create Collection",
                "message": (
                    f"Name: {wiz.collection_name}\n"
                    f"Folder: {wiz.folder_name}\n"
                    f"Formats: {', '.join(fmts) if fmts else 'all'}\n"
                    f"Unzip: {'Yes' if wiz.should_unzip else 'No'}"
                ),
                "buttons": ["Create", "Cancel"],
                "selected": 0,
                "wizard_action": "ia_collection_confirm",
            }
        elif step in ("validating", "creating"):
            return {
                "screen_type": "loading",
                "title": "Collection Wizard",
                "message": "Validating..." if step == "validating" else "Creating collection...",
                "progress": 0,
            }
        elif step == "error":
            return {
                "screen_type": "confirm",
                "title": "Collection Error",
                "message": state.ia_collection_wizard.error_message or "An error occurred",
                "buttons": ["Retry", ""],
                "selected": 0,
                "wizard_action": "ia_collection_error",
            }
        else:
            return {
                "screen_type": "loading",
                "title": "Collection Wizard",
                "message": f"Step: {step}",
                "progress": 0,
            }

    # Scraper login
    if state.scraper_login.show:
        step = state.scraper_login.step
        provider = state.scraper_login.provider
        if step == "username":
            return {
                "screen_type": "text_input",
                "title": f"{provider.title()} - Username",
                "text": state.scraper_login.username,
                "input_type": "text",
                "cursor": state.scraper_login.cursor_position,
            }
        elif step == "password":
            return {
                "screen_type": "text_input",
                "title": f"{provider.title()} - Password",
                "text": state.scraper_login.password,
                "input_type": "password",
                "cursor": state.scraper_login.cursor_position,
            }
        elif step == "api_key":
            return {
                "screen_type": "text_input",
                "title": f"{provider.title()} - API Key",
                "text": state.scraper_login.api_key,
                "input_type": "text",
                "cursor": state.scraper_login.cursor_position,
            }
        else:
            return {
                "screen_type": "loading",
                "title": f"{provider.title()} Login",
                "message": f"Step: {step}",
                "progress": 0,
            }

    # Scraper wizard
    if state.scraper_wizard.show:
        return _serialize_scraper_wizard(state.scraper_wizard)

    # Dedupe wizard
    if state.dedupe_wizard.show:
        return _serialize_dedupe_wizard(state.dedupe_wizard)

    # Rename wizard
    if state.rename_wizard.show:
        return _serialize_rename_wizard(state.rename_wizard)

    # Ghost cleaner
    if state.ghost_cleaner_wizard.show:
        return _serialize_ghost_cleaner(state.ghost_cleaner_wizard)

    # Port details
    if state.port_details.show and state.port_details.port:
        port = state.port_details.port
        return {
            "screen_type": "details",
            "title": "Port Details",
            "name": port.get("attr", {}).get("title", ""),
            "info": port.get("attr", {}).get("desc", ""),
            "actions": ["Install"],
        }

    # Patcher modals (league browser, roster preview, patch progress, color picker)
    patcher = state.active_patcher
    if patcher and hasattr(patcher, "active_modal") and patcher.active_modal:
        modal = patcher.active_modal
        if modal == "league_browser":
            search_query = getattr(patcher, "league_search_query", "")
            items = []
            leagues = getattr(patcher, "available_leagues", [])
            query_lower = search_query.lower() if search_query else ""
            for lg in leagues:
                name = lg.name if hasattr(lg, "name") else (lg.get("name", "") if isinstance(lg, dict) else str(lg))
                country = lg.country if hasattr(lg, "country") else (lg.get("country", "") if isinstance(lg, dict) else "")
                if query_lower and query_lower not in name.lower() and query_lower not in country.lower():
                    continue
                label = f"{name} ({country})" if country else name
                items.append({"name": label, "selected": False})
            return {
                "screen_type": "list",
                "title": "Select League",
                "items": items,
                "highlighted": getattr(patcher, "leagues_highlighted", 0),
                "search": search_query,
                "searchable": True,
            }
        elif modal == "roster_preview":
            return _serialize_roster_preview(patcher)
        elif modal == "patch_progress":
            return {
                "screen_type": "loading",
                "title": "Patching ROM",
                "message": getattr(patcher, "patch_status", ""),
                "progress": int(getattr(patcher, "patch_progress", 0) * 100),
            }
        elif modal == "color_picker":
            return _serialize_color_picker(patcher)

    # --- Main screens ---

    if state.mode == "systems":
        # Build dynamic root menu using the same logic as systems_screen
        from ui.screens.systems_screen import _build_root_menu
        labels, _ = _build_root_menu(settings or {})
        menu_items = [{"name": label, "selected": False} for label in labels]
        return {
            "screen_type": "list",
            "title": "Console Utilities",
            "items": menu_items,
            "highlighted": state.highlighted,
        }

    if state.mode == "systems_list":
        items = []
        if data:
            from services.data_loader import get_visible_systems
            visible = get_visible_systems(data, settings or {})
            for sys in visible:
                items.append({"name": sys.get("name", ""), "selected": False})
        return {
            "screen_type": "list",
            "title": "Game Systems",
            "items": items,
            "highlighted": getattr(state, "systems_list_highlighted", 0),
        }

    if state.mode == "games":
        game_list = state.search.filtered_list if state.search.mode else state.game_list
        items = []
        for i, game in enumerate(game_list):
            name = _get_game_name(game)
            thumb = _get_game_thumb_url(game, data, state)
            item = {
                "name": name,
                "selected": i in state.selected_games,
            }
            if thumb:
                item["thumb_url"] = thumb
            items.append(item)
        system_name = ""
        if data and state.selected_system < len(data):
            system_name = data[state.selected_system].get("name", "")
        return {
            "screen_type": "list",
            "title": system_name or "Games",
            "items": items,
            "highlighted": state.highlighted,
            "search": state.search.query if state.search.mode else "",
        }

    if state.mode == "settings":
        from ui.screens.settings_screen import SettingsScreen
        ss = SettingsScreen()
        setting_items, divider_indices = ss._get_settings_items(settings or {}, data)
        items = []
        for i, label in enumerate(setting_items):
            item = {"name": label, "selected": False}
            if i in divider_indices:
                item["is_divider"] = True
            items.append(item)
        return {
            "screen_type": "list",
            "title": "Settings",
            "items": items,
            "highlighted": state.highlighted,
        }

    if state.mode == "utils":
        from ui.screens.utils_screen import UtilsScreen
        utils = UtilsScreen()
        util_items, divider_indices = utils._get_utils_items(settings or {})
        items = []
        for i, label in enumerate(util_items):
            item = {"name": label, "selected": False}
            if i in divider_indices:
                item["is_divider"] = True
            items.append(item)
        return {
            "screen_type": "list",
            "title": "Utilities",
            "items": items,
            "highlighted": state.highlighted,
        }

    if state.mode == "portmaster":
        pm = state.portmaster
        items = []
        for port in pm.filtered_ports:
            name = port.get("attr", {}).get("title", "") if isinstance(port, dict) else str(port)
            items.append({"name": name, "selected": False})
        return {
            "screen_type": "list",
            "title": "PortMaster",
            "items": items,
            "highlighted": pm.highlighted,
            "search": pm.search_query,
        }

    if state.mode == "downloads":
        items = []
        for it in state.download_queue.items:
            game = it.game
            name = _get_game_name(game)
            items.append({
                "name": name,
                "selected": False,
                "status": it.status,
                "progress": it.progress,
            })
        return {
            "screen_type": "list",
            "title": "Downloads",
            "items": items,
            "highlighted": state.download_queue.highlighted,
        }

    # Patcher screens — use actual screen items
    if state.mode in ("we_patcher", "iss_patcher", "nhl94_patcher",
                       "nhl94_gen_patcher", "nhl07_patcher"):
        fields = _build_patcher_fields(state, settings)
        title_map = {
            "we_patcher": "WE2002 Patcher",
            "iss_patcher": "ISS Patcher",
            "nhl94_patcher": "NHL 94 SNES Patcher",
            "nhl94_gen_patcher": "NHL 94 Genesis Patcher",
            "nhl07_patcher": "NHL 07 PSP Patcher",
        }
        return {
            "screen_type": "form",
            "title": title_map.get(state.mode, state.mode),
            "fields": fields,
            "highlighted": state.highlighted,
        }

    if state.mode == "sports_patcher":
        from ui.screens.sports_patcher_screen import SportsPatcherScreen
        sp = SportsPatcherScreen()
        items = [{"name": label, "selected": False} for label, _ in sp.GAMES]
        return {
            "screen_type": "list",
            "title": "Sports Game Updater",
            "items": items,
            "highlighted": state.highlighted,
        }

    if state.mode == "add_systems":
        items = []
        for sys in (state.available_systems or []):
            name = sys.get("name", "") if isinstance(sys, dict) else str(sys)
            items.append({"name": name, "selected": False})
        return {
            "screen_type": "list",
            "title": "Add Systems",
            "items": items if items else [{"name": "No additional systems available", "selected": False}],
            "highlighted": getattr(state, "add_systems_highlighted", 0),
        }

    if state.mode == "scraper_menu":
        from ui.screens.scraper_menu_screen import ScraperMenuScreen
        sm = ScraperMenuScreen()
        menu_items, divider_indices = sm._get_items(settings or {})
        items = []
        for i, label in enumerate(menu_items):
            item = {"name": label, "selected": False}
            if i in divider_indices:
                item["is_divider"] = True
            items.append(item)
        return {
            "screen_type": "list",
            "title": "Scraper",
            "items": items,
            "highlighted": state.highlighted,
        }

    if state.mode == "scraper_downloads":
        items = []
        for it in state.scraper_queue.items:
            status_map = {
                "pending": "Waiting",
                "searching": "Searching...",
                "downloading": "Downloading...",
                "done": "Done",
                "error": "Error",
                "skipped": it.skip_reason or "Skipped",
            }
            items.append({
                "name": it.name,
                "selected": False,
                "status": status_map.get(it.status, it.status),
            })
        return {
            "screen_type": "list",
            "title": "Scraper Downloads",
            "items": items,
            "highlighted": state.scraper_queue.highlighted,
        }

    if state.mode == "systems_settings":
        items = []
        if data:
            for sys in data:
                name = sys.get("name", "")
                sys_name = sys.get("name", "")
                sys_settings = (settings or {}).get("system_settings", {}).get(sys_name, {})
                tags = []
                if sys_settings.get("hidden", False):
                    tags.append("Hidden")
                if sys_settings.get("custom_folder"):
                    tags.append("Custom Folder")
                label = f"{name} [{', '.join(tags)}]" if tags else name
                items.append({"name": label, "selected": False})
        return {
            "screen_type": "list",
            "title": "Games Backup Settings",
            "items": items,
            "highlighted": getattr(state, "systems_settings_highlighted", 0),
        }

    if state.mode == "system_settings":
        sys_idx = getattr(state, "selected_system_for_settings", 0)
        sys_name = ""
        if data and sys_idx < len(data):
            sys_name = data[sys_idx].get("name", "")
        sys_settings = (settings or {}).get("system_settings", {}).get(sys_name, {})
        hidden = sys_settings.get("hidden", False)
        custom = sys_settings.get("custom_folder", "")
        items = [
            {"name": f"Hide System: {'ON' if hidden else 'OFF'}", "selected": False},
            {"name": f"Custom Folder: {custom or 'Default'}", "selected": False},
        ]
        return {
            "screen_type": "list",
            "title": f"{sys_name} Settings",
            "items": items,
            "highlighted": getattr(state, "system_settings_highlighted", 0),
        }

    if state.mode == "credits":
        return {
            "screen_type": "details",
            "title": "Credits",
            "name": "Console Utilities",
            "info": "A download management tool for handheld gaming consoles.",
            "actions": [],
        }

    # Fallback
    return {
        "screen_type": "unknown",
        "title": state.mode,
        "mode": state.mode,
    }


def _game_info(game):
    """Extract display info from a game dict."""
    if not isinstance(game, dict):
        return ""
    parts = []
    if game.get("size"):
        size = game["size"]
        if isinstance(size, (int, float)) and size > 0:
            if size > 1_000_000_000:
                parts.append(f"Size: {size / 1_000_000_000:.1f} GB")
            elif size > 1_000_000:
                parts.append(f"Size: {size / 1_000_000:.1f} MB")
            else:
                parts.append(f"Size: {size / 1_000:.1f} KB")
        else:
            parts.append(f"Size: {size}")
    if game.get("filename"):
        ext = game["filename"].rsplit(".", 1)[-1] if "." in game["filename"] else ""
        if ext:
            parts.append(f"Format: .{ext}")
    return " | ".join(parts)


def _build_patcher_fields(state, settings):
    """Build form fields from the actual patcher screen items."""
    try:
        if state.mode == "we_patcher":
            from ui.screens.we_patcher_screen import we_patcher_screen
            items = we_patcher_screen._get_items(state, settings)
        elif state.mode == "iss_patcher":
            from ui.screens.iss_patcher_screen import iss_patcher_screen
            items = iss_patcher_screen._get_items(state, settings)
        elif state.mode == "nhl94_patcher":
            from ui.screens.nhl94_snes_patcher_screen import nhl94_snes_patcher_screen
            items = nhl94_snes_patcher_screen._get_items(state, settings)
        elif state.mode == "nhl94_gen_patcher":
            from ui.screens.nhl94_genesis_patcher_screen import nhl94_genesis_patcher_screen
            items = nhl94_genesis_patcher_screen._get_items(state, settings)
        elif state.mode == "nhl07_patcher":
            from ui.screens.nhl07_psp_patcher_screen import nhl07_psp_patcher_screen
            items = nhl07_psp_patcher_screen._get_items(state, settings)
        else:
            items = []

        fields = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 2:
                action_name = item[2] if len(item) >= 3 else ""
                field_type = "cycle" if action_name in ("change_season", "change_language") else "action"
                value = item[1]
                # The pygame screen draws season/language manually, so the
                # tuple value is empty.  Resolve actual values here.
                if not value and action_name == "change_season":
                    from datetime import datetime as _dt
                    patcher = state.active_patcher
                    value = str(getattr(patcher, "selected_season", _dt.now().year))
                elif not value and action_name == "change_language":
                    lang_code = (settings or {}).get("we_patcher_language", "en")
                    try:
                        from services.we_patcher.translations.we2002 import LANGUAGES
                        value = LANGUAGES.get(lang_code, "English")
                    except Exception:
                        value = lang_code
                fields.append({
                    "label": item[0],
                    "value": value,
                    "type": field_type,
                    "action": action_name,
                })
            else:
                fields.append({"label": str(item), "value": "", "type": "text"})
        return fields
    except Exception:
        return []


def _serialize_roster_preview(patcher):
    """Serialize roster preview modal state."""
    league_data = getattr(patcher, "league_data", None)
    team_idx = getattr(patcher, "roster_preview_team_index", 0)
    player_idx = getattr(patcher, "roster_preview_player_index", 0)

    if not league_data or not hasattr(league_data, "teams"):
        return {
            "screen_type": "roster_preview",
            "title": "Roster Preview",
            "teams": [],
            "selected_team": team_idx,
            "selected_player": player_idx,
            "players": [],
        }

    teams = []
    for tr in league_data.teams:
        team_name = tr.team.name if hasattr(tr, "team") else str(tr)
        loading = getattr(tr, "loading", False)
        error = getattr(tr, "error", "")
        teams.append({"name": team_name, "loading": loading, "error": error})

    players = []
    if 0 <= team_idx < len(league_data.teams):
        tr = league_data.teams[team_idx]
        for p in tr.players:
            players.append({
                "name": p.name,
                "position": p.position,
                "number": p.number,
            })

    return {
        "screen_type": "roster_preview",
        "title": "Roster Preview",
        "teams": teams,
        "selected_team": team_idx,
        "selected_player": player_idx,
        "players": players,
    }


def _serialize_color_picker(patcher):
    """Serialize color picker modal state."""
    from services.team_color_cache import COLOR_PALETTE

    league_data = getattr(patcher, "league_data", None)
    cp = getattr(patcher, "color_picker", None)
    team_idx = cp.team_index if cp else 0
    color_idx = cp.color_index if cp else 0
    picking = cp.picking if cp else "primary"

    palette = [{"name": name, "hex": hex_val} for name, hex_val in COLOR_PALETTE]

    if not league_data or not hasattr(league_data, "teams"):
        return {
            "screen_type": "color_picker",
            "title": "Set Team Colors",
            "teams": [],
            "selected_team": team_idx,
            "color_index": color_idx,
            "picking": picking,
            "palette": palette,
        }

    teams = []
    for tr in league_data.teams:
        team = tr.team
        teams.append({
            "name": team.name,
            "color": team.color or "",
            "alternate_color": team.alternate_color or "",
        })

    return {
        "screen_type": "color_picker",
        "title": "Set Team Colors",
        "teams": teams,
        "selected_team": team_idx,
        "color_index": color_idx,
        "picking": picking,
        "palette": palette,
    }


def _serialize_dedupe_wizard(wizard):
    """Serialize dedupe wizard state based on current step."""
    step = wizard.step

    if step == "mode_select":
        items = [
            {"name": "Safe Mode (Automatic)", "selected": False},
            {"name": "Manual Mode (90% Match)", "selected": False},
        ]
        return {
            "screen_type": "list",
            "title": "Dedupe - Select Mode",
            "items": items,
            "highlighted": wizard.mode_highlighted,
        }

    if step == "review":
        groups = wizard.duplicate_groups
        if not groups:
            return {
                "screen_type": "confirm",
                "title": "No Duplicates",
                "message": "No duplicate files found.",
                "buttons": ["OK", ""],
                "selected": 0,
            }
        group_idx = wizard.current_group_index
        group = groups[group_idx] if group_idx < len(groups) else []
        items = []
        for i, f in enumerate(group):
            name = f.get("name", os.path.basename(f.get("path", "")))
            size = f.get("size", 0)
            size_str = ""
            if size > 1_000_000:
                size_str = f" ({size / 1_000_000:.1f} MB)"
            elif size > 1_000:
                size_str = f" ({size / 1_000:.1f} KB)"
            if wizard.mode == "safe":
                marker = " [KEEP]" if i == 0 else ""
            else:
                marker = " [KEEP]" if i == wizard.selected_to_keep else ""
            items.append({
                "name": f"{name}{size_str}{marker}",
                "selected": (i == 0) if wizard.mode == "safe" else (i == wizard.selected_to_keep),
            })
        confirmed = len(wizard.confirmed_groups)
        return {
            "screen_type": "list",
            "title": f"Dedupe Review ({group_idx + 1}/{len(groups)}, {confirmed} confirmed)",
            "items": items,
            "highlighted": wizard.selected_to_keep if wizard.mode == "manual" else 0,
            "wizard_action": "dedupe_review",
        }

    if step == "scanning":
        return {
            "screen_type": "loading",
            "title": "Scanning for Duplicates",
            "message": f"Scanned {wizard.files_scanned} / {wizard.total_files} files",
            "progress": int(wizard.scan_progress * 100),
        }

    if step == "processing":
        return {
            "screen_type": "loading",
            "title": "Removing Duplicates",
            "message": f"Removed {wizard.files_removed} files",
            "progress": int(wizard.process_progress * 100),
        }

    if step in ("complete", "no_duplicates"):
        msg = f"Removed {wizard.files_removed} duplicate files" if step == "complete" else "No duplicates found"
        if wizard.space_freed > 0:
            if wizard.space_freed > 1_000_000_000:
                msg += f"\nFreed {wizard.space_freed / 1_000_000_000:.1f} GB"
            elif wizard.space_freed > 1_000_000:
                msg += f"\nFreed {wizard.space_freed / 1_000_000:.1f} MB"
        return {
            "screen_type": "confirm",
            "title": "Dedupe Complete",
            "message": msg,
            "buttons": ["OK", ""],
            "selected": 0,
        }

    if step == "error":
        return {
            "screen_type": "confirm",
            "title": "Dedupe Error",
            "message": wizard.error_message or "An error occurred",
            "buttons": ["OK", ""],
            "selected": 0,
        }

    return {
        "screen_type": "loading",
        "title": "Dedupe Wizard",
        "message": step,
        "progress": int(wizard.scan_progress * 100),
    }


def _serialize_rename_wizard(wizard):
    """Serialize rename wizard state based on current step."""
    step = wizard.step

    if step == "mode_select":
        items = [
            {"name": "Automatic Mode", "selected": False},
            {"name": "Manual Mode", "selected": False},
        ]
        return {
            "screen_type": "list",
            "title": "Clean File Names - Select Mode",
            "items": items,
            "highlighted": wizard.mode_highlighted,
        }

    if step == "review":
        items = []
        for i, item in enumerate(wizard.rename_items):
            old_name = item.get("name", "")
            new_name = item.get("new_name", "")
            selected = item.get("selected", True)
            items.append({
                "name": f"{old_name} -> {new_name}",
                "selected": selected,
            })
        action = "rename_auto" if wizard.mode == "automatic" else "rename_manual"
        return {
            "screen_type": "list",
            "title": f"Rename Review ({len(items)} files)",
            "items": items,
            "highlighted": wizard.current_item_index,
            "wizard_action": action,
        }

    if step == "scanning":
        return {
            "screen_type": "loading",
            "title": "Scanning Files",
            "message": f"Scanned {wizard.files_scanned} / {wizard.total_files} files",
            "progress": int(wizard.scan_progress * 100),
        }

    if step == "processing":
        return {
            "screen_type": "loading",
            "title": "Renaming Files",
            "message": f"Renamed {wizard.files_renamed} files",
            "progress": int(wizard.process_progress * 100),
        }

    if step in ("complete", "no_changes"):
        msg = f"Renamed {wizard.files_renamed} files" if step == "complete" else "No files to rename"
        return {
            "screen_type": "confirm",
            "title": "Rename Complete",
            "message": msg,
            "buttons": ["OK", ""],
            "selected": 0,
        }

    if step == "error":
        return {
            "screen_type": "confirm",
            "title": "Rename Error",
            "message": wizard.error_message or "An error occurred",
            "buttons": ["OK", ""],
            "selected": 0,
        }

    return {
        "screen_type": "loading",
        "title": "Rename Wizard",
        "message": step,
        "progress": int(wizard.scan_progress * 100),
    }


def _serialize_ghost_cleaner(wizard):
    """Serialize ghost cleaner wizard state based on current step."""
    step = wizard.step

    if step == "scanning":
        return {
            "screen_type": "loading",
            "title": "Scanning for Ghost Files",
            "message": f"Scanned {wizard.files_scanned} / {wizard.total_files} files",
            "progress": int(wizard.scan_progress * 100),
        }

    if step == "review":
        items = []
        for f in wizard.ghost_files:
            name = f.get("name", os.path.basename(f.get("path", "")))
            items.append({"name": name, "selected": False})
        return {
            "screen_type": "list",
            "title": f"Ghost Files Found ({len(items)})",
            "items": items,
            "highlighted": 0,
            "wizard_action": "ghost_review",
        }

    if step == "cleaning":
        return {
            "screen_type": "loading",
            "title": "Removing Ghost Files",
            "message": f"Removed {wizard.files_removed} files",
            "progress": int(wizard.clean_progress * 100),
        }

    if step in ("complete", "no_ghosts"):
        msg = f"Removed {wizard.files_removed} ghost files" if step == "complete" else "No ghost files found"
        if wizard.space_freed > 0:
            if wizard.space_freed > 1_000_000_000:
                msg += f"\nFreed {wizard.space_freed / 1_000_000_000:.1f} GB"
            elif wizard.space_freed > 1_000_000:
                msg += f"\nFreed {wizard.space_freed / 1_000_000:.1f} MB"
        return {
            "screen_type": "confirm",
            "title": "Ghost Cleaner Complete",
            "message": msg,
            "buttons": ["OK", ""],
            "selected": 0,
        }

    if step == "error":
        return {
            "screen_type": "confirm",
            "title": "Ghost Cleaner Error",
            "message": wizard.error_message or "An error occurred",
            "buttons": ["OK", ""],
            "selected": 0,
        }

    return {
        "screen_type": "loading",
        "title": "Ghost Cleaner",
        "message": step,
        "progress": int(wizard.scan_progress * 100),
    }


def _serialize_scraper_wizard(wizard):
    """Serialize scraper wizard state based on current step."""
    step = wizard.step

    if step == "rom_select":
        items = []
        for f in wizard.folder_items:
            if isinstance(f, dict):
                item_type = f.get("type", "")
                items.append({
                    "name": f.get("name", ""),
                    "is_dir": item_type in ("folder", "parent"),
                    "type": item_type,
                })
        return {
            "screen_type": "file_browser",
            "title": "Select ROM",
            "current_path": getattr(wizard, "folder_current_path", ""),
            "entries": items,
            "highlighted": wizard.folder_highlighted,
        }

    if step == "folder_select":
        items = []
        for f in wizard.folder_items:
            if isinstance(f, dict):
                item_type = f.get("type", "")
                items.append({
                    "name": f.get("name", ""),
                    "is_dir": item_type in ("folder", "parent"),
                    "type": item_type,
                })
        return {
            "screen_type": "file_browser",
            "title": "Select ROM Folder",
            "current_path": getattr(wizard, "folder_current_path", ""),
            "entries": items,
            "highlighted": wizard.folder_highlighted,
            "show_select_button": True,
        }

    if step == "game_select":
        items = [
            {"name": r.get("name", ""), "selected": i == wizard.selected_game_index}
            for i, r in enumerate(wizard.search_results)
        ]
        return {
            "screen_type": "list",
            "title": "Select Game Match",
            "items": items,
            "highlighted": wizard.selected_game_index,
        }

    if step == "image_select":
        items = []
        for i, img in enumerate(wizard.available_images):
            name = img.get("type", img.get("name", f"Image {i}")) if isinstance(img, dict) else str(img)
            items.append({
                "name": name,
                "selected": i in wizard.selected_images,
            })
        return {
            "screen_type": "list",
            "title": "Select Images",
            "items": items,
            "highlighted": wizard.image_highlighted,
            "multi_select": True,
        }

    if step == "video_select":
        items = [{"name": "No Video", "selected": wizard.selected_video_index == -1}]
        for i, vid in enumerate(wizard.available_videos):
            name = vid.get("type", vid.get("name", f"Video {i}")) if isinstance(vid, dict) else str(vid)
            items.append({
                "name": name,
                "selected": wizard.selected_video_index == i,
            })
        return {
            "screen_type": "list",
            "title": "Select Video",
            "items": items,
            "highlighted": wizard.video_highlighted,
        }

    if step == "rom_list":
        items = []
        for rom in wizard.batch_roms:
            name = rom.get("name", "")
            status = rom.get("status", "pending")
            items.append({
                "name": name,
                "selected": status == "pending",
                "status": status,
            })
        return {
            "screen_type": "list",
            "title": f"ROMs to Scrape ({sum(1 for r in wizard.batch_roms if r.get('status') == 'pending')} selected)",
            "items": items,
            "highlighted": wizard.batch_current_index,
            "multi_select": True,
            "wizard_action": "scraper_rom_list",
        }

    if step == "batch_options":
        items = _build_batch_options(wizard)
        return {
            "screen_type": "list",
            "title": "Batch Scraper Options",
            "items": items,
            "highlighted": wizard.image_highlighted,
            "wizard_action": "scraper_batch_options",
        }

    if step in ("searching", "downloading", "updating_metadata", "batch_scraping"):
        return {
            "screen_type": "loading",
            "title": "Scraper",
            "message": getattr(wizard, "current_download", "") or step,
            "progress": int(wizard.download_progress * 100),
        }

    if step in ("complete", "batch_complete"):
        return {
            "screen_type": "confirm",
            "title": "Scraper Complete",
            "message": "Scraping finished successfully",
            "buttons": ["OK", ""],
            "selected": 0,
        }

    if step == "error":
        return {
            "screen_type": "confirm",
            "title": "Scraper Error",
            "message": getattr(wizard, "error_message", "") or "An error occurred",
            "buttons": ["Retry", ""],
            "selected": 0,
        }

    return {
        "screen_type": "loading",
        "title": "Scraper",
        "message": step,
        "progress": 0,
    }


def _build_batch_options(wizard):
    """Build batch scraper options list."""
    items = []
    auto_select = getattr(wizard, "auto_select", True)
    items.append({"name": f"Auto-select: {'ON' if auto_select else 'OFF'}", "selected": False})
    default_images = getattr(wizard, "default_images", [])
    image_types = ["box-2D", "boxart", "screenshot", "titlescreen", "fanart", "marquee"]
    for img_type in image_types:
        enabled = img_type in default_images
        items.append({"name": f"{img_type}: {'ON' if enabled else 'OFF'}", "selected": False})
    download_video = getattr(wizard, "download_video", False)
    items.append({"name": f"Download Video: {'ON' if download_video else 'OFF'}", "selected": False})
    return items


def _build_settings_items(settings):
    """Build a simplified list of settings items for the web UI."""
    items = []
    toggles = [
        ("Enable Box-art Display", "enable_boxart", True),
        ("USA Games Only", "usa_only", False),
        ("Show Download All", "show_download_all", False),
        ("Enable PortMaster", "portmaster_enabled", False),
        ("Enable Internet Archive", "ia_enabled", False),
        ("Enable Sports Updater", "sports_roster_enabled", False),
        ("Enable Scraper", "scraper_enabled", False),
        ("Web Companion", "web_companion_enabled", False),
    ]
    for label, key, default in toggles:
        val = settings.get(key, default)
        name = f"{label}: {'ON' if val else 'OFF'}"
        # Mark web companion as locked (can't disable from web)
        if key == "web_companion_enabled" and val:
            name += " (locked)"
        items.append({
            "name": name,
            "selected": False,
        })
    return items
