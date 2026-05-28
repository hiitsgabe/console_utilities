"""Tests for JSON API listing parser (GAB-15).

TDD: these tests are written before the implementation exists. The module is
loaded lazily INSIDE each test (not at import time) so pytest collection stays
clean even while src/services/json_api_listing.py is missing — collection must
succeed and the tests must FAIL at runtime for the right reason (missing
module).
"""

import importlib.util
import os
import sys

# Headless / no-audio defensively, in case the implementation ever pulls pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Import json_api_listing directly by file path to avoid services/__init__.py
# (which pulls in download_manager → nsz → argparse and crashes under pytest).
_mod_path = os.path.join(
    os.path.dirname(__file__), "..", "src", "services", "json_api_listing.py"
)


def _load_mod():
    """Lazy-load the module by file path; raises if the file is missing."""
    spec = importlib.util.spec_from_file_location("json_api_listing", _mod_path)
    if spec is None:
        raise ImportError(f"cannot create spec for {_mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules.setdefault("json_api_listing", mod)
    return mod


class TestItemsPath:
    def test_items_at_default_path(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}, {"name": "b.iso"}]}
        assert mod.parse_json_api_listing(data) == ["a.zip", "b.iso"]

    def test_items_at_nested_path(self):
        mod = _load_mod()
        data = {"roms": [{"name": "x.zip"}]}
        assert mod.parse_json_api_listing(data, items_path="roms") == ["x.zip"]

    def test_missing_path_returns_empty(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}]}
        assert mod.parse_json_api_listing(data, items_path="nope") == []

    def test_non_list_returns_empty(self):
        mod = _load_mod()
        data = {"files": 123}
        assert mod.parse_json_api_listing(data) == []


class TestIdField:
    def test_id_field_extraction(self):
        mod = _load_mod()
        data = {"files": [{"id": "g1.zip"}]}
        assert mod.parse_json_api_listing(data, id_field="id") == ["g1.zip"]


class TestFileFormatFiltering:
    def test_file_format_filtering_default(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}, {"name": "b.iso"}]}
        assert mod.parse_json_api_listing(data, file_format=[".zip"]) == ["a.zip"]

    def test_file_format_filtering_enriched(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}, {"name": "b.iso"}]}
        result = mod.parse_json_api_listing(
            data,
            download_url_template="https://h/dl/<id>",
            file_format=[".zip"],
        )
        assert result == [
            {"filename": "a.zip", "href": "https://h/dl/a.zip", "size": 0}
        ]


class TestEnrichedMode:
    def test_download_template_enriches_to_dicts(self):
        mod = _load_mod()
        data = {"files": [{"name": "g1.zip"}]}
        result = mod.parse_json_api_listing(
            data, download_url_template="https://h/dl/<id>"
        )
        assert result == [
            {"filename": "g1.zip", "href": "https://h/dl/g1.zip", "size": 0}
        ]

    def test_default_no_template_uses_item_url_in_enriched(self):
        mod = _load_mod()
        data = {"files": [{"name": "g.zip", "url": "http://x/g.zip", "sz": 10}]}
        result = mod.parse_json_api_listing(data, size_field="sz")
        assert result == [
            {"filename": "g.zip", "href": "http://x/g.zip", "size": 10}
        ]


class TestReturnTypes:
    def test_default_mode_returns_strings(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}, {"name": "b.iso"}]}
        result = mod.parse_json_api_listing(data)
        assert all(isinstance(x, str) for x in result)
        assert result  # non-empty

    def test_enriched_returns_dicts(self):
        mod = _load_mod()
        data = {"files": [{"name": "a.zip"}]}
        result = mod.parse_json_api_listing(
            data, download_url_template="https://h/dl/<id>"
        )
        assert all(isinstance(x, dict) for x in result)
        assert result  # non-empty
