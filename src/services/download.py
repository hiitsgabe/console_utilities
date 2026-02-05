"""
Download service for Console Utilities.
Handles file downloads, extraction, and processing.
"""

import os
import time
import traceback
from typing import Dict, Any, List, Set, Optional, Callable
from urllib.parse import urljoin
from zipfile import ZipFile

import requests

from utils.logging import log_error
from utils.formatting import format_size
from utils.nsz import decompress_nsz_file
from constants import SCRIPT_DIR


# Type alias for progress callback: (message: str, percent: int, downloaded: int, total: int, speed: float) -> None
ProgressCallback = Callable[[str, int, int, int, float], None]


class DownloadService:
    """
    Manages file downloads and processing.

    Handles direct URL downloads, system-based downloads,
    ZIP extraction, and NSZ decompression.
    """

    def __init__(self, settings: Dict[str, Any]):
        """
        Initialize download service.

        Args:
            settings: Application settings dictionary
        """
        self.settings = settings
        self._cancelled = False

    def cancel(self):
        """Cancel the current download operation."""
        self._cancelled = True

    def reset(self):
        """Reset cancellation state."""
        self._cancelled = False

    @property
    def work_dir(self) -> str:
        """Get the work directory from settings."""
        return self.settings.get("work_dir", os.path.join(SCRIPT_DIR, "downloads"))

    @property
    def roms_dir(self) -> str:
        """Get the ROMs directory from settings."""
        return self.settings.get("roms_dir", os.path.join(SCRIPT_DIR, "roms"))

    def download_direct_file(
        self,
        url: str,
        progress_callback: Optional[ProgressCallback] = None,
        message_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Download a file directly to the work directory.

        Args:
            url: URL to download from
            progress_callback: Callback for progress updates
            message_callback: Callback for status messages

        Returns:
            True if successful, False otherwise
        """
        self.reset()

        def show_message(msg: str):
            if message_callback:
                message_callback(msg)
            else:
                print(msg)

        try:
            # Validate URL
            if not url or not url.strip():
                show_message("Error: No URL provided")
                return False

            if not (url.startswith('http://') or url.startswith('https://')):
                show_message("Error: URL must start with http:// or https://")
                return False

            show_message("Starting download...")

            # Create download directory
            py_downloads_dir = os.path.join(self.work_dir, "py_downloads")
            os.makedirs(py_downloads_dir, exist_ok=True)

            # Extract filename from URL
            parsed_url = url.rstrip('/')
            filename = parsed_url.split('/')[-1]
            if not filename or '.' not in filename:
                filename = "downloaded_file"

            file_path = os.path.join(py_downloads_dir, filename)

            # Download file
            try:
                response = requests.get(url, stream=True, timeout=30, allow_redirects=True)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                start_time = time.time()

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._cancelled:
                            f.close()
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            show_message("Download cancelled")
                            return False

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Calculate speed
                            elapsed_time = time.time() - start_time
                            speed = downloaded / elapsed_time if elapsed_time > 0 else 0

                            if progress_callback:
                                percent = int((downloaded / total_size) * 100) if total_size > 0 else 0
                                progress_callback(
                                    f"Downloading {filename}",
                                    percent, downloaded, total_size, speed
                                )

                show_message(f"Downloaded to work directory: {filename}")
                return True

            except requests.exceptions.RequestException as req_error:
                error_msg = "Network error downloading file"
                if hasattr(req_error, 'response') and req_error.response:
                    error_msg += f" (HTTP {req_error.response.status_code})"
                log_error(error_msg, type(req_error).__name__, traceback.format_exc())
                show_message("Error: Network error - check URL")
                return False

        except Exception as e:
            log_error("Error downloading file", type(e).__name__, traceback.format_exc())
            show_message("Download failed. Check error log for details.")
            return False

    def download_files(
        self,
        system_data: Dict[str, Any],
        all_systems_data: List[Dict[str, Any]],
        game_list: List[Any],
        selected_indices: Set[int],
        progress_callback: Optional[ProgressCallback] = None,
        message_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Download selected files from a system.

        Args:
            system_data: Current system configuration
            all_systems_data: All systems data (for WORK_DIR reference)
            game_list: List of all games
            selected_indices: Set of selected game indices
            progress_callback: Callback for progress updates
            message_callback: Callback for status messages

        Returns:
            True if all downloads successful, False if cancelled or error
        """
        self.reset()

        def show_message(msg: str):
            if message_callback:
                message_callback(msg)
            else:
                print(msg)

        try:
            formats = system_data.get('file_format', [])

            # Determine target ROM folder
            system_name = system_data['name']
            system_settings = self.settings.get("system_settings", {})
            custom_folder = system_settings.get(system_name, {}).get('custom_folder', '')

            if custom_folder and os.path.exists(custom_folder):
                roms_folder = custom_folder
            else:
                roms_folder = os.path.join(self.roms_dir, system_data['roms_folder'])

            os.makedirs(roms_folder, exist_ok=True)

            # Get selected files
            selected_files = [game_list[i] for i in selected_indices]
            total = len(selected_files)

            for idx, game_item in enumerate(selected_files):
                if self._cancelled:
                    show_message("Download cancelled")
                    return False

                log_error(f"Downloading game: {game_item}")

                # Extract filename
                filename = self._get_filename(game_item)

                # Calculate overall progress
                overall_progress = int((idx / total) * 100)
                if progress_callback:
                    progress_callback(
                        f"Downloading {filename} ({idx+1}/{total})",
                        overall_progress, 0, 0, 0
                    )

                # Get download URL
                url = self._get_download_url(system_data, game_item, filename)
                if not url:
                    continue

                # Ensure filename has extension
                if 'download_url' in system_data and '.' not in filename:
                    fmt = formats[0] if formats else ''
                    filename = filename + fmt

                try:
                    # Download file
                    file_path = self._download_single_file(
                        url, filename, system_data, idx, total, progress_callback
                    )

                    if file_path is None:
                        # Download was cancelled
                        return False

                    if file_path:
                        # Process downloaded file
                        def file_progress(text: str, percent: int):
                            if progress_callback:
                                progress_callback(text, percent, 0, 0, 0)

                        success = self.process_downloaded_file(
                            file_path, filename, system_data, roms_folder, file_progress
                        )

                        if not success and not self._cancelled:
                            # Move original file if processing failed
                            try:
                                if any(filename.endswith(ext) for ext in formats):
                                    dst_path = os.path.join(roms_folder, filename)
                                    os.rename(file_path, dst_path)
                                    print(f"Moved unprocessed file: {filename}")
                            except Exception as e:
                                print(f"Failed to move unprocessed file: {e}")

                except Exception as e:
                    log_error(f"Failed to download {filename}", type(e).__name__, traceback.format_exc())

            return True

        except Exception as e:
            log_error(f"Error in download_files for system", type(e).__name__, traceback.format_exc())
            return False

    def process_downloaded_file(
        self,
        file_path: str,
        filename: str,
        system_data: Dict[str, Any],
        roms_folder: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> bool:
        """
        Process a downloaded file (extract, decompress, move).

        Args:
            file_path: Path to downloaded file
            filename: Name of the file
            system_data: System configuration
            roms_folder: Target ROM folder
            progress_callback: Callback for progress updates (text, percent)

        Returns:
            True if successful, False otherwise
        """
        try:
            formats = system_data.get('file_format', [])

            def update_progress(text: str, percent: int = 0):
                if progress_callback:
                    progress_callback(text, percent)
                else:
                    print(f"{text} - {percent}%")

            # Handle ZIP extraction
            if filename.endswith(".zip") and system_data.get('should_unzip', False):
                update_progress(f"Extracting {filename}...", 0)

                with ZipFile(file_path, 'r') as zip_ref:
                    total_files = len(zip_ref.namelist())
                    extracted_files = 0

                    for file_info in zip_ref.infolist():
                        zip_ref.extract(file_info, self.work_dir)
                        extracted_files += 1

                        if extracted_files % 10 == 0 or file_info.file_size > 1024*1024:
                            progress = int((extracted_files / total_files) * 100)
                            update_progress(
                                f"Extracting {filename}... ({extracted_files}/{total_files})",
                                progress
                            )

                    update_progress(f"Extracting {filename}... Complete", 100)

                os.remove(file_path)

            elif filename.endswith(".nsz"):
                update_progress(f"Attempting NSZ decompression for {filename}...", 0)

                keys_path = self.settings.get("nsz_keys_path", "")
                nsz_success = decompress_nsz_file(
                    file_path, self.work_dir, keys_path, update_progress
                )

                if nsz_success:
                    # Move NSP files
                    for file in os.listdir(self.work_dir):
                        if file.endswith('.nsp'):
                            src_path = os.path.join(self.work_dir, file)
                            dst_path = os.path.join(roms_folder, file)
                            os.rename(src_path, dst_path)
                            print(f"Moved decompressed NSP: {file}")

                    if os.path.exists(file_path):
                        os.remove(file_path)

                    return True
                else:
                    return False

            # Move compatible files to ROMs folder
            update_progress("Moving files to ROMS folder...", 0)

            files_moved = 0
            for f in os.listdir(self.work_dir):
                if any(f.endswith(ext) for ext in formats):
                    src_path = os.path.join(self.work_dir, f)
                    dst_path = os.path.join(roms_folder, f)
                    os.rename(src_path, dst_path)
                    files_moved += 1
                    print(f"Moved file: {f}")

            # Clean up work directory
            for f in os.listdir(self.work_dir):
                file_to_remove = os.path.join(self.work_dir, f)
                if os.path.isfile(file_to_remove):
                    os.remove(file_to_remove)

            update_progress("Processing complete", 100)
            return True

        except Exception as e:
            log_error(f"Error processing file {filename}: {e}")
            if progress_callback:
                progress_callback(f"Error processing {filename}: {e}", 0)
            return False

    def _get_filename(self, game_item: Any) -> str:
        """Extract filename from game item."""
        if isinstance(game_item, dict):
            if 'name' in game_item:
                return game_item['name']
            elif 'filename' in game_item:
                return game_item['filename']
            else:
                return str(game_item)
        return str(game_item)

    def _get_download_url(
        self,
        system_data: Dict[str, Any],
        game_item: Any,
        filename: str
    ) -> Optional[str]:
        """Get download URL for a game item."""
        if 'download_url' in system_data:
            return game_item.get('href') if isinstance(game_item, dict) else None
        elif 'url' in system_data:
            if isinstance(game_item, dict) and 'href' in game_item:
                return urljoin(system_data['url'], game_item['href'])
            else:
                return urljoin(system_data['url'], filename)
        return None

    def _download_single_file(
        self,
        url: str,
        filename: str,
        system_data: Dict[str, Any],
        idx: int,
        total: int,
        progress_callback: Optional[ProgressCallback]
    ) -> Optional[str]:
        """
        Download a single file.

        Returns:
            File path if successful, None if cancelled, raises exception on error
        """
        # Prepare authentication
        headers = {}
        cookies = {}

        if 'auth' in system_data:
            auth_config = system_data['auth']
            if auth_config.get('cookies', False) and 'token' in auth_config:
                cookie_name = auth_config.get('cookie_name', 'auth_token')
                cookies[cookie_name] = auth_config['token']
            elif 'token' in auth_config:
                headers['Authorization'] = f"Bearer {auth_config['token']}"

        response = requests.get(url, stream=True, timeout=10, headers=headers, cookies=cookies)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        last_update = start_time
        last_downloaded = 0

        file_path = os.path.join(self.work_dir, filename)
        os.makedirs(self.work_dir, exist_ok=True)

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                if self._cancelled:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return None

                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update speed every 500ms
                    current_time = time.time()
                    if current_time - last_update >= 0.5:
                        speed = (downloaded - last_downloaded) * 2
                        last_downloaded = downloaded
                        last_update = current_time

                        if progress_callback:
                            file_progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
                            current_progress = int(((idx + (file_progress / 100)) / total) * 100)
                            progress_callback(
                                f"Downloading {filename} ({idx+1}/{total})",
                                current_progress, downloaded, total_size, speed
                            )

        return file_path


# Factory function
def create_download_service(settings: Dict[str, Any]) -> DownloadService:
    """Create a download service instance."""
    return DownloadService(settings)
