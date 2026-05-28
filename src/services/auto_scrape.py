"""Auto-scrape gating and new-completion detection (GAB-19).

Pure helpers with no project dependencies so they remain trivially testable.
"""

from typing import Any, Callable, Hashable, Iterable, Mapping


def should_auto_scrape(settings: Mapping[str, Any]) -> bool:
    return (
        bool(settings.get("auto_scrape_after_download", False))
        and bool(settings.get("scraper_enabled", False))
        and settings.get("scraper_provider", "") not in ("", None)
    )


def new_completions(prev_status, items, id_of, status_of) -> list:
    result = []
    for item in items:
        iid = id_of(item)
        if status_of(item) == "completed" and prev_status.get(iid) != "completed":
            result.append(iid)
    return result
