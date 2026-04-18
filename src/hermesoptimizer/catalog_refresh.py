"""
Safe Provider Endpoint Catalog Refresh Pipeline.

This module provides a safe, non-aggressive mechanism for refreshing the
provider endpoint documentation catalog. Key features:

- Records blocked-doc states explicitly instead of treating them as transient failures
- Works on checked-in JSON data, not runtime ~/.hermes config
- Does NOT aggressively scrape or hammer providers
- Supports explicit blocked state tracking with retry-after dates
- Validates JSON data against the schema

The refresh pipeline is designed to be run manually or via CI to update
the checked-in catalog, while the runtime repair path reads the checked-in
JSON instead of scraping on demand.

Usage:
    from hermesoptimizer.catalog_refresh import catalog_refresh

    # Refresh the catalog (dry run)
    result = catalog_refresh("data/provider_endpoints.json", dry_run=True)

    # Refresh with actual updates (will modify the file)
    result = catalog_refresh("data/provider_endpoints.json", dry_run=False)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from hermesoptimizer.schemas.provider_endpoint import (
    ProviderEndpointCatalog,
    load_provider_endpoints_catalog,
    validate_provider_endpoints,
)


# -----------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------

class BlockedReason(str, Enum):
    """Reasons why a provider's documentation is blocked or inaccessible."""

    ANTI_BOT_BLOCK = "anti_bot_block"
    RATE_LIMIT = "rate_limit"
    AUTH_REQUIRED = "auth_required"
    JAVASCRIPT_WALL = "javascript_wall"
    NOT_FOUND = "not_found"
    CONNECTION_ERROR = "connection_error"
    SERVER_ERROR = "server_error"
    MANUAL_CURATION = "manual_curation"


class EndpointRefreshOutcome(str, Enum):
    """Outcome of attempting to refresh a provider's endpoint data."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    ERROR = "error"
    NO_CHANGE = "no_change"
    MANUAL_CURATION = "manual_curation"


# -----------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------

@dataclass
class BlockedDocState:
    """
    Records the blocked state for a provider's documentation.

    When a provider's documentation is blocked (anti-bot, rate limit, etc.),
    this state is recorded so we don't repeatedly hammer the provider.
    """

    provider_slug: str
    blocked_reason: BlockedReason
    blocked_date: date
    source_urls_attempted: list[str]
    retry_after: date | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        result: dict[str, Any] = {
            "provider_slug": self.provider_slug,
            "blocked_reason": self.blocked_reason.value,
            "blocked_date": self.blocked_date.isoformat(),
            "source_urls_attempted": self.source_urls_attempted,
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlockedDocState":
        """Deserialize from dictionary."""
        return cls(
            provider_slug=data["provider_slug"],
            blocked_reason=BlockedReason(data["blocked_reason"]),
            blocked_date=date.fromisoformat(data["blocked_date"]),
            source_urls_attempted=data["source_urls_attempted"],
            retry_after=date.fromisoformat(data["retry_after"])
            if data.get("retry_after")
            else None,
        )


@dataclass
class ProviderRefreshResult:
    """
    Result of refreshing a single provider's endpoint data.
    """

    provider_slug: str
    outcome: EndpointRefreshOutcome
    updated_endpoints: list[dict[str, Any]] | None = None
    blocked_state: BlockedDocState | None = None
    error_message: str | None = None
    source_url: str | None = None


@dataclass
class CatalogRefreshResult:
    """
    Aggregate result of refreshing the entire catalog.
    """

    version: str
    refresh_date: date
    provider_results: list[ProviderRefreshResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Count of successfully refreshed providers."""
        return sum(1 for r in self.provider_results if r.outcome == EndpointRefreshOutcome.SUCCESS)

    @property
    def blocked_count(self) -> int:
        """Count of blocked providers."""
        return sum(1 for r in self.provider_results if r.outcome == EndpointRefreshOutcome.BLOCKED)

    @property
    def error_count(self) -> int:
        """Count of providers with errors."""
        return sum(1 for r in self.provider_results if r.outcome == EndpointRefreshOutcome.ERROR)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the refresh result."""
        blocked_providers = [
            r.provider_slug
            for r in self.provider_results
            if r.outcome == EndpointRefreshOutcome.BLOCKED
        ]
        error_providers = [
            r.provider_slug
            for r in self.provider_results
            if r.outcome == EndpointRefreshOutcome.ERROR
        ]
        success_providers = [
            r.provider_slug
            for r in self.provider_results
            if r.outcome == EndpointRefreshOutcome.SUCCESS
        ]

        return {
            "total_providers": len(self.provider_results),
            "success_count": self.success_count,
            "blocked_count": self.blocked_count,
            "error_count": self.error_count,
            "blocked_providers": blocked_providers,
            "error_providers": error_providers,
            "success_providers": success_providers,
        }


@dataclass
class RefreshState:
    """
    Persistent state tracking for catalog refresh operations.

    This tracks which providers are blocked, when they were blocked,
    and the overall outcome of the last refresh attempt.
    """

    version: str
    last_refresh: date
    blocked_providers: dict[str, BlockedDocState] = field(default_factory=dict)
    provider_outcomes: dict[str, EndpointRefreshOutcome] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "version": self.version,
            "last_refresh": self.last_refresh.isoformat(),
            "blocked_providers": {
                slug: state.to_dict() for slug, state in self.blocked_providers.items()
            },
            "provider_outcomes": {
                slug: outcome.value for slug, outcome in self.provider_outcomes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RefreshState":
        """Deserialize from dictionary."""
        blocked_providers = {}
        for slug, state_data in data.get("blocked_providers", {}).items():
            blocked_providers[slug] = BlockedDocState.from_dict(state_data)

        provider_outcomes = {}
        for slug, outcome_value in data.get("provider_outcomes", {}).items():
            provider_outcomes[slug] = EndpointRefreshOutcome(outcome_value)

        return cls(
            version=data["version"],
            last_refresh=date.fromisoformat(data["last_refresh"]),
            blocked_providers=blocked_providers,
            provider_outcomes=provider_outcomes,
        )


# -----------------------------------------------------------------------
# Refresh State Persistence
# -----------------------------------------------------------------------

DEFAULT_REFRESH_STATE_FILENAME = "catalog_refresh_state.json"


def get_refresh_state_path(
    base_dir: Path | None = None, filename: str = DEFAULT_REFRESH_STATE_FILENAME
) -> Path:
    """
    Return the path to the catalog refresh state file.

    Args:
        base_dir: Directory for the state file. Defaults to the data directory
                  in the hermesoptimizer package.
        filename: Name of the state file.

    Returns:
        Path to the refresh state file.
    """
    if base_dir is None:
        # Default to the data directory in the package
        base_dir = Path(__file__).parent.parent.parent / "data"
    return base_dir / filename


def save_refresh_state(state: RefreshState, path: Path) -> None:
    """
    Save refresh state to a JSON file.

    Args:
        state: The RefreshState to save.
        path: Path to save the state file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)


