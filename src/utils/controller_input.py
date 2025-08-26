"""
Controller input integration for Kivy
"""
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None

from typing import Dict, Any, Optional, Callable
from kivy.clock import Clock
from kivy.event import EventDispatcher

from utils.controller_manager import ControllerManager


class ControllerInput(EventDispatcher):
    """Handles controller input integration with Kivy"""
    
    __events__ = ('on_controller_action',)
    
    def __init__(self, controller_manager: ControllerManager):
        super().__init__()
        
        self.controller_manager = controller_manager
        self.pygame_initialized = False
        self.joysticks = []
        
        # Navigation state
        self.navigation_callbacks = {}
        self.action_callbacks = {}
        
        # Input control
        self.is_paused = False
        
        # Initialize pygame joystick support
        self._init_pygame_joystick()
        
        # Start input polling
        self.input_event = Clock.schedule_interval(self._poll_input, 1/60.0)
    
    def _init_pygame_joystick(self):
        """Initialize pygame joystick support"""
        if not PYGAME_AVAILABLE:
            print("Pygame not available - controller support disabled")
            self.pygame_initialized = False
            return
            
        try:
            # Only initialize if not already done by Kivy/other components
            if not pygame.get_init():
                pygame.init()
            
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            
            # Initialize all joysticks
            joystick_count = pygame.joystick.get_count()
            print(f"Found {joystick_count} joystick(s)")
            
            self.joysticks = []  # Clear existing joysticks
            for i in range(joystick_count):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    joystick.init()
                    self.joysticks.append(joystick)
                    print(f"Initialized joystick {i}: {joystick.get_name()}")
                except Exception as e:
                    print(f"Failed to initialize joystick {i}: {e}")
            
            self.pygame_initialized = True
            print(f"Controller input system initialized with {len(self.joysticks)} controllers")
            
        except Exception as e:
            print(f"Failed to initialize pygame joystick: {e}")
            self.pygame_initialized = False
    
    def has_controllers(self):
        """Check if any controllers are connected"""
        return len(self.joysticks) > 0
    
    def get_controller_info(self):
        """Get information about connected controllers"""
        info = []
        for i, joystick in enumerate(self.joysticks):
            try:
                info.append({
                    'id': i,
                    'name': joystick.get_name(),
                    'buttons': joystick.get_numbuttons(),
                    'hats': joystick.get_numhats(),
                    'axes': joystick.get_numaxes()
                })
            except Exception as e:
                print(f"Error getting info for joystick {i}: {e}")
        return info
    
    def pause(self):
        """Pause controller input processing"""
        self.is_paused = True
        print("Controller input paused")
    
    def resume(self):
        """Resume controller input processing"""
        self.is_paused = False
        print("Controller input resumed")
    
    def _poll_input(self, dt):
        """Poll for controller input"""
        if not PYGAME_AVAILABLE or not self.pygame_initialized or self.is_paused:
            return True
        
        try:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    self._handle_button_press(event)
                elif event.type == pygame.JOYHATMOTION:
                    self._handle_hat_motion(event)
                elif event.type == pygame.JOYAXISMOTION:
                    self._handle_axis_motion(event)
        
        except Exception as e:
            print(f"Error polling controller input: {e}")
        
        return True
    
    def _handle_button_press(self, event):
        """Handle joystick button press"""
        event_data = {
            'button': event.button,
            'joy': event.joy if hasattr(event, 'joy') else 0
        }
        
        # Check if this maps to any action
        action = self.controller_manager.process_input_event('joybuttondown', event_data)
        if action:
            self._trigger_action(action, event_data)
    
    def _handle_hat_motion(self, event):
        """Handle joystick hat (D-pad) motion"""
        event_data = {
            'value': event.value,
            'hat': event.hat if hasattr(event, 'hat') else 0,
            'joy': event.joy if hasattr(event, 'joy') else 0
        }
        
        # Check if this maps to any action
        action = self.controller_manager.process_input_event('joyhatmotion', event_data)
        if action:
            self._trigger_action(action, event_data)
    
    def _handle_axis_motion(self, event):
        """Handle joystick axis motion (analog sticks)"""
        # We can use analog sticks for navigation too
        threshold = 0.5
        
        event_data = {
            'axis': event.axis,
            'value': event.value,
            'joy': event.joy if hasattr(event, 'joy') else 0
        }
        
        # Convert axis motion to directional input
        if event.axis == 0:  # Left stick X-axis
            if event.value < -threshold:
                self._trigger_action('left', event_data)
            elif event.value > threshold:
                self._trigger_action('right', event_data)
        elif event.axis == 1:  # Left stick Y-axis
            if event.value < -threshold:
                self._trigger_action('up', event_data)
            elif event.value > threshold:
                self._trigger_action('down', event_data)
    
    def _trigger_action(self, action: str, event_data: Dict[str, Any]):
        """Trigger an action based on controller input"""
        print(f"Controller action: {action}")
        
        # Dispatch the event
        self.dispatch('on_controller_action', action, event_data)
        
        # Call registered callbacks
        if action in self.action_callbacks:
            for callback in self.action_callbacks[action]:
                try:
                    callback(action, event_data)
                except Exception as e:
                    print(f"Error in action callback: {e}")
    
    def register_action_callback(self, action: str, callback: Callable):
        """Register a callback for a specific action"""
        if action not in self.action_callbacks:
            self.action_callbacks[action] = []
        self.action_callbacks[action].append(callback)
    
    def unregister_action_callback(self, action: str, callback: Callable):
        """Unregister a callback for a specific action"""
        if action in self.action_callbacks:
            try:
                self.action_callbacks[action].remove(callback)
            except ValueError:
                pass
    
    def register_navigation_callback(self, screen_name: str, callback: Callable):
        """Register a navigation callback for a specific screen"""
        self.navigation_callbacks[screen_name] = callback
    
    def unregister_navigation_callback(self, screen_name: str):
        """Unregister a navigation callback for a screen"""
        if screen_name in self.navigation_callbacks:
            del self.navigation_callbacks[screen_name]
    
    def trigger_navigation(self, screen_name: str, action: str, event_data: Dict[str, Any]):
        """Trigger navigation for a specific screen"""
        if screen_name in self.navigation_callbacks:
            try:
                self.navigation_callbacks[screen_name](action, event_data)
            except Exception as e:
                print(f"Error in navigation callback: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.input_event:
            self.input_event.cancel()
            self.input_event = None
        
        # Clean up pygame
        if PYGAME_AVAILABLE and self.pygame_initialized:
            for joystick in self.joysticks:
                joystick.quit()
            pygame.joystick.quit()
            pygame.quit()
    
    def on_controller_action(self, *args):
        """Event handler for controller actions (override in subclass)"""
        pass
