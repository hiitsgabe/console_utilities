# Scraper Refactor Design (GAB-18)

Design notes for centralizing multi-provider scraper orchestration and
charting the path toward platform-expansion fallback and a handheld-
friendly scraping UX.

## Competitor review

Existing ROM scrapers converge on a few well-proven patterns:

- **Skyscraper** chains lookups by descending confidence: file **hash**
  match first (CRC/MD5/SHA1), then **exact filename** match, then a
  **fuzzy** title match. It aggressively **caches** every resolved game
  locally so re-runs and quota-limited sources are not hammered.
- **ES-DE / Universal XML Scraper** are **hash-first** as well, then fall
  back through title matching with **region fallback** (e.g. try the
  user's region, then World/USA/EU/JP) so the right box art is chosen.
- **ScreenScraper** is the de-facto **primary** source for most setups
  because of its rich media set and hash database; tools treat it as the
  first provider when credentials exist.
- **TheGamesDB / ScreenScraper quotas**: both impose per-user request
  budgets (ScreenScraper scales by contributor level; TheGamesDB by API
  key tier). Tools mitigate this by caching and by only falling back to a
  secondary source when the primary fails or is exhausted.

Takeaway: confidence-ordered chaining, region/platform fallback, and
caching to respect quotas are the shared backbone.

## Recommended fallback + platform-expansion algorithm

1. **Order configured providers.** Primary first, then the remaining
   chain de-duplicated, keeping only providers that are actually
   configured (`is_configured()`), swallowing construction errors. This
   is now the pure `ordered_configured_providers` helper.
2. **Same-platform first.** Search the ROM's own platform across all
   configured providers. Return the first confident hit.
3. **Then expand.** If no provider matches on the native platform, retry
   the same providers against related platform ids (e.g. a multi-system
   compilation, or libretro/ScreenScraper id mismatches). This is the
   `search_same_platform_then_expand` helper.
4. **Stop at first confident hit.** As soon as any `(provider, platform)`
   pair returns results, accept it and stop searching.
5. **Region fallback.** Within a provider, prefer the user's region for
   media/title, then fall through World/USA/EU/JP (Phase 2+ concern,
   handled inside individual providers).
6. **Cache to respect quotas.** Auth/credential/api-key/quota errors do
   **not** count as a "no match"; the provider is skipped so a healthy
   secondary still answers. Resolved results should be cached so repeat
   scrapes and quota-limited providers are not re-queried.

## Recommended handheld UX

Constrained to an 800x600 screen with D-pad/controller input.

- **Single scrape**: show the candidate **title + box art + confidence**
  score, with **Accept / Skip / Edit** actions. On a **no-match**, drop
  straight into **edit-name** (on-screen keyboard) so the user can refine
  the search term and retry without leaving the screen.
- **Batch scrape**: show **progress N/M**, **auto-accept** high-confidence
  matches without prompting, and **queue only ambiguous** ones for review.
  Support **halt-to-current** (stop but keep everything matched so far)
  and present a **final summary** (matched / skipped / failed counts).

## Phased plan

- **Phase 1 (THIS PR)** — Introduce the pure `scraper_orchestration`
  module (`ordered_configured_providers`,
  `search_game_with_fallback`, `search_same_platform_then_expand`) with
  full unit tests, and delegate `ScraperService._get_provider_chain()`'s
  multi-provider branch to `ordered_configured_providers`. Centralizes
  true configured-provider fallback in dependency-free, testable code.
  Backward compatible: the produced provider list is identical to before
  for current configs, and the fallback-disabled branch is unchanged.
- **Phase 2** — Wire `search_same_platform_then_expand` into
  `ScraperService.search_game`, passing a `name_adapter` that carries the
  existing libretro special-case name handling, plus an
  `other_system_ids` source for platform expansion. Add caching and
  region fallback inside providers.
- **Phase 3** — UI overhaul: implement the single and batch scraping
  screens described above (confidence display, Accept/Skip/Edit,
  auto-accept, review queue, halt-to-current, final summary).
