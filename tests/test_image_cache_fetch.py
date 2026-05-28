"""Tests for image_cache._fetch_image_bytes (GAB-11).

The image fetch path needs robust retry/backoff behaviour so transient
network problems (timeouts, dropped connections, 5xx) don't permanently fail
a thumbnail/boxart load, while permanent failures (404/403/etc.) fail fast
without wasting time on retries.

These tests pin the contract of the (to-be-implemented) helper:

    ic._fetch_image_bytes(session, url, *, connect=5, read=15, attempts=3) -> bytes | None

    - returns resp.content on 2xx
    - returns None WITHOUT retrying on permanent statuses {400,401,403,404,410}
    - retries on Timeout / ConnectionError / 5xx with backoff sleeps, up to
      `attempts` total, then returns None
    - calls session.get(url, timeout=(connect, read))
"""

import importlib.util
import os
import sys

# Headless: must be set BEFORE anything imports pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import requests  # noqa: E402  (for its exception classes)

# Load the module directly from its file so we don't trigger
# src/services/__init__.py (which chains into the nsz CLI and calls sys.exit).
# Importing as a module object still lets us monkeypatch its globals.
_spec = importlib.util.spec_from_file_location(
    "image_cache",
    os.path.join(os.path.dirname(__file__), "..", "src", "services", "image_cache.py"),
)
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)


class _FakeResp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Error", response=self
            )


class _FakeSession:
    """Fake session whose .get is driven by a list of scripted outcomes.

    Each item in `outcomes` is either a _FakeResp to return or an Exception
    instance to raise. If outcomes is exhausted, the last item repeats.
    Records every (args, kwargs) it was called with.
    """

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def get(self, url, timeout=None, **kwargs):
        self.calls.append({"url": url, "timeout": timeout, "kwargs": kwargs})
        idx = min(len(self.calls) - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[idx]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def call_count(self):
        return len(self.calls)


def _patch_sleep(monkeypatch):
    """Replace time.sleep with a recorder so tests are instant.

    Patching the `time` module's sleep covers both `import time; time.sleep`
    and `ic.time.sleep` usage in the implementation.
    """
    recorded = []

    def _fake_sleep(seconds):
        recorded.append(seconds)

    import time

    monkeypatch.setattr(time, "sleep", _fake_sleep)
    return recorded


def test_success_returns_bytes(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([_FakeResp(200, content=b"PNG")])

    result = ic._fetch_image_bytes(session, "http://x/a.png")

    assert result == b"PNG"
    assert session.call_count == 1


def test_404_fails_fast_no_retry(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([_FakeResp(404)])

    result = ic._fetch_image_bytes(session, "http://x/missing.png")

    assert result is None
    assert session.call_count == 1


def test_403_fails_fast_no_retry(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([_FakeResp(403)])

    result = ic._fetch_image_bytes(session, "http://x/forbidden.png")

    assert result is None
    assert session.call_count == 1


def test_timeout_retries_then_none(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([requests.exceptions.Timeout("slow")])

    result = ic._fetch_image_bytes(session, "http://x/a.png", attempts=3)

    assert result is None
    assert session.call_count == 3


def test_timeout_then_success(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession(
        [requests.exceptions.Timeout("slow"), _FakeResp(200, content=b"OK")]
    )

    result = ic._fetch_image_bytes(session, "http://x/a.png", attempts=3)

    assert result == b"OK"
    assert session.call_count == 2


def test_5xx_retries_then_none(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([_FakeResp(500)])

    result = ic._fetch_image_bytes(session, "http://x/a.png", attempts=3)

    assert result is None
    assert session.call_count == 3


def test_uses_tuple_timeout(monkeypatch):
    _patch_sleep(monkeypatch)
    session = _FakeSession([_FakeResp(200, content=b"PNG")])

    ic._fetch_image_bytes(session, "http://x/a.png")

    assert session.calls[0]["timeout"] == (5, 15)


def test_backoff_sleeps_between_retries(monkeypatch):
    recorded = _patch_sleep(monkeypatch)
    session = _FakeSession([requests.exceptions.Timeout("slow")])

    result = ic._fetch_image_bytes(session, "http://x/a.png", attempts=3)

    assert result is None
    # attempts - 1 sleeps: no sleep after the final failed attempt.
    assert len(recorded) == 2
    assert all(s > 0 for s in recorded)
