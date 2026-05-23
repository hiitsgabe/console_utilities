"""Tests for SyncthingService.is_running candidate-URL probing.

Regression: on Android, Catfriend1's Syncthing-Fork commonly serves the GUI
only over HTTPS (self-signed) or only over 127.0.0.1, and the system network
policy may block cleartext HTTP from our app. The previous is_running tried
only `http://localhost:8384` and silently returned False on any exception, so
the Syncthing screen would always show "not found" even when the service was
reachable. is_running now probes HTTP/HTTPS and localhost/127.0.0.1, remembers
the working URL, and applies the right TLS verify flag to subsequent calls.
"""

import importlib.util
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_spec = importlib.util.spec_from_file_location(
    "syncthing_service",
    os.path.join(os.path.dirname(__file__), "..", "src", "services", "syncthing_service.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SyncthingService = _mod.SyncthingService


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _responder(success_url, status=200, success_verify=None):
    """Build a fake requests.get that succeeds only for `success_url`.

    If success_verify is given, the call must also pass verify=success_verify.
    """

    def fake_get(url, headers=None, timeout=None, verify=None, **kwargs):
        base = url.rsplit("/rest/", 1)[0]
        if base == success_url and (
            success_verify is None or verify == success_verify
        ):
            return _FakeResponse(status)
        raise ConnectionError(f"refused: {base}")

    return fake_get


def test_running_when_default_http_succeeds():
    """Standard case: http://localhost:8384 responds 200, no switching needed."""
    svc = SyncthingService(api_key="k")
    with patch.object(_mod.requests, "get", _responder("http://localhost:8384")):
        assert svc.is_running() is True
    assert svc.api_url == "http://localhost:8384"
    assert svc._verify is True


def test_falls_back_to_127_when_localhost_unreachable():
    """Some environments (incl. some Android setups) fail localhost resolution."""
    svc = SyncthingService(api_key="k")
    with patch.object(_mod.requests, "get", _responder("http://127.0.0.1:8384")):
        assert svc.is_running() is True
    assert svc.api_url == "http://127.0.0.1:8384"
    assert svc._verify is True


def test_falls_back_to_https_when_http_blocked():
    """Catfriend1 Android default: HTTPS only. Probe must reach it with verify=False."""
    svc = SyncthingService(api_key="k")
    fake = _responder("https://localhost:8384", success_verify=False)
    with patch.object(_mod.requests, "get", fake):
        assert svc.is_running() is True
    assert svc.api_url == "https://localhost:8384"
    assert svc._verify is False


def test_falls_back_to_https_127():
    """Worst case combo: cleartext blocked AND localhost broken."""
    svc = SyncthingService(api_key="k")
    fake = _responder("https://127.0.0.1:8384", success_verify=False)
    with patch.object(_mod.requests, "get", fake):
        assert svc.is_running() is True
    assert svc.api_url == "https://127.0.0.1:8384"
    assert svc._verify is False


def test_403_counts_as_running():
    """Auth-required response means Syncthing is up but key is missing/wrong."""
    svc = SyncthingService(api_key="")
    with patch.object(
        _mod.requests, "get", _responder("http://localhost:8384", status=403)
    ):
        assert svc.is_running() is True


def test_all_candidates_failing_returns_false():
    """When nothing responds, return False (and the user sees 'not found')."""
    svc = SyncthingService(api_key="k")

    def always_fail(*a, **kw):
        raise ConnectionError("nope")

    with patch.object(_mod.requests, "get", always_fail):
        assert svc.is_running() is False
    # api_url should remain at its initial default, not mutated by a failed probe.
    assert svc.api_url == "http://localhost:8384"


def test_already_working_url_probed_first():
    """A second call to is_running should hit the remembered URL first."""
    svc = SyncthingService(api_key="k")
    svc.api_url = "https://localhost:8384"
    svc._verify = False

    calls = []

    def tracker(url, **kw):
        calls.append((url, kw.get("verify")))
        if url.startswith("https://localhost:8384"):
            return _FakeResponse(200)
        raise ConnectionError("not this one")

    with patch.object(_mod.requests, "get", tracker):
        assert svc.is_running() is True
    # First probe must be the remembered URL.
    assert calls[0][0].startswith("https://localhost:8384")
    assert calls[0][1] is False
