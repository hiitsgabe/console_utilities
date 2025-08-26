"""
Controller mapping modal for first-time controller setup
"""
from typing import Callable, Optional
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None

from ..atoms.labels import HeadingLabel, SubheadingLabel, BodyLabel, StatusLabel
from ..atoms.buttons import PrimaryButton, SecondaryButton
from ..molecules.loading_indicators import LoadingIndicator
from utils.controller_manager import ControllerManager


class ControllerMappingModal(ModalView):
    """Modal for controller button mapping setup"""
    
    def __init__(self, controller_manager: ControllerManager, 
                 on_complete: Optional[Callable] = None,
                 on_dismiss_callback: Optional[Callable] = None,
                 **kwargs):
        default_kwargs = {
            'size_hint': (0.8, 0.8),
            'auto_dismiss': False,  # Don't auto-dismiss
            'background_color': (0, 0, 0, 0.8),
        }
        default_kwargs.update(kwargs)
        
        super().__init__(**default_kwargs)
        
        self.controller_manager = controller_manager
        self.on_complete_callback = on_complete
        self.on_dismiss_callback = on_dismiss_callback
        
        # Mapping state
        self.current_button_index = 0
        self.is_collecting = False
        self.essential_buttons = controller_manager.essential_buttons
        
        # Input handling
        self.input_event = None
        self.has_controllers = False
        
        self._build_ui()
        self._bind_events()
    
    def _build_ui(self):
        """Build the modal UI"""
        # Main container
        self.main_layout = BoxLayout(
            orientation='vertical',
            padding=40,
            spacing=20
        )
        
        # Background
        with self.main_layout.canvas.before:
            Color(0.1, 0.1, 0.1, 0.95)
            self.bg_rect = Rectangle()
        
        self.main_layout.bind(size=self._update_bg, pos=self._update_bg)
        
        # Title
        self.title_label = HeadingLabel(
            text="Controller Setup",
            size_hint_y=None,
            height=50
        )
        self.main_layout.add_widget(self.title_label)
        
        # Subtitle
        self.subtitle_label = SubheadingLabel(
            text="Configure your controller for navigation",
            size_hint_y=None,
            height=30
        )
        self.main_layout.add_widget(self.subtitle_label)
        
        # Controller status
        self.status_label = BodyLabel(
            text="",
            size_hint_y=None,
            height=25,
            color=(0.8, 0.8, 0.2, 1)  # Yellow color for warnings
        )
        self.main_layout.add_widget(self.status_label)
        
        # Current instruction
        self.instruction_label = BodyLabel(
            text="Press any button on your controller to start mapping",
            size_hint_y=None,
            height=40,
            text_size=(None, None),
            halign='center'
        )
        self.main_layout.add_widget(self.instruction_label)
        
        # Progress label
        self.progress_label = StatusLabel(
            text="",
            size_hint_y=None,
            height=30
        )
        self.main_layout.add_widget(self.progress_label)
        
        # Mapped buttons display
        self.mapped_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=200,
            spacing=5
        )
        self.main_layout.add_widget(self.mapped_layout)
        
        # Button container
        button_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=60,
            spacing=20
        )
        
        # Start/Continue button - not needed, we'll detect controller input directly
        # self.start_button = PrimaryButton(
        #     text="Start Mapping",
        #     size_hint=(None, None),
        #     size=(150, 50)
        # )
        # self.start_button.bind(on_press=self._start_mapping)
        # button_layout.add_widget(self.start_button)
        
        # Skip button (for touchscreen users)
        self.skip_button = SecondaryButton(
            text="Skip (Touchscreen)",
            size_hint=(None, None),
            size=(180, 50)
        )
        self.skip_button.bind(on_press=self._skip_mapping)
        button_layout.add_widget(self.skip_button)
        
        # Add spacer and buttons
        button_layout.add_widget(Label())  # Spacer
        self.main_layout.add_widget(button_layout)
        
        self.add_widget(self.main_layout)
        
        # Update initial state
        self._check_controller_status()
        self._update_display()
        
        # Start listening for input immediately
        self._start_listening()
    
    def _update_bg(self, *args):
        """Update background rectangle"""
        self.bg_rect.pos = self.main_layout.pos
        self.bg_rect.size = self.main_layout.size
    
    def _bind_events(self):
        """Bind controller input events"""
        # We'll need to integrate with Kivy's input system
        # For now, we'll use a scheduled check
        pass
    
    def _check_controller_status(self):
        """Check if controllers are available"""
        if not PYGAME_AVAILABLE:
            self.has_controllers = False
            self.status_label.text = "Controller support not available"
            self.status_label.color = (0.8, 0.8, 0.2, 1)  # Yellow
            return
            
        try:
            # Initialize pygame if needed
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            
            joystick_count = pygame.joystick.get_count()
            self.has_controllers = joystick_count > 0
            
            if self.has_controllers:
                controller_names = []
                for i in range(joystick_count):
                    try:
                        joystick = pygame.joystick.Joystick(i)
                        joystick.init()
                        controller_names.append(joystick.get_name())
                    except Exception as e:
                        print(f"Error initializing controller {i}: {e}")
                
                self.status_label.text = f"Controllers detected: {', '.join(controller_names)}"
                self.status_label.color = (0.2, 0.8, 0.2, 1)  # Green
            else:
                self.status_label.text = "No controllers detected - will use simulation for demo"
                self.status_label.color = (0.8, 0.8, 0.2, 1)  # Yellow
                
        except Exception as e:
            print(f"Error checking controller status: {e}")
            self.has_controllers = False
            self.status_label.text = "Controller detection failed"
            self.status_label.color = (0.8, 0.2, 0.2, 1)  # Red
    
    def _start_listening(self):
        """Start listening for controller input"""
        if not self.input_event:
            # Start input polling immediately
            self.input_event = Clock.schedule_interval(self._check_for_input, 1/60.0)
            print("Started listening for controller input...")
    
    def _start_actual_mapping(self):
        """Actually start the mapping process after detecting first input"""
        if not self.is_collecting:
            print("Starting controller mapping process...")
            self.is_collecting = True
            self.current_button_index = 0
            self.controller_manager.controller_mapping = {}
            self.skip_button.text = "Cancel"
            self._update_display()
    
    def _start_mapping(self, *args):
        """Start the controller mapping process"""
        if not self.is_collecting:
            self.is_collecting = True
            self.current_button_index = 0
            self.controller_manager.controller_mapping = {}
            self.start_button.text = "Mapping..."
            self.start_button.disabled = True
            self.skip_button.disabled = True
            
            # Start listening for input
            self.input_event = Clock.schedule_interval(self._check_for_input, 1/60.0)
            self._update_display()
    
    def _skip_mapping(self, *args):
        """Skip controller mapping for touchscreen users or cancel current mapping"""
        if self.is_collecting:
            # Cancel current mapping
            self.is_collecting = False
            self.current_button_index = 0
            self.skip_button.text = "Skip (Touchscreen)"
            self._update_display()
        else:
            # Skip entirely for touchscreen users
            if self.on_dismiss_callback:
                self.on_dismiss_callback()
            self.dismiss()
    
    def _check_for_input(self, dt):
        """Check for real controller input"""
        if not PYGAME_AVAILABLE:
            return True
            
        if self.current_button_index >= len(self.essential_buttons):
            self._complete_mapping()
            return False
        
        try:
            # Process pygame events for controller input
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.JOYBUTTONDOWN:
                    print(f"Detected controller button press: {event.button}")
                    if not self.is_collecting:
                        # First button press starts the mapping process
                        self._start_actual_mapping()
                    else:
                        self._handle_button_mapping(event.button)
                    return True
                elif event.type == pygame.JOYHATMOTION and event.value != (0, 0):
                    print(f"Detected controller hat motion: {event.value}")
                    if not self.is_collecting:
                        # First input starts the mapping process
                        self._start_actual_mapping()
                    else:
                        self._handle_hat_mapping(event.value)
                    return True
                elif event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.5:
                    print(f"Detected controller axis motion: axis {event.axis} = {event.value}")
                    if not self.is_collecting:
                        # First input starts the mapping process
                        self._start_actual_mapping()
                    # Note: We don't map axes in this implementation, just buttons and hats
                    return True
        except Exception as e:
            print(f"Error checking for controller input: {e}")
            # Fall back to simulation for demo if no real controllers
            if not self.has_controllers:
                self._simulate_input_fallback(dt)
        
        return True
    
    def _handle_button_mapping(self, button):
        """Handle mapping a regular button"""
        if self.current_button_index < len(self.essential_buttons):
            button_key, _ = self.essential_buttons[self.current_button_index]
            self.controller_manager.map_button(button_key, button)
            self.current_button_index += 1
            self._update_display()
    
    def _handle_hat_mapping(self, hat_value):
        """Handle mapping a hat (D-pad) input"""
        if self.current_button_index < len(self.essential_buttons):
            button_key, _ = self.essential_buttons[self.current_button_index]
            
            # Only map if this is a directional input and matches expected direction
            hat_x, hat_y = hat_value
            if button_key == "up" and hat_y == 1:
                self.controller_manager.map_button(button_key, ("hat", 0, 1))
                self.current_button_index += 1
                self._update_display()
            elif button_key == "down" and hat_y == -1:
                self.controller_manager.map_button(button_key, ("hat", 0, -1))
                self.current_button_index += 1
                self._update_display()
            elif button_key == "left" and hat_x == -1:
                self.controller_manager.map_button(button_key, ("hat", -1, 0))
                self.current_button_index += 1
                self._update_display()
            elif button_key == "right" and hat_x == 1:
                self.controller_manager.map_button(button_key, ("hat", 1, 0))
                self.current_button_index += 1
                self._update_display()
    
    def _simulate_input_fallback(self, dt):
        """Fallback simulation if no controller is detected"""
        # For demonstration when no controller is present
        if hasattr(self, '_demo_timer'):
            self._demo_timer += dt
            if self._demo_timer >= 2.0:
                self._simulate_button_press()
                self._demo_timer = 0
        else:
            self._demo_timer = 0
    
    def _simulate_button_press(self):
        """Simulate a button press for demo purposes"""
        if self.current_button_index < len(self.essential_buttons):
            button_key, _ = self.essential_buttons[self.current_button_index]
            
            # Simulate mapping
            if button_key in ['up', 'down', 'left', 'right']:
                # Simulate hat input for directional buttons
                directions = {'up': (0, 1), 'down': (0, -1), 'left': (-1, 0), 'right': (1, 0)}
                self.controller_manager.map_button(button_key, ("hat", *directions[button_key]))
            else:
                # Simulate regular button
                self.controller_manager.map_button(button_key, self.current_button_index)
            
            self.current_button_index += 1
            self._update_display()
    
    def _update_display(self):
        """Update the display with current mapping state"""
        if not self.is_collecting:
            self.instruction_label.text = "Press any button on your controller to start mapping"
            self.progress_label.text = "Waiting for controller input..."
        elif self.current_button_index < len(self.essential_buttons):
            button_key, button_description = self.essential_buttons[self.current_button_index]
            self.instruction_label.text = f"Press the {button_description}"
            self.progress_label.text = f"Button {self.current_button_index + 1} of {len(self.essential_buttons)}"
        else:
            self.instruction_label.text = "Mapping complete!"
            self.progress_label.text = f"All {len(self.essential_buttons)} buttons mapped"
        
        # Update mapped buttons display
        self.mapped_layout.clear_widgets()
        
        for i, (button_key, _) in enumerate(self.essential_buttons[:self.current_button_index]):
            if button_key in self.controller_manager.controller_mapping:
                mapping_info = self.controller_manager.controller_mapping[button_key]
                if isinstance(mapping_info, tuple) and mapping_info[0] == "hat":
                    mapped_text = f"{button_key}: D-pad {mapping_info[1:]}"
                else:
                    mapped_text = f"{button_key}: Button {mapping_info}"
                
                mapped_label = BodyLabel(
                    text=mapped_text,
                    size_hint_y=None,
                    height=25,
                    color=(0.2, 0.8, 0.2, 1)  # Green color
                )
                self.mapped_layout.add_widget(mapped_label)
    
    def _complete_mapping(self):
        """Complete the mapping process"""
        if self.input_event:
            self.input_event.cancel()
            self.input_event = None
        
        # Save the mapping
        self.controller_manager.save_mapping()
        
        self.is_collecting = False
        self.skip_button.text = "Continue"
        self.skip_button.disabled = False
        
        self._update_display()
        
        # Auto-close after a short delay
        Clock.schedule_once(self._auto_close, 2.0)
    
    def _auto_close(self, dt):
        """Auto-close the modal after completion"""
        if self.on_complete_callback:
            self.on_complete_callback()
        self.dismiss()
    
    def on_dismiss(self):
        """Clean up when modal is dismissed"""
        if self.input_event:
            self.input_event.cancel()
            self.input_event = None
        return super().on_dismiss()
