"""Pure scraper orchestration helpers (GAB-18).

Dependency-free coordination logic for multi-provider scraping. This
module deliberately imports only from ``typing`` so it can be unit
tested in isolation, without pygame, network access, or provider side
effects. Provider construction is injected via ``provider_factory`` and
providers are treated as duck-typed objects exposing ``is_configured()``
and ``search_game(name, system_id)``.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


def ordered_configured_providers(
    primary_name: str,
    fallback_enabled: bool,
    provider_chain: Sequence[str],
    settings: Dict[str, Any],
    provider_factory: Callable[[str, Dict[str, Any]], Any],
) -> List[Tuple[str, Any]]:
    """Build the ordered list of configured providers to try.

    The primary provider is always first. When ``fallback_enabled`` is
    truthy, the remaining names in ``provider_chain`` are appended (de-
    duplicated, preserving order). Each name is instantiated via
    ``provider_factory`` and kept only if ``is_configured()`` is truthy.
    Any exception during construction or configuration check causes that
    provider to be skipped.

    Returns a list of ``(name, provider)`` tuples.
    """
    order = [primary_name]
    if fallback_enabled:
        for name in provider_chain:
            if name not in order:
                order.append(name)

    result: List[Tuple[str, Any]] = []
    for name in order:
        try:
            provider = provider_factory(name, settings)
        except Exception:
            continue
        try:
            if provider.is_configured():
                result.append((name, provider))
        except Exception:
            continue
    return result


def search_game_with_fallback(
    game_name: str,
    system_id: str,
    providers: Sequence[Tuple[str, Any]],
    name_adapter: Optional[Callable[[str, str], str]] = None,
) -> Tuple[bool, Optional[Any], str, Optional[str]]:
    """Search providers in order, returning the first confident hit.

    Auth/credential/quota style errors cause the provider to be skipped
    without being treated as the surfaced error. Other errors are tracked
    as ``last_error``. ``name_adapter(game_name, provider_name)`` lets a
    caller adjust the search term per provider.

    Returns ``(success, result, error, provider_name)``.
    """
    last_error = ""
    for name, provider in providers:
        search_name = name_adapter(game_name, name) if name_adapter else game_name
        try:
            ok, results, error = provider.search_game(search_name, system_id)
        except Exception as e:
            last_error = str(e)
            continue
        if ok and results:
            return (True, results[0], "", name)
        if error and any(
            tok in error.lower()
            for tok in ("auth", "credential", "api key", "quota")
        ):
            continue
        if error:
            last_error = error
    return (False, None, last_error or "No results from any provider", None)


def search_same_platform_then_expand(
    game_name: str,
    primary_system_id: str,
    providers: Sequence[Tuple[str, Any]],
    other_system_ids: Sequence[str] = (),
    name_adapter: Optional[Callable[[str, str], str]] = None,
) -> Tuple[bool, Optional[Any], str, Optional[str]]:
    """Search the primary platform first, then expand to other platforms.

    Phase 1 searches ``primary_system_id`` across all providers. If that
    yields a hit it is returned immediately. Otherwise each id in
    ``other_system_ids`` is searched in turn, returning the first hit. If
    nothing matches anywhere, the phase 1 (negative) result is returned.

    Returns ``(success, result, error, provider_name)``.
    """
    phase1 = search_game_with_fallback(
        game_name, primary_system_id, providers, name_adapter
    )
    if phase1[0]:
        return phase1
    for sid in other_system_ids:
        r = search_game_with_fallback(game_name, sid, providers, name_adapter)
        if r[0]:
            return r
    return phase1
