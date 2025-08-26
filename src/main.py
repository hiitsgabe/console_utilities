"""
Simplified Kivy ROM Downloader Application
Basic working version without complex components
"""

import os
import sys
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.config import Config

# Configure Kivy window settings
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '600')
Config.set('graphics', 'resizable', True)

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.json_reader import JSONReader
from utils.settings_manager import SettingsManager
from utils.controller_manager import ControllerManager
from utils.controller_input import ControllerInput
from utils.focus_manager import FocusManager
from screens.games_screen import GamesScreen
from components.molecules.navigation_manager import NavigationManager
from components.organisms.controller_mapping_modal import ControllerMappingModal


class SystemsScreen(Screen):
    """Systems screen with real data from JSON configuration"""
    
    def __init__(self, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.name = 'systems'
        self.app_instance = app_instance
        self.systems_data = []
        
        # Focus management for controller navigation
        self.focus_manager = FocusManager()
        self.focus_manager.bind(on_item_selected=self._on_item_selected)
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        title = Label(
            text='ROM Downloader - Select a System',
            font_size='24sp',
            size_hint_y=None,
            height=50,
            color=(1, 1, 1, 1)
        )
        main_layout.add_widget(title)
        
        # Scrollable systems list
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView()
        
        # Systems container
        self.systems_container = BoxLayout(
            orientation='vertical',
            spacing=5,
            size_hint_y=None
        )
        self.systems_container.bind(minimum_height=self.systems_container.setter('height'))
        
        scroll.add_widget(self.systems_container)
        main_layout.add_widget(scroll)
        
        # Settings button at bottom
        self.settings_btn = Button(
            text='Settings',
            size_hint_y=None,
            height=50,
            font_size='16sp'
        )
        self.settings_btn.bind(on_press=self._go_to_settings)
        main_layout.add_widget(self.settings_btn)
        
        self.add_widget(main_layout)
        
        # Load systems data on creation
        self._load_systems_data()
    
    def _load_systems_data(self):
        """Load gaming systems from JSON configuration"""
        try:
            if self.app_instance and hasattr(self.app_instance, 'json_reader'):
                # Try to load from the assets/config directory
                config_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    'assets', 'config', 'download.json'
                )
                
                if os.path.exists(config_path):
                    self.systems_data = self.app_instance.json_reader.get_systems(config_path)
                    print(f"Loaded {len(self.systems_data)} gaming systems")
                    self._populate_systems_list()
                else:
                    print(f"Config file not found at: {config_path}")
                    self._show_no_systems_message()
            else:
                self._show_no_systems_message()
        except Exception as e:
            print(f"Error loading systems data: {e}")
            self._show_no_systems_message()
    
    def _populate_systems_list(self):
        """Populate the systems list with loaded data"""
        # Clear existing systems
        self.systems_container.clear_widgets()
        self.focus_manager.clear()
        
        # Add each system as a button
        for system in self.systems_data:
            system_name = system.get('name', 'Unknown System')
            
            # Create system button
            system_btn = Button(
                text=system_name,
                size_hint_y=None,
                height=60,
                font_size='18sp',
                text_size=(None, None),
                halign='left',
                valign='middle'
            )
            
            # Bind the button to select this system
            system_btn.bind(on_press=lambda btn, sys=system: self._select_system(sys))
            
            # Add to container
            self.systems_container.add_widget(system_btn)
            
            # Add to focus manager for controller navigation
            self.focus_manager.add_focusable(
                system_btn, 
                on_select=lambda sys=system: self._select_system(sys),
                data=system,
                navigation_id=f"system_{system_name}"
            )
        
        # Add settings button to focus manager
        self.focus_manager.add_focusable(
            self.settings_btn,
            on_select=lambda data: self._go_to_settings(None),
            navigation_id="settings_button"
        )
        
        print(f"Added {len(self.systems_data)} system buttons to interface")
    
    def _on_item_selected(self, focus_manager, index: int, focusable_widget):
        """Handle item selection from focus manager"""
        focusable_widget.select()
    
    def navigate_up(self):
        """Handle up navigation"""
        self.focus_manager.navigate_up()
    
    def navigate_down(self):
        """Handle down navigation"""
        self.focus_manager.navigate_down()
    
    def navigate_left(self):
        """Handle left navigation"""
        self.focus_manager.navigate_left()
    
    def navigate_right(self):
        """Handle right navigation"""
        self.focus_manager.navigate_right()
    
    def select_current(self):
        """Handle select button press"""
        self.focus_manager.select_current()
    
    def _show_no_systems_message(self):
        """Show message when no systems are available"""
        self.systems_container.clear_widgets()
        
        message = Label(
            text='No gaming systems found.\nPlease check configuration.',
            font_size='16sp',
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=100
        )
        self.systems_container.add_widget(message)
    
    def _select_system(self, system):
        """Handle system selection"""
        system_name = system.get('name', 'Unknown')
        print(f"Selected system: {system_name}")
        
        # Get the app instance and navigate to games screen
        if self.app_instance and hasattr(self.app_instance, 'games_screen') and hasattr(self.app_instance, 'navigation_manager'):
            # Set the system data on the games screen
            self.app_instance.games_screen.set_system_data(system)
            
            # Navigate to games screen with proper transition
            self.app_instance.navigation_manager.navigate_to('games', 'forward')
        else:
            # Fallback - show error message
            from kivy.uix.popup import Popup
            
            content = Label(
                text=f'Error: Cannot access games screen.\nPlease try again.',
                text_size=(300, None),
                halign='center'
            )
            
            popup = Popup(
                title='Navigation Error',
                content=content,
                size_hint=(0.6, 0.4)
            )
            popup.open()
    
    def _go_to_settings(self, button):
        """Navigate to settings screen"""
        if self.app_instance and hasattr(self.app_instance, 'navigation_manager'):
            self.app_instance.navigation_manager.navigate_to('settings', 'modal')
        else:
            self.manager.current = 'settings'


