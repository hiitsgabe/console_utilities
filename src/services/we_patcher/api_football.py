"""API-Football client — re-exported from services.sports_api."""

from services.sports_api.api_football import (  # noqa: F401
    ApiFootballClient,
    RateLimitError,
    DailyLimitError,
    SeasonNotAvailableError,
)
