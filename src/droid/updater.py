"""
Android auto-update: download APK from GitHub release and launch system installer.
"""

import os
import threading
import traceback

import pygame
import requests

from utils.logging import log_error

# Custom pygame event for triggering APK install on the main thread.
# jnius calls must happen on the main thread (or a JVM-attached thread);
# posting a pygame event is the safest way to ensure that.
APK_INSTALL_EVENT = pygame.USEREVENT + 99


def apply_android_update(
    asset_url: str, on_progress=None, on_complete=None, on_error=None
):
    """
    Download and apply an Android APK update.

    Downloads consoleutils.apk from GitHub and launches the system
    package installer via Intent.

    Args:
        asset_url: URL to download the consoleutils.apk asset
        on_progress: Callback(progress_float, status_str) for progress updates
        on_complete: Callback() when update is ready to install
        on_error: Callback(error_str) on failure
    """

    def _do_update():
        cache_dir = None
        try:
            if on_progress:
                on_progress(0.0, "Downloading update...")

            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            cache_dir = PythonActivity.mActivity.getCacheDir().getAbsolutePath()

            final_apk = os.path.join(cache_dir, "console_utilities_update.apk")

            # Stream download with progress (SSL fallback for Android cert issues)
            dl_headers = {"User-Agent": "ConsoleUtilities/1.0"}
            try:
                response = requests.get(
                    asset_url, stream=True, timeout=(15, 120), headers=dl_headers
                )
                response.raise_for_status()
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                response = requests.get(
                    asset_url,
                    stream=True,
                    timeout=(15, 120),
                    headers=dl_headers,
                    verify=False,
                )
                response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(final_apk, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and on_progress:
                        on_progress(downloaded / total * 0.9, "Downloading update...")

            if on_progress:
                on_progress(0.9, "Launching installer...")

            # Post APK install to the main thread via pygame event.
            # jnius Intent calls must run on the main/UI thread.
            event = pygame.event.Event(APK_INSTALL_EVENT, apk_path=final_apk)
            pygame.event.post(event)

            if on_progress:
                on_progress(1.0, "Installing...")

            if on_complete:
                on_complete()

        except Exception as e:
            log_error("Android update failed", type(e).__name__, traceback.format_exc())
            if on_error:
                msg = str(e)
                if "SSLError" in type(e).__name__ or "SSL" in msg:
                    msg = "SSL connection error. Check your internet connection."
                elif "ConnectionError" in type(e).__name__:
                    msg = "Connection failed. Check your internet connection."
                elif "Timeout" in type(e).__name__:
                    msg = "Download timed out. Try again later."
                on_error(msg)

    thread = threading.Thread(target=_do_update, daemon=True)
    thread.start()
    return thread


def install_apk(apk_path: str):
    """Launch Android package installer for the given APK file.

    Must be called on the main thread (jnius requirement).
    """
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    FileProvider = autoclass("androidx.core.content.FileProvider")

    activity = PythonActivity.mActivity
    context = activity.getApplicationContext()

    apk_file = File(apk_path)
    authority = context.getPackageName() + ".fileprovider"
    apk_uri = FileProvider.getUriForFile(context, authority, apk_file)

    intent = Intent(Intent.ACTION_VIEW)
    intent.setDataAndType(apk_uri, "application/vnd.android.package-archive")
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    activity.startActivity(intent)
