"""TDD (red) tests for GAB-10: Android external storage resolution.

get_external_data_dir falls back silently when the JNI call fails or when
getExternalFilesDir returns null. A silent fallback to app-private storage is
exactly how a large extraction ends up on the wrong (smaller) volume without
any diagnostic. These tests require a stderr warning on every fallback.

Pinned NOT-YET-IMPLEMENTED behavior in droid.storage:
    - On JNI failure -> return fallback AND warn on stderr.
    - On null external dir -> return fallback AND warn on stderr.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.argv = sys.argv[:1]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from droid import storage  # noqa: E402


def test_returns_fallback_and_warns_on_jni_failure(monkeypatch, capsys):
    # Ensure jnius is unavailable so the import inside the function raises.
    monkeypatch.setitem(sys.modules, "jnius", None)

    result = storage.get_external_data_dir("/my/fallback")

    captured = capsys.readouterr()
    assert result == "/my/fallback"
    assert "fallback" in captured.err.lower()


def test_resolves_via_service_context_when_no_activity(monkeypatch):
    # p4a service process: PythonActivity.mActivity is None, but the context is
    # available via PythonService.mService. Must resolve the external dir there
    # instead of falling back to internal storage (the NSZ log-loss bug).
    ext = SimpleNamespace(getAbsolutePath=lambda: "/sdcard/ext/files")
    context = SimpleNamespace(getExternalFilesDir=lambda arg: ext)
    service = SimpleNamespace(getApplicationContext=lambda: context)
    python_activity = SimpleNamespace(mActivity=None)
    python_service = SimpleNamespace(mService=service)

    def fake_autoclass(name):
        return python_service if "PythonService" in name else python_activity

    monkeypatch.setitem(sys.modules, "jnius", SimpleNamespace(autoclass=fake_autoclass))

    result = storage.get_external_data_dir("/should/not/use")

    assert result == "/sdcard/ext/files"


def test_returns_fallback_when_ext_dir_null(monkeypatch, capsys):
    context = SimpleNamespace(getExternalFilesDir=lambda arg: None)
    activity = SimpleNamespace(getApplicationContext=lambda: context)
    python_activity = SimpleNamespace(mActivity=activity)

    fake_jnius = SimpleNamespace(autoclass=lambda name: python_activity)
    monkeypatch.setitem(sys.modules, "jnius", fake_jnius)

    result = storage.get_external_data_dir("/fb2")

    captured = capsys.readouterr()
    assert result == "/fb2"
    assert "fallback" in captured.err.lower()
