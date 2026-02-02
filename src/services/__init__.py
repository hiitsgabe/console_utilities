"""
Services layer for Console Utilities.
Handles data loading, file operations, downloads, and image caching.
"""

from .data_loader import (
    load_main_systems_data,
    load_available_systems,
    load_added_systems,
    save_added_systems,
    add_system_to_added_systems,
    update_json_file_path,
    get_visible_systems,
    get_system_index_by_name,
)
from .file_listing import (
    list_files,
    filter_games_by_search,
    load_folder_contents,
    find_next_letter_index,
    get_file_size,
)
from .image_cache import (
    ImageCache,
    image_cache,
)
from .download import (
    DownloadService,
    create_download_service,
)

__all__ = [
    # Data loader
    'load_main_systems_data',
    'load_available_systems',
    'load_added_systems',
    'save_added_systems',
    'add_system_to_added_systems',
    'update_json_file_path',
    'get_visible_systems',
    'get_system_index_by_name',
    # File listing
    'list_files',
    'filter_games_by_search',
    'load_folder_contents',
    'find_next_letter_index',
    'get_file_size',
    # Image cache
    'ImageCache',
    'image_cache',
    # Download
    'DownloadService',
    'create_download_service',
]
