"""Android external storage utilities."""

import os
import sys


def get_external_data_dir(fallback: str) -> str:
    """Get Android external files directory that persists across app updates.

    Args:
        fallback: Directory to return if JNI call fails.
    """
    try:
        from jnius import autoclass

        # In the main app process the context comes from the Activity; in p4a
        # service processes (download/extraction) there is no Activity, so
        # PythonActivity.mActivity is None and we must use PythonService.mService
        # instead. Without this, service processes fall back to internal private
        # storage and write error.log/NSZ diagnostics to a different, invisible
        # file than the one the app and in-app viewer read.
        context = None
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            if PythonActivity.mActivity is not None:
                context = PythonActivity.mActivity.getApplicationContext()
        except Exception:
            context = None
        if context is None:
            PythonService = autoclass("org.kivy.android.PythonService")
            if PythonService.mService is not None:
                context = PythonService.mService.getApplicationContext()
        if context is None:
            print(
                "get_external_data_dir: no Activity or Service context, using fallback",
                file=sys.stderr,
                flush=True,
            )
            return fallback
        ext_dir = context.getExternalFilesDir(None)
        if ext_dir:
            return ext_dir.getAbsolutePath()
        print(
            "get_external_data_dir: external dir is null, using fallback",
            file=sys.stderr,
            flush=True,
        )
        return fallback
    except Exception as e:
        print(
            f"get_external_data_dir: JNI failed ({e}), using fallback",
            file=sys.stderr,
            flush=True,
        )
        return fallback
