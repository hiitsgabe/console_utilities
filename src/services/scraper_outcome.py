"""Pure helper for classifying scraper search outcomes (GAB-12)."""


def classify_search_outcome(success, results, error=None):
    """Return 'error' if the search failed, 'no_match' if it succeeded
    with no results, else 'success'."""
    if not success:
        return "error"
    if not results:
        return "no_match"
    return "success"
