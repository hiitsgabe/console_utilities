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

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity.getApplicationContext()
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
