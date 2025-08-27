#!/usr/bin/env python3
"""Test script to debug settings loading"""

import json
import os

# Use the same paths as the main application
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, "config.json")

def load_settings():
    """Load settings from config file"""
    if os.name == 'nt':
        # Windows
        default_work_dir = os.path.join(os.path.expanduser("~"), "Downloads", "py_downloads")
        default_roms_dir = os.path.join(os.path.expanduser("~"), "Documents", "roms")
    else:
        # Unix-like (Linux, macOS)
        if os.path.exists("/userdata/roms"):
            # Batocera/console environment
            default_work_dir = "/userdata/py_downloads"
            default_roms_dir = "/userdata/roms"
        else:
            # Development environment
            default_work_dir = os.path.join(script_dir, "py_downloads")
            default_roms_dir = os.path.join(script_dir, "roms")
    
    default_settings = {
        "enable_boxart": True,
        "view_type": "list",
        "usa_only": False,
        "work_dir": default_work_dir,
        "roms_dir": default_roms_dir,
        "switch_keys_path": "",
        "cache_enabled": True,
        "archive_json_url": ""
    }
    
    print(f"Looking for config file: {CONFIG_FILE}")
    print(f"Config file exists: {os.path.exists(CONFIG_FILE)}")
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_settings = json.load(f)
                print(f"Loaded settings from file: {loaded_settings}")
                # Merge with defaults to handle new settings
                default_settings.update(loaded_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")
    else:
        print("No config file found, using defaults")
    
    print(f"Final settings: {default_settings}")
    return default_settings

if __name__ == "__main__":
    print("Testing settings loading...")
    settings = load_settings()
    print(f"enable_boxart: {settings.get('enable_boxart')}")
    print(f"cache_enabled: {settings.get('cache_enabled')}")