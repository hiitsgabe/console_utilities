#!/usr/bin/env python3

import sys
import os

# Ensure src directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Android compatibility adjustments
if __name__ == "__main__":
    # Set Android environment flag
    os.environ["ANDROID_BUILD"] = "1"
    
    # Android specific path adjustments
    if hasattr(sys, 'android'):
        # We're running on Android
        try:
            from android.storage import app_storage_path
            from android.permissions import request_permissions, Permission
            
            # Request necessary permissions
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])
            
            # Set Android-specific paths
            os.environ["ANDROID_STORAGE"] = app_storage_path()
        except ImportError:
            # Android libraries not available, continue without them
            pass
    
    # Import and run the main application
    from app import main
    main()