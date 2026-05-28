"""Tests for URL download validation and filename derivation (GAB-14)."""

import importlib.util
import os

# Defensive headless defaults so collection never tries to open a display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Load src/services/url_download.py DIRECTLY by file path to avoid
# services/__init__.py (which pulls in heavy deps that crash under pytest).
# A lazy loader keeps collection clean even before the module file exists:
# importing happens at test-call time, not at collection time.
_mod_path = os.path.join(
    os.path.dirname(__file__), "..", "src", "services", "url_download.py"
)

_mod = None


def _load():
    global _mod
    if _mod is None:
        spec = importlib.util.spec_from_file_location("url_download", _mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _mod = mod
    return _mod


class TestIsValidDownloadUrl:
    def test_valid_http(self):
        mod = _load()
        assert mod.is_valid_download_url("http://example.com/f.zip") is True

    def test_valid_https(self):
        mod = _load()
        assert mod.is_valid_download_url("https://example.com/f.zip") is True

    def test_empty_false(self):
        mod = _load()
        assert mod.is_valid_download_url("") is False

    def test_whitespace_false(self):
        mod = _load()
        assert mod.is_valid_download_url("   ") is False

    def test_no_scheme_false(self):
        mod = _load()
        assert mod.is_valid_download_url("example.com/f.zip") is False

    def test_ftp_rejected(self):
        mod = _load()
        assert mod.is_valid_download_url("ftp://example.com/f.zip") is False


class TestDeriveDownloadFilename:
    def test_normal(self):
        mod = _load()
        assert mod.derive_download_filename("https://x.com/path/game.zip") == "game.zip"

    def test_trailing_slash(self):
        mod = _load()
        assert mod.derive_download_filename("https://x.com/path/") == "download"

    def test_strips_query(self):
        mod = _load()
        assert mod.derive_download_filename("https://x.com/f.zip?token=abc") == "f.zip"

    def test_strips_fragment(self):
        mod = _load()
        assert mod.derive_download_filename("https://x.com/f.zip#frag") == "f.zip"

    def test_no_basename_fallback(self):
        mod = _load()
        assert mod.derive_download_filename("https://host") == "download"

    def test_sanitizes_illegal(self):
        # urlparse keeps ':' and '*' inside the path component, so a basename
        # like 'a:b*c.zip' exercises the illegal-char sanitization. Chars from
        # the set <>:"/\|?* must not survive in the result. ('/' would split
        # the path and '?' starts the query, so we focus on the chars that can
        # legitimately appear in a urlparse path: ':' and '*'.)
        mod = _load()
        result = mod.derive_download_filename("https://x.com/path/a:b*c.zip")
        illegal = set('<>:"/\\|?*')
        assert not (set(result) & illegal), f"illegal chars remain in {result!r}"
        # The non-illegal characters should be preserved (replaced ones -> '_').
        assert result == "a_b_c.zip"