class SettingsScreen(Screen):
    """Settings screen with real settings management"""
    
    def __init__(self, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.name = 'settings'
        self.app_instance = app_instance
        
        # Focus management for controller navigation
        self.focus_manager = FocusManager()
        self.focus_manager.bind(on_item_selected=self._on_item_selected)
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        title = Label(
            text='Settings',
            font_size='24sp',
            size_hint_y=None,
            height=50,
            color=(1, 1, 1, 1)
        )
        main_layout.add_widget(title)
        
        # Scrollable settings list
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView()
        
        # Settings container
        self.settings_container = BoxLayout(
            orientation='vertical',
            spacing=10,
            size_hint_y=None
        )
        self.settings_container.bind(minimum_height=self.settings_container.setter('height'))
        
        scroll.add_widget(self.settings_container)
        main_layout.add_widget(scroll)
        
        # Button layout
        button_layout = BoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint_y=None,
            height=50
        )
        
        # Back button
        self.back_btn = Button(
            text='← Back to Systems',
            size_hint_x=0.5,
            font_size='16sp'
        )
        self.back_btn.bind(on_press=self._go_back)
        button_layout.add_widget(self.back_btn)
        
        # Reset defaults button
        self.reset_btn = Button(
            text='Reset to Defaults',
            size_hint_x=0.5,
            font_size='16sp'
        )
        self.reset_btn.bind(on_press=self._reset_defaults)
        button_layout.add_widget(self.reset_btn)
        
        main_layout.add_widget(button_layout)
        self.add_widget(main_layout)
        
        # Add buttons to focus manager
        self.focus_manager.add_focusable(
            self.back_btn,
            on_select=lambda data: self._go_back(None),
            navigation_id="back_button"
        )
        self.focus_manager.add_focusable(
            self.reset_btn,
            on_select=lambda data: self._reset_defaults(None),
            navigation_id="reset_button"
        )
        
        # Load settings when screen is created
        self._load_settings_display()
    
    def _on_item_selected(self, focus_manager, index: int, focusable_widget):
        """Handle item selection from focus manager"""
        focusable_widget.select()
    
    def navigate_up(self):
        """Handle up navigation"""
        self.focus_manager.navigate_up()
    
    def navigate_down(self):
        """Handle down navigation"""
        self.focus_manager.navigate_down()
    
    def navigate_left(self):
        """Handle left navigation"""
        self.focus_manager.navigate_left()
    
    def navigate_right(self):
        """Handle right navigation"""
        self.focus_manager.navigate_right()
    
    def select_current(self):
        """Handle select button press"""
        self.focus_manager.select_current()
    
    def _load_settings_display(self):
        """Load and display current settings"""
        if not self.app_instance or not hasattr(self.app_instance, 'settings_manager'):
            self._show_no_settings_message()
            return
        
        settings_manager = self.app_instance.settings_manager
        settings_list = settings_manager.get_settings_display_list()
        
        # Clear existing settings
        self.settings_container.clear_widgets()
        
        # Add each setting as a row
        for setting in settings_list:
            self._create_setting_row(setting)
    
    def _create_setting_row(self, setting):
        """Create a row for a single setting"""
        # Setting row container
        row = BoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint_y=None,
            height=60
        )
        
        # Setting name label
        name_label = Label(
            text=setting['name'],
            font_size='16sp',
            color=(1, 1, 1, 1),
            size_hint_x=0.6,
            text_size=(None, None),
            halign='left',
            valign='middle'
        )
        row.add_widget(name_label)
        
        # Setting value/control
        if setting['type'] == 'boolean':
            # Toggle button for boolean settings
            value_btn = Button(
                text='ON' if setting['value'] else 'OFF',
                size_hint_x=0.4,
                font_size='14sp'
            )
            value_btn.bind(on_press=lambda btn, s=setting: self._toggle_boolean_setting(s, btn))
            row.add_widget(value_btn)
            
        elif setting['type'] == 'choice':
            # Button that cycles through choices
            value_btn = Button(
                text=str(setting['value']).upper(),
                size_hint_x=0.4,
                font_size='14sp'
            )
            value_btn.bind(on_press=lambda btn, s=setting: self._cycle_choice_setting(s, btn))
            row.add_widget(value_btn)
            
        elif setting['type'] == 'path':
            # Button to edit path
            display_path = setting['value'] if setting['value'] else 'Not set'
            if len(display_path) > 30:
                display_path = '...' + display_path[-27:]
            
            value_btn = Button(
                text=display_path,
                size_hint_x=0.4,
                font_size='12sp'
            )
            value_btn.bind(on_press=lambda btn, s=setting: self._edit_path_setting(s))
            row.add_widget(value_btn)
        
        self.settings_container.add_widget(row)
    
    def _toggle_boolean_setting(self, setting, button):
        """Toggle a boolean setting"""
        if not self.app_instance or not hasattr(self.app_instance, 'settings_manager'):
            return
        
        settings_manager = self.app_instance.settings_manager
        current_value = settings_manager.get_setting(setting['key'])
        new_value = not current_value
        
        settings_manager.set_setting(setting['key'], new_value)
        button.text = 'ON' if new_value else 'OFF'
        
        print(f"Toggled {setting['name']}: {new_value}")
    
    def _cycle_choice_setting(self, setting, button):
        """Cycle through choices for a choice setting"""
        if not self.app_instance or not hasattr(self.app_instance, 'settings_manager'):
            return
        
        settings_manager = self.app_instance.settings_manager
        current_value = settings_manager.get_setting(setting['key'])
        
        # Find current index and move to next
        try:
            current_index = setting['choices'].index(current_value)
            next_index = (current_index + 1) % len(setting['choices'])
            new_value = setting['choices'][next_index]
        except ValueError:
            # Current value not in choices, use first choice
            new_value = setting['choices'][0]
        
        settings_manager.set_setting(setting['key'], new_value)
        button.text = str(new_value).upper()
        
        print(f"Changed {setting['name']}: {new_value}")
    
    def _edit_path_setting(self, setting):
        """Edit a path setting"""
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        
        if not self.app_instance or not hasattr(self.app_instance, 'settings_manager'):
            return
        
        settings_manager = self.app_instance.settings_manager
        current_value = settings_manager.get_setting(setting['key'], '')
        
        # Create text input for path
        path_input = TextInput(
            text=current_value,
            multiline=False,
            size_hint_y=None,
            height=40
        )
        
        # Container for input and buttons
        content_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content_layout.add_widget(Label(text=f"Edit {setting['name']}:", size_hint_y=None, height=30))
        content_layout.add_widget(path_input)
        
        # Button layout
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
        
        def save_path(button):
            new_path = path_input.text.strip()
            settings_manager.set_setting(setting['key'], new_path)
            popup.dismiss()
            self._load_settings_display()  # Refresh display
            print(f"Updated {setting['name']}: {new_path}")
        
        def cancel_edit(button):
            popup.dismiss()
        
        save_btn = Button(text='Save', size_hint_x=0.5)
        save_btn.bind(on_press=save_path)
        cancel_btn = Button(text='Cancel', size_hint_x=0.5)
        cancel_btn.bind(on_press=cancel_edit)
        
        btn_layout.add_widget(save_btn)
        btn_layout.add_widget(cancel_btn)
        content_layout.add_widget(btn_layout)
        
        # Create and open popup
        popup = Popup(
            title=f'Edit {setting["name"]}',
            content=content_layout,
            size_hint=(0.8, 0.6)
        )
        popup.open()
    
    def _show_no_settings_message(self):
        """Show message when settings manager is not available"""
        self.settings_container.clear_widgets()
        
        message = Label(
            text='Settings not available.\nSettings manager not initialized.',
            font_size='16sp',
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=100
        )
        self.settings_container.add_widget(message)
    
    def _reset_defaults(self, button):
        """Reset all settings to default values"""
        if not self.app_instance or not hasattr(self.app_instance, 'settings_manager'):
            return
        
        from kivy.uix.popup import Popup
        
        def confirm_reset(btn):
            self.app_instance.settings_manager.reset_to_defaults()
            popup.dismiss()
            self._load_settings_display()  # Refresh display
            print("Settings reset to defaults")
        
        def cancel_reset(btn):
            popup.dismiss()
        
        # Create confirmation popup
        content_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content_layout.add_widget(Label(
            text='Are you sure you want to reset all settings to defaults?\nThis cannot be undone.',
            size_hint_y=None,
            height=60
        ))
        
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
        confirm_btn = Button(text='Reset', size_hint_x=0.5)
        confirm_btn.bind(on_press=confirm_reset)
        cancel_btn = Button(text='Cancel', size_hint_x=0.5)
        cancel_btn.bind(on_press=cancel_reset)
        
        btn_layout.add_widget(confirm_btn)
        btn_layout.add_widget(cancel_btn)
        content_layout.add_widget(btn_layout)
        
        popup = Popup(
            title='Confirm Reset',
            content=content_layout,
            size_hint=(0.6, 0.4)
        )
        popup.open()
    
    def _go_back(self, button):
        """Navigate back to previous screen"""
        if self.app_instance and hasattr(self.app_instance, 'navigation_manager'):
            self.app_instance.navigation_manager.go_back()
        else:
            self.manager.current = 'systems'