def load_refresh_state(path: Path) -> RefreshState | None:
    """
    Load refresh state from a JSON file.

    Args:
        path: Path to the state file.

    Returns:
        RefreshState if file exists and is valid, None otherwise.
    """
    if not path.is_file():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RefreshState.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


# -----------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------

def get_blocked_providers(state: RefreshState) -> dict[str, BlockedDocState]:
    """
    Return the dictionary of blocked providers from refresh state.

    Args:
        state: The RefreshState to query.

    Returns:
        Dictionary mapping provider slug to BlockedDocState.
    """
    return dict(state.blocked_providers)


def merge_refresh_results(results: list[CatalogRefreshResult]) -> CatalogRefreshResult:
    """
    Merge multiple CatalogRefreshResult instances into one.

    Useful when running partial refreshes and needing to combine results.

    Args:
        results: List of CatalogRefreshResult to merge.

    Returns:
        A single merged CatalogRefreshResult.
    """
    if not results:
        return CatalogRefreshResult(
            version="1.0.0",
            refresh_date=date.today(),
            provider_results=[],
        )

    # Use the version from the first result
    version = results[0].version
    # Use the latest refresh date
    refresh_date = max(r.refresh_date for r in results)

    # Combine all provider results, deduplicating by provider_slug
    # (later results overwrite earlier ones for the same provider)
    by_slug: dict[str, ProviderRefreshResult] = {}
    for result in results:
        for pr in result.provider_results:
            by_slug[pr.provider_slug] = pr

    return CatalogRefreshResult(
        version=version,
        refresh_date=refresh_date,
        provider_results=list(by_slug.values()),
    )


# -----------------------------------------------------------------------
# Main Refresh Function
# -----------------------------------------------------------------------

