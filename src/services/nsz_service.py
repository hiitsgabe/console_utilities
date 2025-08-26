"""
NSZ Service
Handles Nintendo Switch NSZ file decompression using nsz library directly
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple


class NSZService:
    """Service for handling NSZ file decompression using nsz library"""
    
    def __init__(self):
        self.keys_path = None
        self._setup_keys_environment()
    
    def _setup_keys_environment(self):
        """Setup Nintendo Switch keys environment"""
        # Check for keys in common locations
        default_keys_paths = [
            os.path.expanduser("~/.switch/prod.keys"),
            os.path.join(os.getcwd(), "keys.txt"),
            os.path.join(os.getcwd(), "prod.keys")
        ]
        
        for path in default_keys_paths:
            if os.path.exists(path):
                self.keys_path = path
                break
    
    def set_keys_path(self, keys_path: str) -> bool:
        """
        Set the path to Nintendo Switch keys file
        
        Args:
            keys_path: Path to keys file or directory containing prod.keys
            
        Returns:
            True if keys file is found and valid, False otherwise
        """
        actual_keys_path = None
        
        if os.path.isfile(keys_path) and keys_path.lower().endswith('.keys'):
            # Direct file path
            actual_keys_path = keys_path
        elif os.path.isdir(keys_path):
            # Directory path, look for prod.keys
            prod_keys_path = os.path.join(keys_path, "prod.keys")
            if os.path.exists(prod_keys_path):
                actual_keys_path = prod_keys_path
        
        if actual_keys_path and self._validate_keys_file(actual_keys_path):
            self.keys_path = actual_keys_path
            self._ensure_keys_in_switch_dir()
            return True
        
        return False
    
    def _validate_keys_file(self, keys_path: str) -> bool:
        """
        Basic validation of Nintendo Switch keys file
        
        Args:
            keys_path: Path to keys file
            
        Returns:
            True if file appears to be valid keys file
        """
        try:
            with open(keys_path, 'r') as f:
                content = f.read()
            
            # Check for key-value pairs with hex values
            lines = content.strip().split('\n')
            valid_lines = 0
            
            for line in lines:
                line = line.strip()
                if '=' in line and len(line) > 10:
                    key_name, key_value = line.split('=', 1)
                    if len(key_value) == 32:  # 128-bit key
                        try:
                            int(key_value, 16)  # Validate hex
                            valid_lines += 1
                        except ValueError:
                            pass
            
            return valid_lines > 0
            
        except Exception:
            return False
    
    def _ensure_keys_in_switch_dir(self):
        """Copy keys to expected ~/.switch/prod.keys location if needed"""
        if not self.keys_path:
            return
        
        switch_dir = os.path.expanduser("~/.switch")
        expected_keys = os.path.join(switch_dir, "prod.keys")
        
        if not os.path.exists(switch_dir):
            os.makedirs(switch_dir, exist_ok=True)
        
        if not os.path.exists(expected_keys) and self.keys_path != expected_keys:
            shutil.copy2(self.keys_path, expected_keys)
    
    def is_available(self) -> bool:
        """
        Check if NSZ decompression is available
        
        Returns:
            True if nsz library and keys are available
        """
        try:
            # Try importing nsz to verify it's available
            import nsz
            return self.keys_path is not None and os.path.isfile(self.keys_path)
        except (ImportError, EOFError, Exception):
            return False
    
    def get_requirements_status(self) -> dict:
        """
        Get status of NSZ service requirements
        
        Returns:
            Dictionary with requirement status information
        """
        nsz_available = False
        try:
            import nsz
            nsz_available = True
        except (ImportError, EOFError, Exception):
            pass
        
        return {
            'nsz_library': {
                'available': nsz_available,
                'message': 'nsz library imported successfully' if nsz_available else 'nsz library not found'
            },
            'keys_file': {
                'available': self.keys_path is not None and os.path.isfile(self.keys_path),
                'path': self.keys_path
            },
            'ready': self.is_available()
        }
    
    def decompress_nsz(self, nsz_file_path: str, output_dir: str) -> Tuple[bool, str]:
        """
        Decompress an NSZ file to NSP format using nsz library directly
        
        Args:
            nsz_file_path: Path to the NSZ file
            output_dir: Directory to output the decompressed NSP file
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_available():
            return False, "NSZ service not available. Check nsz library and keys file."
        
        if not os.path.isfile(nsz_file_path):
            return False, f"NSZ file not found: {nsz_file_path}"
        
        if not nsz_file_path.lower().endswith('.nsz'):
            return False, "File is not an NSZ file"
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Store original working directory and argv
        original_cwd = os.getcwd()
        original_argv = sys.argv.copy()
        
        try:
            # Change to output directory for decompression
            os.chdir(output_dir)
            
            # Ensure keys are in place
            self._ensure_keys_in_switch_dir()
            
            # Create Path objects for nsz decompress function
            nsz_path = Path(nsz_file_path).resolve()
            output_path = Path(output_dir).resolve()
            
            # Import nsz decompress function only when needed
            from nsz import decompress
            
            # Call NSZ decompress function directly
            # Parameters: filePath, outputDir, fixPadding
            decompress(nsz_path, output_path, False)
            
            # Check for output NSP file
            nsz_filename = os.path.basename(nsz_file_path)
            expected_nsp = nsz_filename.replace('.nsz', '.nsp')
            nsp_path = os.path.join(output_dir, expected_nsp)
            
            if os.path.isfile(nsp_path):
                return True, f"Successfully decompressed to {nsp_path}"
            else:
                # Check for any NSP files created
                nsp_files = [f for f in os.listdir(output_dir) if f.endswith('.nsp')]
                if nsp_files:
                    return True, f"Successfully decompressed. Created: {', '.join(nsp_files)}"
                else:
                    return False, "Decompression completed but no NSP files found"
                    
        except Exception as e:
            return False, f"NSZ decompression failed: {str(e)}"
        finally:
            # Restore original working directory and argv
            os.chdir(original_cwd)
            sys.argv = original_argv
    
    def get_decompressed_size_estimate(self, nsz_file_path: str) -> Optional[int]:
        """
        Estimate the decompressed size of an NSZ file
        NSZ files are typically 30-50% smaller than NSP files
        
        Args:
            nsz_file_path: Path to the NSZ file
            
        Returns:
            Estimated decompressed size in bytes, or None if unavailable
        """
        if not os.path.isfile(nsz_file_path):
            return None
        
        nsz_size = os.path.getsize(nsz_file_path)
        # Estimate NSP size as 2x NSZ size (conservative estimate)
        return nsz_size * 2
    
    def install_instructions(self) -> str:
        """
        Get instructions for setting up NSZ decompression
        
        Returns:
            String with setup instructions
        """
        return """
To use NSZ decompression, you need:

1. Install the nsz library:
   pip install nsz

2. Obtain Nintendo Switch keys:
   - You need prod.keys from your own Switch console
   - Place the keys file in one of these locations:
     * ~/.switch/prod.keys
     * Configure custom path in settings
   
3. Usage:
   - NSZ files will be automatically decompressed to NSP format
   - Original NSZ files can be kept or removed after decompression
   - Decompressed NSP files are larger than NSZ files

Important: You must legally own the games and extract keys from your own console.
"""