class SimpleROMDownloaderApp(App):
    """Simplified ROM Downloader App"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "ROM Downloader - Kivy Edition"
        
        # Initialize utilities
        self.json_reader = JSONReader()
        self.settings_manager = SettingsManager()
        self.systems_data = None
        self.navigation_manager = None
        
        # Initialize controller support
        self.controller_manager = ControllerManager()
        self.controller_input = None
        self.controller_mapping_modal = None
        
    def build(self):
        """Build the main application interface"""
        # Create screen manager
        sm = ScreenManager()
        
        # Add screens with app instance reference
        systems_screen = SystemsScreen(app_instance=self)
        settings_screen = SettingsScreen(app_instance=self)
        games_screen = GamesScreen()
        
        # Setup games screen navigation
        games_screen.setup_navigation(sm, self)
        
        sm.add_widget(systems_screen)
        sm.add_widget(settings_screen)
        sm.add_widget(games_screen)
        
        # Store reference to games screen for easy access
        self.games_screen = games_screen
        
        # Initialize navigation manager
        self.navigation_manager = NavigationManager(sm)
        
        # Set up navigation callbacks for logging
        self.navigation_manager.add_navigation_callback(self._on_navigation_change)
        
        # Initialize controller input
        self.controller_input = ControllerInput(self.controller_manager)
        self._setup_controller_callbacks()
        
        # Check if controller mapping is needed
        if self.controller_manager.needs_mapping():
            # Show controller mapping modal on next frame
            from kivy.clock import Clock
            Clock.schedule_once(self._show_controller_mapping, 0.5)
        
        # Start at systems screen
        self.navigation_manager.navigate_to_root('systems')
        
        return sm
    
    def _on_navigation_change(self, from_screen: str, to_screen: str):
        """Handle navigation changes"""
        print(f"Navigation: {from_screen} → {to_screen}")
        
        # Update window title based on current screen
        screen_titles = {
            'systems': 'ROM Downloader - Select System',
            'games': 'ROM Downloader - Browse Games', 
            'settings': 'ROM Downloader - Settings'
        }
        
        new_title = screen_titles.get(to_screen, 'ROM Downloader')
        self.title = new_title
    
    def _setup_controller_callbacks(self):
        """Setup controller input callbacks"""
        # Register callbacks for navigation actions
        self.controller_input.register_action_callback('up', self._handle_controller_navigation)
        self.controller_input.register_action_callback('down', self._handle_controller_navigation)
        self.controller_input.register_action_callback('left', self._handle_controller_navigation)
        self.controller_input.register_action_callback('right', self._handle_controller_navigation)
        self.controller_input.register_action_callback('select', self._handle_controller_action)
        self.controller_input.register_action_callback('back', self._handle_controller_action)
        self.controller_input.register_action_callback('start', self._handle_controller_action)
    
    def _handle_controller_navigation(self, action: str, event_data: dict):
        """Handle controller navigation input"""
        current_screen = self.navigation_manager.current_screen
        print(f"Controller navigation: {action} on {current_screen}")
        
        # Get the current screen object
        screen_obj = self.navigation_manager.screen_manager.get_screen(current_screen)
        
        # Delegate navigation to the screen if it supports it
        if action == 'up' and hasattr(screen_obj, 'navigate_up'):
            screen_obj.navigate_up()
        elif action == 'down' and hasattr(screen_obj, 'navigate_down'):
            screen_obj.navigate_down()
        elif action == 'left' and hasattr(screen_obj, 'navigate_left'):
            screen_obj.navigate_left()
        elif action == 'right' and hasattr(screen_obj, 'navigate_right'):
            screen_obj.navigate_right()
    
    def _handle_controller_action(self, action: str, event_data: dict):
        """Handle controller action input"""
        current_screen = self.navigation_manager.current_screen
        print(f"Controller action: {action} on {current_screen}")
        
        # Get the current screen object
        screen_obj = self.navigation_manager.screen_manager.get_screen(current_screen)
        
        if action == 'select':
            # Handle select button
            if hasattr(screen_obj, 'select_current'):
                screen_obj.select_current()
        elif action == 'back':
            # Handle back navigation
            if current_screen != 'systems':
                self.navigation_manager.go_back()
        elif action == 'start':
            # Handle start button - different actions per screen
            if current_screen == 'systems':
                self.navigation_manager.navigate_to('settings', 'modal')
            elif current_screen == 'games':
                # Quick download action
                if hasattr(screen_obj, 'game_browser') and hasattr(screen_obj.game_browser, 'start_action'):
                    screen_obj.game_browser.start_action()
    
    def _show_controller_mapping(self, dt):
        """Show the controller mapping modal"""
        if self.controller_mapping_modal is None:
            # Pause main controller input to avoid conflicts
            if self.controller_input:
                self.controller_input.pause()
            
            self.controller_mapping_modal = ControllerMappingModal(
                self.controller_manager,
                on_complete=self._on_controller_mapping_complete,
                on_dismiss_callback=self._on_controller_mapping_dismissed
            )
        
        self.controller_mapping_modal.open()
    
    def _on_controller_mapping_complete(self):
        """Called when controller mapping is completed"""
        print("Controller mapping completed successfully")
        self.controller_mapping_modal = None
        # Resume main controller input
        if self.controller_input:
            self.controller_input.resume()
    
    def _on_controller_mapping_dismissed(self):
        """Called when controller mapping is dismissed"""
        print("Controller mapping dismissed (touchscreen user)")
        self.controller_mapping_modal = None
        # Resume main controller input
        if self.controller_input:
            self.controller_input.resume()
    
    def on_stop(self):
        """Cleanup when app stops"""
        if self.controller_input:
            self.controller_input.cleanup()
        return super().on_stop()
    



if __name__ == '__main__':
    SimpleROMDownloaderApp().run()