def catalog_refresh(
    catalog_path: Path | str,
    dry_run: bool = True,
    state_path: Path | str | None = None,
) -> CatalogRefreshResult | None:
    """
    Refresh the provider endpoint catalog.

    This function safely refreshes the endpoint catalog by:
    1. Loading the current catalog
    2. Checking each provider's refresh state
    3. For each provider, determining if it needs refresh based on:
       - Last verified date
       - Current blocked state
    4. Recording blocked-doc states explicitly
    5. Returning a detailed result without aggressive scraping

    In dry_run mode (default), no modifications are made.
    When dry_run=False, the refresh state is saved to the state file.

    Args:
        catalog_path: Path to the provider_endpoints.json catalog file.
        dry_run: If True, don't modify any files. Default is True.
        state_path: Optional path to the refresh state file.

    Returns:
        CatalogRefreshResult with details of the refresh operation,
        or None if the catalog could not be loaded.
    """
    catalog_path = Path(catalog_path)
    today = date.today()

    # Load current catalog
    try:
        catalog = ProviderEndpointCatalog.from_file(catalog_path)
    except Exception:
        # If we can't load the catalog, return a result with all errors
        return CatalogRefreshResult(
            version="1.0.0",
            refresh_date=today,
            provider_results=[
                ProviderRefreshResult(
                    provider_slug=slug,
                    outcome=EndpointRefreshOutcome.ERROR,
                    error_message="Failed to load catalog",
                )
                for slug in ["openai", "anthropic", "qwen", "xai", "minimax", "zai"]
            ],
        )

    # Load refresh state if available
    if state_path is None:
        state_path = get_refresh_state_path(catalog_path.parent)
    else:
        state_path = Path(state_path)

    refresh_state = load_refresh_state(state_path)

    # Build result list
    provider_results: list[ProviderRefreshResult] = []

    for slug in catalog.provider_slugs:
        provider = catalog.get_provider(slug)
        if provider is None:
            provider_results.append(
                ProviderRefreshResult(
                    provider_slug=slug,
                    outcome=EndpointRefreshOutcome.ERROR,
                    error_message="Provider not found in catalog",
                )
            )
            continue

        # Check if this provider is blocked
        if refresh_state and slug in refresh_state.blocked_providers:
            blocked = refresh_state.blocked_providers[slug]
            # Check if we should skip due to retry_after
            if blocked.retry_after and blocked.retry_after > today:
                provider_results.append(
                    ProviderRefreshResult(
                        provider_slug=slug,
                        outcome=EndpointRefreshOutcome.BLOCKED,
                        blocked_state=blocked,
                    )
                )
                continue

        # Get endpoint families
        endpoints = catalog.list_endpoint_families(slug)

        # In a real implementation, we would:
        # 1. Check if the provider needs refresh (based on last_verified)
        # 2. If needed, attempt to fetch from doc_urls
        # 3. If blocked, record the blocked state
        # 4. If successful, update the endpoint data
        #
        # For this safe implementation, we record the current state
        # and mark as MANUAL_CURATION since we're not actually scraping

        # Record the outcome for this provider
        outcome = EndpointRefreshOutcome.MANUAL_CURATION
        source_url = endpoints[0].get("doc_urls", [None])[0] if endpoints else None

        provider_results.append(
            ProviderRefreshResult(
                provider_slug=slug,
                outcome=outcome,
                updated_endpoints=endpoints,
                source_url=source_url,
            )
        )

    result = CatalogRefreshResult(
        version=catalog.version or "1.0.0",
        refresh_date=today,
        provider_results=provider_results,
    )

    # Persist state only when not in dry_run mode
    if not dry_run:
        # Build or update the refresh state
        blocked_providers: dict[str, BlockedDocState] = {}
        provider_outcomes: dict[str, EndpointRefreshOutcome] = {}

        # Carry forward any existing blocked states that still have valid retry_after
        if refresh_state:
            for slug, blocked in refresh_state.blocked_providers.items():
                if blocked.retry_after and blocked.retry_after > today:
                    blocked_providers[slug] = blocked

        # Add/update outcomes and blocked states from this refresh
        for pr in provider_results:
            provider_outcomes[pr.provider_slug] = pr.outcome
            if pr.outcome == EndpointRefreshOutcome.BLOCKED and pr.blocked_state:
                blocked_providers[pr.provider_slug] = pr.blocked_state

        new_state = RefreshState(
            version=catalog.version or "1.0.0",
            last_refresh=today,
            blocked_providers=blocked_providers,
            provider_outcomes=provider_outcomes,
        )
        save_refresh_state(new_state, state_path)

    return result


# -----------------------------------------------------------------------
# Blocked State Recording
# -----------------------------------------------------------------------

def record_blocked_state(
    provider_slug: str,
    reason: BlockedReason,
    source_urls: list[str],
    retry_after: date | None = None,
    state_path: Path | str | None = None,
) -> BlockedDocState:
    """
    Record a blocked state for a provider.

    This function creates a BlockedDocState and saves it to the
    refresh state file, so future refreshes know to skip this provider.

    Args:
        provider_slug: The provider identifier.
        reason: The reason for the block.
        source_urls: List of URLs that were attempted.
        retry_after: Optional date after which to retry.
        state_path: Optional path to the state file.

    Returns:
        The created BlockedDocState.
    """
    blocked_state = BlockedDocState(
        provider_slug=provider_slug,
        blocked_reason=reason,
        blocked_date=date.today(),
        source_urls_attempted=source_urls,
        retry_after=retry_after,
    )

    # Load existing state or create new
    if state_path is None:
        state_path = get_refresh_state_path()
    else:
        state_path = Path(state_path)

    current_state = load_refresh_state(state_path)

    if current_state is None:
        new_state = RefreshState(
            version="1.0.0",
            last_refresh=date.today(),
            blocked_providers={provider_slug: blocked_state},
            provider_outcomes={provider_slug: EndpointRefreshOutcome.BLOCKED},
        )
    else:
        new_state = current_state
        new_state.blocked_providers[provider_slug] = blocked_state
        new_state.provider_outcomes[provider_slug] = EndpointRefreshOutcome.BLOCKED
        new_state.last_refresh = date.today()

    save_refresh_state(new_state, state_path)

    return blocked_state
