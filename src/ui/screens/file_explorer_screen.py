"""
File explorer screen — full-screen file manager with D-pad navigation.
"""

import os
import pygame
from typing import Dict, List, Optional, Set, Tuple, Any

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.organisms.menu_list import MenuList
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from ui.atoms.surface import Surface
from ui.molecules.action_button import ActionButton
from utils.button_hints import get_button_name
from services.file_explorer_service import format_size, get_file_icon
from constants import BEZEL_INSET


class FileExplorerScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.menu_list = MenuList(theme)
        self.text = Text(theme)
        self.surface = Surface(theme)
        self.modal_frame = ModalFrame(theme)
        self.action_button = ActionButton(theme)
        self.char_keyboard = CharKeyboard(theme)

    def render(
        self,
        screen: pygame.Surface,
        state: Any,
        input_mode: str = "keyboard",
    ) -> Dict[str, Any]:
        """Render the file explorer screen. Returns dict of interactive rects."""
        rects: Dict[str, Any] = {}
        fe = state.file_explorer
        w, h = screen.get_size()

        screen.fill(self.theme.background)

        header_rect, back_rect = self.header.render(
            screen, title="File Explorer", show_back=True,
        )
        rects["back"] = back_rect

        inset = BEZEL_INSET

        # Breadcrumb bar
        breadcrumb_y = header_rect.bottom
        breadcrumb_h = 28
        breadcrumb_rect = pygame.Rect(inset, breadcrumb_y, w - inset * 2, breadcrumb_h)
        pygame.draw.rect(screen, self.theme.surface, breadcrumb_rect)

        breadcrumb_text = self._format_breadcrumb(fe.current_path, w)
        font_sm = self.theme.font_size_sm
        self.text.render(
            screen, breadcrumb_text,
            (inset + self.theme.padding_md, breadcrumb_y + (breadcrumb_h - font_sm) // 2),
            color=self.theme.primary, size=font_sm,
        )

        # Footer
        footer_h = 36
        footer_y = h - footer_h - inset
        footer_rect = pygame.Rect(inset, footer_y, w - inset * 2, footer_h)
        pygame.draw.rect(screen, self.theme.surface, footer_rect)
        touch_rects = self._render_footer(screen, footer_rect, fe, input_mode)
        rects.update(touch_rects)

        # File list area
        list_y = breadcrumb_rect.bottom
        list_h = footer_y - list_y
        list_rect = pygame.Rect(inset, list_y, w - inset * 2, list_h)

        if not fe.entries:
            self.text.render(
                screen, "This folder is empty",
                (w // 2, list_y + list_h // 2 - self.theme.font_size_md // 2),
                color=self.theme.text_secondary, size=self.theme.font_size_md,
                align="center",
            )
            rects["item_rects"] = []
            rects["scroll_offset"] = 0
        else:
            item_rects, scroll_offset = self.menu_list.render(
                screen, list_rect, fe.entries, fe.highlighted, fe.selected,
                item_height=44, get_label=self._get_item_label,
                get_secondary=self._get_item_secondary,
                show_checkbox=bool(fe.selected),
            )
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        # Modals (priority order)
        if fe.error_message:
            self._render_error_modal(screen, fe, rects)
        elif fe.delete_modal_open:
            self._render_delete_modal(screen, fe, rects)
        elif fe.extract_modal_open:
            self._render_extract_modal(screen, fe, rects)
        elif fe.input_modal_open:
            self._render_input_modal(screen, fe, input_mode, rects)
        elif fe.viewer_open:
            self._render_viewer(screen, fe, rects)
        elif fe.context_menu_open:
            self._render_context_menu(screen, fe, rects)

        return rects

    def _format_breadcrumb(self, path: str, max_width: int) -> str:
        if not path:
            return "/"
        parts = path.split(os.sep)
        parts = [p for p in parts if p]
        if len(parts) > 4:
            return "/ > ... > " + " > ".join(parts[-3:])
        return "/ > " + " > ".join(parts) if parts else "/"

    def _get_item_label(self, item: Any) -> str:
        if isinstance(item, dict):
            name = item.get("name", "")
            icon = get_file_icon(name, item.get("is_dir", False))
            prefix = {"D": "[DIR] ", "Z": "[ZIP] ", "T": "[TXT] "}.get(icon, "")
            return f"{prefix}{name}"
        return str(getattr(item, "name", item))

    def _get_item_secondary(self, item: Any) -> str:
        if isinstance(item, dict):
            if item.get("is_dir"):
                return "Folder"
            return format_size(item.get("size"))
        return ""

    def _render_footer(self, screen, rect, fe, input_mode):
        rects: Dict[str, Any] = {}
        mid_y = rect.top + rect.height // 2

        if fe.clipboard_paths:
            count = len(fe.clipboard_paths)
            mode_label = "copied" if fe.clipboard_mode == "copy" else "cut"
            left_text = f"{count} file{'s' if count > 1 else ''} {mode_label}"
            left_color = self.theme.primary if fe.clipboard_mode == "copy" else self.theme.warning
        elif fe.selected:
            left_text = f"{len(fe.selected)} selected"
            left_color = self.theme.text_primary
        else:
            left_text = f"{len(fe.entries)} items"
            left_color = self.theme.text_secondary

        font_sm = self.theme.font_size_sm
        text_y = mid_y - font_sm // 2
        self.text.render(
            screen, left_text,
            (rect.left + self.theme.padding_md, text_y),
            color=left_color, size=font_sm,
        )

        if input_mode == "touch":
            rects.update(self._render_touch_buttons(screen, rect, fe))
        else:
            hints = self._get_button_hints(fe, input_mode)
            self.text.render(
                screen, hints,
                (rect.right - self.theme.padding_md, text_y),
                color=self.theme.text_secondary, size=font_sm,
                align="right",
            )
        return rects

    def _render_touch_buttons(self, screen, rect, fe):
        rects: Dict[str, Any] = {}
        btn_h = 28
        btn_y = rect.top + (rect.height - btn_h) // 2
        btn_x = rect.right - self.theme.padding_md
        btn_spacing = 8

        if fe.clipboard_paths:
            buttons = [("Paste", "touch_paste"), ("Back", "touch_back")]
        elif fe.selected:
            buttons = [("Actions", "touch_actions"), ("Deselect", "touch_deselect"), ("Back", "touch_back")]
        else:
            buttons = [("Open", "touch_open"), ("Actions", "touch_actions"), ("Back", "touch_back")]

        for label, key in reversed(buttons):
            btn_w = max(60, len(label) * 9 + 16)
            btn_x -= btn_w
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            self.action_button.render(screen, btn_rect, label)
            rects[key] = btn_rect
            btn_x -= btn_spacing
        return rects

    def _get_button_hints(self, fe, input_mode):
        a = get_button_name("select", input_mode)
        b = get_button_name("back", input_mode)
        x = get_button_name("search", input_mode)
        y = get_button_name("detail", input_mode)
        if fe.clipboard_paths:
            return f"[{x}] Paste  [{b}] Back"
        elif fe.selected:
            return f"[{y}] Actions  [{x}] Toggle  [{b}] Back"
        else:
            return f"[{y}] Actions  [{a}] Open  [{b}] Back"

    def _render_context_menu(self, screen, fe, rects):
        w, h = screen.get_size()
        actions = fe.context_menu_actions
        if not actions:
            return

        menu_w = min(300, w - 40)
        item_h = 40
        menu_h = min(len(actions) * item_h + 20, h - 100)
        menu_x = (w - menu_w) // 2
        menu_y = (h - menu_h) // 2

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        menu_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
        pygame.draw.rect(screen, self.theme.surface, menu_rect, border_radius=8)
        pygame.draw.rect(screen, self.theme.text_secondary, menu_rect, width=1, border_radius=8)

        ctx_item_rects = []
        for i, (action_id, label) in enumerate(actions):
            item_y = menu_y + 10 + i * item_h
            item_rect = pygame.Rect(menu_x + 4, item_y, menu_w - 8, item_h)
            if i == fe.context_menu_highlighted:
                pygame.draw.rect(screen, self.theme.primary, item_rect, border_radius=4)
                text_color = self.theme.background
            else:
                text_color = self.theme.text_primary
            if action_id == "delete":
                text_color = self.theme.background if i == fe.context_menu_highlighted else self.theme.error

            self.text.render(
                screen, label, (menu_x + 20, item_y + (item_h - self.theme.font_size_md) // 2),
                color=text_color, size=self.theme.font_size_md,
            )
            ctx_item_rects.append(item_rect)
        rects["context_menu_items"] = ctx_item_rects

    def _render_viewer(self, screen, fe, rects):
        w, h = screen.get_size()
        screen.fill(self.theme.background)

        header_rect, close_rect = self.header.render(screen, title=fe.viewer_title, show_back=True)
        rects["viewer_close"] = close_rect

        content_y = header_rect.bottom + 4
        content_h = h - content_y
        line_h = 18
        visible_lines = content_h // line_h
        max_scroll = max(0, len(fe.viewer_content) - visible_lines)
        scroll = min(fe.viewer_scroll, max_scroll)

        for i in range(visible_lines):
            line_idx = scroll + i
            if line_idx >= len(fe.viewer_content):
                break
            line = fe.viewer_content[line_idx]
            y = content_y + i * line_h
            self.text.render(
                screen, line[:120],
                (self.theme.padding_md, y),
                color=self.theme.text_primary, size=self.theme.font_size_sm,
            )

        if fe.viewer_truncated and scroll >= max_scroll:
            self.text.render(
                screen, "--- File truncated (5000 lines shown) ---",
                (w // 2, h - 20), color=self.theme.warning,
                size=self.theme.font_size_sm, align="center",
            )

        if len(fe.viewer_content) > visible_lines:
            pct = scroll / max(max_scroll, 1)
            bar_h = max(20, int(content_h * visible_lines / len(fe.viewer_content)))
            bar_y = content_y + int((content_h - bar_h) * pct)
            bar_rect = pygame.Rect(w - 6, bar_y, 4, bar_h)
            pygame.draw.rect(screen, self.theme.text_secondary, bar_rect, border_radius=2)

    def _render_error_modal(self, screen, fe, rects):
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(400, w - 40)
        modal_h = 140
        modal_rect = pygame.Rect((w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h)
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(screen, "Error", (modal_rect.centerx, modal_rect.top + 25),
                         color=self.theme.error, size=self.theme.font_size_lg, align="center")
        self.text.render(screen, fe.error_message[:60], (modal_rect.centerx, modal_rect.centery),
                         color=self.theme.text_primary, size=self.theme.font_size_md, align="center")

        btn_w, btn_h = 80, 32
        btn_rect = pygame.Rect(modal_rect.centerx - btn_w // 2, modal_rect.bottom - btn_h - 15, btn_w, btn_h)
        self.action_button.render(screen, btn_rect, "OK", hover=True)
        rects["error_ok"] = btn_rect

    def _render_delete_modal(self, screen, fe, rects):
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        count = len(fe.delete_targets)
        modal_w = min(400, w - 40)
        modal_h = min(60 + count * 20 + 60, h - 80)
        modal_rect = pygame.Rect((w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h)
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(screen, f"Delete {count} item{'s' if count > 1 else ''}?",
                         (modal_rect.centerx, modal_rect.top + 25),
                         color=self.theme.error, size=self.theme.font_size_lg, align="center")

        for i, name in enumerate(fe.delete_targets[:5]):
            self.text.render(screen, os.path.basename(name),
                             (modal_rect.centerx, modal_rect.top + 50 + i * 18),
                             color=self.theme.text_secondary, size=self.theme.font_size_sm, align="center")
        if count > 5:
            self.text.render(screen, f"... and {count - 5} more",
                             (modal_rect.centerx, modal_rect.top + 50 + 5 * 18),
                             color=self.theme.text_secondary, size=self.theme.font_size_sm, align="center")

        btn_w, btn_h = 80, 32
        btn_y = modal_rect.bottom - btn_h - 15
        gap = 20
        yes_rect = pygame.Rect(modal_rect.centerx - btn_w - gap // 2, btn_y, btn_w, btn_h)
        no_rect = pygame.Rect(modal_rect.centerx + gap // 2, btn_y, btn_w, btn_h)
        self.action_button.render(screen, yes_rect, "Yes", hover=(fe.delete_highlighted == 0))
        self.action_button.render(screen, no_rect, "No", hover=(fe.delete_highlighted == 1))
        rects["delete_yes"] = yes_rect
        rects["delete_no"] = no_rect

    def _render_extract_modal(self, screen, fe, rects):
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(400, w - 40)
        modal_h = 160
        modal_rect = pygame.Rect((w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h)
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        archive_name = os.path.basename(fe.extract_target)
        self.text.render(screen, f"Extract: {archive_name}",
                         (modal_rect.centerx, modal_rect.top + 20),
                         color=self.theme.text_primary, size=self.theme.font_size_md, align="center")

        options = ["Extract to current folder", "Extract to new subfolder"]
        for i, label in enumerate(options):
            opt_y = modal_rect.top + 55 + i * 38
            opt_rect = pygame.Rect(modal_rect.left + 15, opt_y, modal_rect.width - 30, 34)
            if i == fe.extract_highlighted:
                pygame.draw.rect(screen, self.theme.primary, opt_rect, border_radius=4)
                color = self.theme.background
            else:
                color = self.theme.text_primary
            self.text.render(screen, label, (opt_rect.left + 12, opt_rect.centery - self.theme.font_size_md // 2),
                             color=color, size=self.theme.font_size_md)

        rects["extract_options"] = [
            pygame.Rect(modal_rect.left + 15, modal_rect.top + 55 + i * 38, modal_rect.width - 30, 34)
            for i in range(2)
        ]

    def _render_input_modal(self, screen, fe, input_mode, rects):
        w, h = screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(500, w - 20)
        modal_h = min(380, h - 40)
        modal_rect = pygame.Rect((w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h)
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(screen, fe.input_modal_title,
                         (modal_rect.centerx, modal_rect.top + 20),
                         color=self.theme.text_primary, size=self.theme.font_size_md, align="center")

        input_y = modal_rect.top + 48
        input_rect = pygame.Rect(modal_rect.left + 15, input_y, modal_rect.width - 30, 30)
        pygame.draw.rect(screen, self.theme.background, input_rect, border_radius=4)
        pygame.draw.rect(screen, self.theme.primary, input_rect, width=1, border_radius=4)
        self.text.render(screen, fe.input_modal_value or " ",
                         (input_rect.left + 8, input_rect.centery - self.theme.font_size_md // 2),
                         color=self.theme.text_primary, size=self.theme.font_size_md)

        kb_rect = pygame.Rect(modal_rect.left + 10, input_y + 40, modal_rect.width - 20, modal_h - 100)
        char_rects, _ = self.char_keyboard.render(
            screen, kb_rect, fe.input_modal_value, fe.kb_selected_index, show_input_field=False,
        )
        rects["kb_char_rects"] = char_rects
