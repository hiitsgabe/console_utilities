"""
Steam game search service.

Searches the Steam store to find games by name and get App IDs.
Used for creating .steam shortcut files for ES-DE on Android.
"""

import re
from html import unescape as html_unescape
import threading
from typing import List, Dict, Optional

import requests

from utils.logging import log_error

STEAM_SEARCH_URL = "https://store.steampowered.com/search/results/"
RESULTS_PER_PAGE = 25


def search_steam_games(query: str, start: int = 0, on_results=None, on_error=None):
    """Search Steam for games matching the query in a background thread.

    Args:
        query: Game name to search for.
        start: Result offset for pagination (0-based).
        on_results: Callback(results_list, has_more) with list of dicts.
        on_error: Callback(error_str) on failure.
    """

    def _do_search():
        try:
            response = requests.get(
                STEAM_SEARCH_URL,
                params={
                    "term": query,
                    "l": "english",
                    "cc": "US",
                    "count": str(RESULTS_PER_PAGE),
                    "start": str(start),
                    "sort_by": "_ASC",
                    "infinite": "1",
                    "json": "1",
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            html = data.get("results_html", "")
            total = data.get("total_count", 0)

            # Parse app IDs and names from HTML results
            matches = re.findall(
                r'data-ds-appid="(\d+)".*?<span class="title">(.*?)</span>',
                html,
                re.DOTALL,
            )
            results = [
                {
                    "appid": int(appid),
                    "name": html_unescape(name),
                    "banner_url": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                }
                for appid, name in matches
            ]
            has_more = (start + len(results)) < total
            if on_results:
                on_results(results, has_more)
        except Exception as e:
            log_error("Steam search failed", type(e).__name__, str(e))
            if on_error:
                on_error(str(e))

    thread = threading.Thread(target=_do_search, daemon=True)
    thread.start()
