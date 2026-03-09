"""
Native Android file/folder picker using SAF (Storage Access Framework).

Uses ACTION_OPEN_DOCUMENT_TREE for folder selection and ACTION_OPEN_DOCUMENT
for file selection. Results are posted as pygame events to integrate with the
existing main loop.
"""

import os
import threading

import pygame
from utils.logging import log_error

# Custom pygame event for picker results
PICKER_RESULT_EVENT = pygame.USEREVENT + 1

# Request codes for onActivityResult
_REQUEST_FOLDER = 9001
_REQUEST_FILE = 9002

# Maps selection_type -> "folder" or "file"
SELECTION_CONFIG = {
    # Folder selections
    "work_dir": "folder",
    "roms_dir": "folder",
    "custom_folder": "folder",
    "esde_media_path": "folder",
    "esde_gamelists_path": "folder",
    "retroarch_thumbnails": "folder",
    "add_system_folder": "folder",
    "ia_download_folder": "folder",
    "ia_collection_folder": "folder",
    "dedupe_folder": "folder",
    "rename_folder": "folder",
    "ghost_cleaner_folder": "folder",
    "scraper_batch_folder": "folder",
    # File selections
    "archive_json": "file",
    "nsz_keys": "file",
    "nsz_converter": "file",
    "extract_zip": "file",
    "extract_rar": "file",
    "extract_7z": "file",
    "we_patcher_rom": "file",
    "iss_patcher_rom": "file",
    "nhl94_patcher_rom": "file",
    "nhl94_gen_patcher_rom": "file",
    "nhl07_patcher_rom": "file",
    "kgj_mlb_patcher_rom": "file",
    "nbalive95_patcher_rom": "file",
    "mvp_psp_patcher_rom": "file",
}

# MIME types for file picker
_MIME_TYPES = {
    "archive_json": ["application/json"],
    "nsz_keys": ["*/*"],
    "nsz_converter": ["*/*"],
    "extract_zip": ["application/zip"],
    "extract_rar": ["*/*"],
    "extract_7z": ["*/*"],
    "we_patcher_rom": ["*/*"],
    "iss_patcher_rom": ["*/*"],
    "nhl94_patcher_rom": ["*/*"],
    "nhl94_gen_patcher_rom": ["*/*"],
    "nhl07_patcher_rom": ["*/*"],
    "kgj_mlb_patcher_rom": ["*/*"],
    "nbalive95_patcher_rom": ["*/*"],
    "mvp_psp_patcher_rom": ["*/*"],
}

# Post-selection extension validation for types using */* MIME
VALID_EXTENSIONS = {
    "nsz_keys": [".keys"],
    "nsz_converter": [".nsz", ".nsp", ".xci", ".xcz"],
    "extract_rar": [".rar"],
    "extract_7z": [".7z"],
    "we_patcher_rom": [".bin", ".cue", ".img", ".zip"],
    "iss_patcher_rom": [".sfc", ".smc", ".zip"],
    "nhl94_patcher_rom": [".sfc", ".smc", ".zip"],
    "nhl94_gen_patcher_rom": [".bin", ".md", ".gen", ".zip"],
    "nhl07_patcher_rom": [".iso", ".cso", ".zip"],
    "kgj_mlb_patcher_rom": [".sfc", ".smc", ".zip"],
    "nbalive95_patcher_rom": [".bin", ".md", ".gen", ".zip"],
    "mvp_psp_patcher_rom": [".iso", ".cso", ".zip"],
}


class AndroidFilePicker:
    """Launches native Android SAF pickers and posts results as pygame events."""

    def __init__(self):
        self._current_selection_type = None

    def pick_folder(self, selection_type, initial_uri=None):
        """Launch ACTION_OPEN_DOCUMENT_TREE."""
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        self._current_selection_type = selection_type
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)

        if initial_uri:
            DocumentsContract = autoclass(
                "android.provider.DocumentsContract"
            )
            intent.putExtra(
                DocumentsContract.EXTRA_INITIAL_URI,
                Uri.parse(initial_uri),
            )

        activity = PythonActivity.mActivity
        from android.activity import bind as bind_activity_result

        bind_activity_result(on_activity_result=self._on_activity_result)
        activity.startActivityForResult(intent, _REQUEST_FOLDER)

    def pick_file(self, selection_type, mime_types=None, initial_uri=None):
        """Launch ACTION_OPEN_DOCUMENT."""
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        self._current_selection_type = selection_type
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)

        if mime_types and len(mime_types) == 1:
            intent.setType(mime_types[0])
        elif mime_types and len(mime_types) > 1:
            intent.setType("*/*")
            intent.putExtra(Intent.EXTRA_MIME_TYPES, mime_types)
        else:
            intent.setType("*/*")

        if initial_uri:
            DocumentsContract = autoclass(
                "android.provider.DocumentsContract"
            )
            intent.putExtra(
                DocumentsContract.EXTRA_INITIAL_URI,
                Uri.parse(initial_uri),
            )

        activity = PythonActivity.mActivity
        from android.activity import bind as bind_activity_result

        bind_activity_result(on_activity_result=self._on_activity_result)
        activity.startActivityForResult(intent, _REQUEST_FILE)

    def _on_activity_result(self, request_code, result_code, intent):
        """Handle SAF picker result — runs on Android UI thread.

        Must be lightweight to avoid blocking SDL surface recreation (ANR).
        Extract URI string immediately, then defer heavy processing to a
        background thread.
        """
        try:
            selection_type = self._current_selection_type
            uri_str = None
            is_file = request_code == _REQUEST_FILE

            # RESULT_OK = -1 on Android; avoid autoclass call here to
            # reduce JNI work on the UI thread during surface restoration.
            if result_code == -1 and intent is not None:
                try:
                    uri = intent.getData()
                    if uri is not None:
                        uri_str = uri.toString()
                except Exception as e:
                    log_error(f"[file_picker] getData error: {e}")

            # Defer heavy URI-to-path resolution off the UI thread
            def _resolve():
                path = None
                if uri_str:
                    try:
                        from jnius import autoclass as ac

                        Uri = ac("android.net.Uri")
                        uri = Uri.parse(uri_str)
                        path = self._uri_to_path(uri)
                        if path is None and is_file:
                            path = self._copy_uri_to_cache(uri)
                    except Exception as e:
                        log_error(f"[file_picker] resolve error: {e}")

                try:
                    evt = pygame.event.Event(
                        PICKER_RESULT_EVENT,
                        {"path": path, "selection_type": selection_type},
                    )
                    pygame.event.post(evt)
                except Exception as e:
                    log_error(f"[file_picker] event post error: {e}")

            threading.Thread(target=_resolve, daemon=True).start()

        except Exception as e:
            log_error(f"[file_picker] _on_activity_result error: {e}")

    def _uri_to_path(self, uri):
        """Convert a content:// URI to a filesystem path, if possible."""
        try:
            uri_str = uri.toString()
            log_error(f"[file_picker] URI: {uri_str}")

            # Handle external storage document URIs
            from jnius import autoclass

            DocumentsContract = autoclass(
                "android.provider.DocumentsContract"
            )

            if DocumentsContract.isDocumentUri(
                self._get_context(), uri
            ) or "document" in uri_str:
                # Extract document ID — e.g. "primary:Download/roms"
                try:
                    doc_id = DocumentsContract.getDocumentId(uri)
                except Exception:
                    doc_id = DocumentsContract.getTreeDocumentId(uri)

                log_error(f"[file_picker] doc_id: {doc_id}")

                if ":" in doc_id:
                    storage_type, rel_path = doc_id.split(":", 1)
                    if storage_type == "primary":
                        Environment = autoclass(
                            "android.os.Environment"
                        )
                        root = (
                            Environment.getExternalStorageDirectory()
                            .getAbsolutePath()
                        )
                        full_path = os.path.join(root, rel_path)
                        if os.path.exists(full_path):
                            return full_path
                    else:
                        # SD card or other volume
                        # Try /storage/<volume_id>/
                        sd_path = os.path.join(
                            "/storage", storage_type, rel_path
                        )
                        if os.path.exists(sd_path):
                            return sd_path

            # Fallback: try file:// scheme
            if uri_str.startswith("file://"):
                path = uri_str[7:]
                if os.path.exists(path):
                    return path

        except Exception as e:
            log_error(f"[file_picker] URI conversion error: {e}")

        return None

    def _copy_uri_to_cache(self, uri):
        """Copy file from content URI to app cache dir (fallback for non-local providers)."""
        try:
            from jnius import autoclass

            context = self._get_context()
            resolver = context.getContentResolver()
            input_stream = resolver.openInputStream(uri)

            if input_stream is None:
                return None

            # Try to get a filename from the URI
            filename = self._get_display_name(uri) or "picked_file"
            cache_dir = context.getCacheDir().getAbsolutePath()
            dest_path = os.path.join(cache_dir, filename)

            # Read and write
            BufferedInputStream = autoclass("java.io.BufferedInputStream")
            bis = BufferedInputStream(input_stream)

            with open(dest_path, "wb") as f:
                buf = bytearray(8192)
                while True:
                    n = bis.read(buf, 0, len(buf))
                    if n == -1:
                        break
                    f.write(bytes(buf[:n]))

            bis.close()
            input_stream.close()

            log_error(f"[file_picker] Cached URI to: {dest_path}")
            return dest_path

        except Exception as e:
            log_error(f"[file_picker] Cache copy error: {e}")
            return None

    def _get_display_name(self, uri):
        """Query the display name of a content URI."""
        try:
            from jnius import autoclass

            context = self._get_context()
            resolver = context.getContentResolver()
            cursor = resolver.query(uri, None, None, None, None)
            if cursor is not None and cursor.moveToFirst():
                OpenableColumns = autoclass(
                    "android.provider.OpenableColumns"
                )
                idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if idx >= 0:
                    name = cursor.getString(idx)
                    cursor.close()
                    return name
                cursor.close()
        except Exception:
            pass
        return None

    def _get_context(self):
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        return PythonActivity.mActivity
