"""
Provider Model Catalog for Hermes.

Captures current best models and capability families for all supported providers,
with support for role/capability-based lookups and region-aware validation.

Providers covered:
- OpenAI (gpt-4, gpt-4o, gpt-4o-mini, etc.)
- Anthropic (claude-3.5, claude-3, etc.)
- Alibaba/Qwen (qwen3.6-plus, qwen3-max, qwen3-coder-plus, qwen3-vl-plus, etc.)
- xAI/Grok (grok-4, grok-imagine, etc.)
- MiniMax (MiniMax-M2.7, MiniMax-VL-01, etc.)
- Z.AI/GLM (GLM-5.1, GLM-4.6, etc.)

Key design:
- Pure-Python, no external dependencies beyond PyYAML (shared with the project)
- Dataclass-based entries for easy introspection
- Global singleton MODEL_CATALOG pre-populated with all known families
- Support for role/capability lookups (best_for map per model)
- Region-aware validation (region codes from RegionAvailability enum)
- Full validation pass on the global catalog
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RegionAvailability(str, Enum):
    """Valid region codes for model availability."""
    US = "us"
    EU = "eu"
    CN = "cn"
    AP = "ap"   # Asia-Pacific
    GLOBAL = "global"


class LatencyTier(str, Enum):
    """Latency/compute tier classification."""
    FAST = "fast"       # e.g. reasoning-optimized, flash
    STANDARD = "standard"
    SLOW = "slow"       # e.g. large context, premium


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_ROLE_LITERALS = [
    "coding",
    "reasoning",
    "vision",
    "text",
    "embedding",
    "reranking",
    "speech-to-text",
    "text-to-speech",
    "image-generation",
    "video-generation",
    "music-generation",
    "translation",
    "multimodal",
    "fast-response",
    "large-context",
    "cost-effective",
]


@dataclass(slots=True)
class ModelCatalogEntry:
    """
    A single model entry in the provider catalog.

    Attributes
    ----------
    name : str
        Canonical model name string, e.g. "qwen3.6-plus", "gpt-4o".
    display_name : str
        Human-readable name, e.g. "Qwen 3.6 Plus".
    provider : str
        Canonical provider name, e.g. "qwen", "openai".
    capabilities : list[str]
        Capability tags, e.g. ["text", "vision", "reasoning"].
        Must contain at least one non-empty string.
    context_window : int
        Maximum context window size in tokens. Must be > 0.
    input_cost_per_mtok : float | None, default None
        Input cost per million tokens. None means unknown/not applicable.
    output_cost_per_mtok : float | None, default None
        Output cost per million tokens. None means unknown/not applicable.
    latency_tier : LatencyTier | None, default None
        Relative latency/compute tier for the model.
    region_availability : list[str] | None, default None
        List of region codes (from RegionAvailability) where the model is available.
        None means region info is not tracked.
    release_date : str | None, default None
        ISO-8601 date string for the model's release date.
    is_deprecated : bool, default False
        True if this model is deprecated.
    is_best_for : dict[str, str] | None, default None
        Map from role (e.g. "reasoning", "coding") to the canonical name of the
        best model for that role within the same provider family.
        e.g. {"reasoning": "qwen3.6-plus", "coding": "qwen3-coder-plus"}.
    endpoint : str | None, default None
        Canonical API endpoint URL for this model family.
    auth_type : str | None, default None
        Authentication type, e.g. "bearer", "api_key".
    auth_key_env : str | None, default None
        Environment variable name that holds the API key, e.g. "DASHSCOPE_API_KEY".
    notes : str | None, default None
        Free-form notes about this model.
    """

    name: str
    display_name: str
    provider: str
    capabilities: list[str]
    context_window: int

    # Optional cost info
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None

    # Latency tier
    latency_tier: LatencyTier | None = None

    # Region availability
    region_availability: list[str] | None = None

    # Metadata
    release_date: str | None = None
    is_deprecated: bool = False

    # Role/capability recommendation map: role name -> best model name (same provider)
    is_best_for: dict[str, str] | None = None

    # Endpoint and auth
    endpoint: str | None = None
    auth_type: str | None = None
    auth_key_env: str | None = None

    # Notes
    notes: str | None = None

    def __post_init__(self) -> None:
        # Normalize provider to lowercase
        object.__setattr__(self, "provider", self.provider.lower().strip())


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class CatalogValidationError(ValueError):
    """Raised when a catalog entry or operation fails validation."""
    pass


def _validate_entry(entry: ModelCatalogEntry, known_names: set[tuple[str, str]]) -> list[str]:
    """
    Validate a single catalog entry.

    Returns a list of error messages (empty if valid).
    known_names is the set of (provider, model_name) pairs already registered.
    """
    errors: list[str] = []

    if not entry.name:
        errors.append(f"Model entry has empty name")

    if not entry.provider:
        errors.append(f"Model entry '{entry.name}' has empty provider")

    if not entry.capabilities:
        errors.append(f"Model entry '{entry.name}' has no capabilities (empty list)")
    elif not all(entry.capabilities):
        errors.append(f"Model entry '{entry.name}' has empty capability string in list")

    # context_window must be > 0 for text-capable models, but 0 is allowed
    # for audio/image/video-only models (ASR, TTS, image gen, etc.)
    if entry.context_window < 0:
        errors.append(f"Model entry '{entry.name}' has invalid context_window {entry.context_window} (must be >= 0)")
    elif entry.context_window == 0 and "text" in entry.capabilities:
        errors.append(f"Model entry '{entry.name}' has context_window=0 but has 'text' capability (must be > 0)")

    key = (entry.provider, entry.name)
    if key in known_names:
        errors.append(
            f"Model entry '{entry.name}' in provider '{entry.provider}' is a duplicate"
        )

    if entry.region_availability is not None:
        valid_regions = {r.value for r in RegionAvailability}
        for region in entry.region_availability:
            if region not in valid_regions:
                errors.append(
                    f"Model entry '{entry.name}' has invalid region '{region}'. "
                    f"Valid regions: {valid_regions}"
                )

    if entry.latency_tier is not None:
        valid_tiers = {t.value for t in LatencyTier}
        if entry.latency_tier not in valid_tiers:
            errors.append(
                f"Model entry '{entry.name}' has invalid latency_tier '{entry.latency_tier}'. "
                f"Valid tiers: {valid_tiers}"
            )

    if entry.is_best_for is not None:
        for role, suggested_name in entry.is_best_for.items():
            if not suggested_name:
                errors.append(
                    f"Model entry '{entry.name}' has empty best_for value for role '{role}'"
                )

    if entry.endpoint is not None:
        if not entry.endpoint.startswith(("http://", "https://")):
            errors.append(
                f"Model entry '{entry.name}' has invalid endpoint URL '{entry.endpoint}' "
                f"(must start with http:// or https://)"
            )
        if entry.auth_type is None:
            errors.append(
                f"Model entry '{entry.name}' has endpoint but no auth_type set"
            )
        if entry.auth_key_env is None:
            errors.append(
                f"Model entry '{entry.name}' has endpoint but no auth_key_env set"
            )

    if entry.input_cost_per_mtok is not None and entry.input_cost_per_mtok < 0:
        errors.append(
            f"Model entry '{entry.name}' has negative input_cost_per_mtok {entry.input_cost_per_mtok}"
        )

    if entry.output_cost_per_mtok is not None and entry.output_cost_per_mtok < 0:
        errors.append(
            f"Model entry '{entry.name}' has negative output_cost_per_mtok {entry.output_cost_per_mtok}"
        )

    return errors


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class ProviderModelCatalog:
    """
    In-memory model catalog for a set of providers.

    Supports adding entries, querying by provider/capability/role,
    and full catalog validation.
    """

    def __init__(self) -> None:
        self._entries: list[ModelCatalogEntry] = []
        self._by_provider: dict[str, list[ModelCatalogEntry]] = {}

    def add(self, entry: ModelCatalogEntry) -> None:
        """Add a model entry to the catalog. Raises CatalogValidationError on duplicate."""
        errors = _validate_entry(entry, self._known_names())
        if errors:
            raise CatalogValidationError(
                f"Cannot add model '{entry.name}': " + "; ".join(errors)
            )
        self._entries.append(entry)
        provider_list = self._by_provider.setdefault(entry.provider, [])
        provider_list.append(entry)

    def _known_names(self) -> set[tuple[str, str]]:
        return {(e.provider, e.name) for e in self._entries}

    def list_providers(self) -> list[str]:
        """Return sorted list of canonical provider names in this catalog."""
        return sorted(self._by_provider.keys())

    def list_models(self, provider: str | None = None) -> list[ModelCatalogEntry]:
        """
        Return all model entries.

        If provider is specified, returns only entries for that provider.
        """
        if provider is None:
            return list(self._entries)
        return list(self._by_provider.get(provider.lower().strip(), []))

    def get(self, provider: str, name: str) -> ModelCatalogEntry | None:
        """Get a specific entry by provider and model name."""
        provider = provider.lower().strip()
        for entry in self._by_provider.get(provider, []):
            if entry.name == name:
                return entry
        return None

    def best_model(
        self,
        role: str | None = None,
        capability: str | None = None,
        provider: str | None = None,
    ) -> ModelCatalogEntry | None:
        """
        Find the best model for a given role or capability.

        If role is provided, looks up is_best_for[role] within matching provider
        and returns the referenced model.

        If capability is provided, returns the first model that has it.

        If provider is also provided, restricts the search to that provider.

        Priority: role > capability.
        """
        if role:
            # Use is_best_for map to find the recommended model
            candidates = self.list_models(provider) if provider else self._entries
            for entry in candidates:
                if entry.is_best_for and role in entry.is_best_for:
                    target_name = entry.is_best_for[role]
                    # Look up the target model
                    found = self.get(entry.provider, target_name)
                    if found:
                        return found
            return None

        if capability:
            for entry in self._entries:
                if provider and entry.provider != provider.lower().strip():
                    continue
                if capability in entry.capabilities:
                    return entry
            return None

        return None

    def region_aware_best(
        self,
        role: str,
        region: str,
    ) -> ModelCatalogEntry | None:
        """
        Find the best model for a role that is available in the given region.

        Returns None if no suitable model is found.
        """
        candidate = self.best_model(role=role)
        if candidate is None:
            return None
        if candidate.region_availability is None:
            return candidate
        if region in candidate.region_availability:
            return candidate
        # Fallback: search for other models with same role that are available in region
        for entry in self._entries:
            if entry.is_best_for and role in entry.is_best_for:
                target_name = entry.is_best_for[role]
                found = self.get(entry.provider, target_name)
                if found and found.region_availability is not None and region in found.region_availability:
                    return found
        return None

    def validate(self) -> list[str]:
        """
        Validate the entire catalog.

        Returns a list of error messages (empty if fully valid).
        """
        all_errors: list[str] = []

        # Check for duplicate entries
        seen: dict[str, list[str]] = {}
        for entry in self._entries:
            key = entry.provider
            if key not in seen:
                seen[key] = []
            if entry.name in seen[key]:
                all_errors.append(
                    f"Duplicate model name '{entry.name}' in provider '{entry.provider}'"
                )
            seen[key].append(entry.name)

        # Validate each entry.  Use a growing seen-set so we detect duplicates
        # only when the same provider/model pair appears more than once in the
        # catalog, not because we are validating an entry against itself.
        seen: set[tuple[str, str]] = set()
        for entry in self._entries:
            errors = _validate_entry(entry, seen)
            all_errors.extend(f"[{entry.provider}/{entry.name}] {e}" for e in errors)
            seen.add((entry.provider, entry.name))

        # Validate is_best_for cross-references
        for entry in self._entries:
            if entry.is_best_for:
                for role, suggested_name in entry.is_best_for.items():
                    if not self.get(entry.provider, suggested_name):
                        all_errors.append(
                            f"[{entry.provider}/{entry.name}] best_for['{role}']='{suggested_name}' "
                            f"refers to a model that does not exist in provider '{entry.provider}'"
                        )

        return all_errors


# ---------------------------------------------------------------------------
# Global pre-populated catalog
# ---------------------------------------------------------------------------

def _build_model_catalog() -> ProviderModelCatalog:
    """
    Build and populate the global MODEL_CATALOG with all known provider families.
    """
    catalog = ProviderModelCatalog()

    # ========================================================================
    # OpenAI
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="gpt-4o",
        display_name="GPT-4o",
        provider="openai",
        capabilities=["text", "vision", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=15.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-05-13",
        is_best_for={"reasoning": "gpt-4o", "text": "gpt-4o", "fast-response": "gpt-4o-mini"},
        endpoint="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key_env="OPENAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider="openai",
        capabilities=["text", "vision", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=0.15,
        output_cost_per_mtok=0.6,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-07-18",
        is_best_for={"cost-effective": "gpt-4o-mini", "fast-response": "gpt-4o-mini"},
        endpoint="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key_env="OPENAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="gpt-4-turbo",
        display_name="GPT-4 Turbo",
        provider="openai",
        capabilities=["text", "vision", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=10.0,
        output_cost_per_mtok=30.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2023-11-06",
        is_best_for={"large-context": "gpt-4-turbo"},
        endpoint="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key_env="OPENAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="o1",
        display_name="OpenAI o1",
        provider="openai",
        capabilities=["reasoning", "text"],
        context_window=128000,
        input_cost_per_mtok=15.0,
        output_cost_per_mtok=60.0,
        latency_tier=LatencyTier.SLOW,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2024-09-12",
        is_best_for={"reasoning": "o1"},
        endpoint="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key_env="OPENAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="o3",
        display_name="OpenAI o3",
        provider="openai",
        capabilities=["reasoning", "text"],
        context_window=200000,
        input_cost_per_mtok=15.0,
        output_cost_per_mtok=60.0,
        latency_tier=LatencyTier.SLOW,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-01",
        is_best_for={"reasoning": "o3", "large-context": "o3"},
        endpoint="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key_env="OPENAI_API_KEY",
    ))

    # ========================================================================
    # Anthropic
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="claude-3.5-sonnet",
        display_name="Claude 3.5 Sonnet",
        provider="anthropic",
        capabilities=["text", "vision", "reasoning"],
        context_window=200000,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=15.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-06-20",
        is_best_for={"reasoning": "claude-3.5-sonnet", "text": "claude-3.5-sonnet", "large-context": "claude-3.5-sonnet"},
        endpoint="https://api.anthropic.com/v1",
        auth_type="api_key",
        auth_key_env="ANTHROPIC_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="claude-3.5-haiku",
        display_name="Claude 3.5 Haiku",
        provider="anthropic",
        capabilities=["text", "vision", "reasoning"],
        context_window=200000,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=4.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-07-18",
        is_best_for={"cost-effective": "claude-3.5-haiku"},
        endpoint="https://api.anthropic.com/v1",
        auth_type="api_key",
        auth_key_env="ANTHROPIC_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="claude-3-opus",
        display_name="Claude 3 Opus",
        provider="anthropic",
        capabilities=["text", "vision", "reasoning"],
        context_window=200000,
        input_cost_per_mtok=15.0,
        output_cost_per_mtok=75.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.EU, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-02-29",
        is_best_for={"large-context": "claude-3-opus"},
        endpoint="https://api.anthropic.com/v1",
        auth_type="api_key",
        auth_key_env="ANTHROPIC_API_KEY",
    ))

    # ========================================================================
    # Alibaba/Qwen
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="qwen3.6-plus",
        display_name="Qwen 3.6 Plus",
        provider="qwen",
        capabilities=["text", "reasoning", "coding"],
        context_window=32000,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=1.5,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-01-26",
        is_best_for={"reasoning": "qwen3.6-plus", "coding": "qwen3.6-plus", "text": "qwen3.6-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
        notes="Flagship reasoning model, supports extended thought.",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-max",
        display_name="Qwen 3 Max",
        provider="qwen",
        capabilities=["text", "reasoning", "coding"],
        context_window=32000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=3.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-02-14",
        is_best_for={"reasoning": "qwen3.6-plus", "large-context": "qwen3-max"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen-plus",
        display_name="Qwen Plus",
        provider="qwen",
        capabilities=["text", "reasoning"],
        context_window=32000,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=2.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-11-20",
        is_best_for={"text": "qwen-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-coder-plus",
        display_name="Qwen 3 Coder Plus",
        provider="qwen",
        capabilities=["text", "coding"],
        context_window=32000,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=2.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-01-26",
        is_best_for={"coding": "qwen3-coder-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-vl-plus",
        display_name="Qwen 3 VL Plus",
        provider="qwen",
        capabilities=["text", "vision", "reasoning"],
        context_window=32000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=3.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-02-06",
        is_best_for={"vision": "qwen3-vl-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-omni-plus",
        display_name="Qwen 3 Omni Plus",
        provider="qwen",
        capabilities=["text", "vision", "reasoning", "multimodal"],
        context_window=32000,
        input_cost_per_mtok=1.5,
        output_cost_per_mtok=4.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-20",
        is_best_for={"multimodal": "qwen3-omni-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-reranker",
        display_name="Qwen 3 Reranker",
        provider="qwen",
        capabilities=["reranking", "text"],
        context_window=8000,
        input_cost_per_mtok=0.2,
        output_cost_per_mtok=0.2,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-10",
        is_best_for={"reranking": "qwen3-reranker"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-embedding",
        display_name="Qwen 3 Embedding",
        provider="qwen",
        capabilities=["embedding", "text"],
        context_window=8000,
        input_cost_per_mtok=0.1,
        output_cost_per_mtok=0.1,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-10",
        is_best_for={"embedding": "qwen3-embedding"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-asr-flash",
        display_name="Qwen 3 ASR Flash",
        provider="qwen",
        capabilities=["speech-to-text"],
        context_window=0,
        input_cost_per_mtok=0.05,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-15",
        is_best_for={"speech-to-text": "qwen3-asr-flash"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-tts-instruct-flash",
        display_name="Qwen 3 TTS Instruct Flash",
        provider="qwen",
        capabilities=["text-to-speech"],
        context_window=0,
        input_cost_per_mtok=0.1,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-15",
        is_best_for={"text-to-speech": "qwen3-tts-instruct-flash"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen-image-2.0-pro",
        display_name="Qwen Image 2.0 Pro",
        provider="qwen",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-20",
        is_best_for={"image-generation": "qwen-image-2.0-pro"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="wan2.6-t2i",
        display_name="Wan 2.6 T2I",
        provider="qwen",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=0.3,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-01",
        is_best_for={"image-generation": "qwen-image-2.0-pro"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="wan2.6-t2v",
        display_name="Wan 2.6 T2V",
        provider="qwen",
        capabilities=["video-generation"],
        context_window=0,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.SLOW,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-01",
        is_best_for={"video-generation": "wan2.6-t2v"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen-mt-plus",
        display_name="Qwen MT Plus",
        provider="qwen",
        capabilities=["translation", "text"],
        context_window=32000,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=1.5,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2024-12-01",
        is_best_for={"translation": "qwen-mt-plus"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-image",
        display_name="Qwen 3 Image",
        provider="qwen",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=0.4,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-10",
        is_best_for={"image-generation": "qwen-image-2.0-pro"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-vl-flash",
        display_name="Qwen 3 VL Flash",
        provider="qwen",
        capabilities=["vision", "text"],
        context_window=32000,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=1.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-02-06",
        is_best_for={"vision": "qwen3-vl-flash"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="qwen3-omni-flash",
        display_name="Qwen 3 Omni Flash",
        provider="qwen",
        capabilities=["multimodal", "vision", "text"],
        context_window=32000,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=2.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-20",
        is_best_for={"multimodal": "qwen3-omni-flash"},
        endpoint="https://dashscope.aliyuncs.com/v1",
        auth_type="api_key",
        auth_key_env="DASHSCOPE_API_KEY",
    ))

    # ========================================================================
    # xAI / Grok
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="grok-4.20-0309-reasoning",
        display_name="Grok 4.20 (0309) Reasoning",
        provider="xai",
        capabilities=["text", "reasoning"],
        context_window=131072,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=15.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-03-09",
        is_best_for={"reasoning": "grok-4.20-0309-reasoning", "text": "grok-4.20-0309-reasoning"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-4.20-0309-non-reasoning",
        display_name="Grok 4.20 (0309) Non-Reasoning",
        provider="xai",
        capabilities=["text"],
        context_window=131072,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=15.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-03-09",
        is_best_for={"text": "grok-4.20-0309-non-reasoning"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-4.20-multi-agent-0309",
        display_name="Grok 4.20 Multi-Agent (0309)",
        provider="xai",
        capabilities=["text", "reasoning"],
        context_window=131072,
        input_cost_per_mtok=6.0,
        output_cost_per_mtok=18.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-03-09",
        is_best_for={"reasoning": "grok-4.20-0309-reasoning"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
        notes="Multi-agent optimized variant of grok-4.20.",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-4-1-fast-reasoning",
        display_name="Grok 4-1 Fast Reasoning",
        provider="xai",
        capabilities=["text", "reasoning"],
        context_window=131072,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=10.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-20",
        is_best_for={"reasoning": "grok-4-1-fast-reasoning", "fast-response": "grok-4-1-fast-reasoning"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-4-1-fast-non-reasoning",
        display_name="Grok 4-1 Fast Non-Reasoning",
        provider="xai",
        capabilities=["text"],
        context_window=131072,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=10.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-20",
        is_best_for={"text": "grok-4-1-fast-non-reasoning", "fast-response": "grok-4-1-fast-non-reasoning"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-imagine-image",
        display_name="Grok Imagine (Image)",
        provider="xai",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-02-15",
        is_best_for={"image-generation": "grok-imagine-image"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-imagine-image-pro",
        display_name="Grok Imagine Pro (Image)",
        provider="xai",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-02-15",
        is_best_for={"image-generation": "grok-imagine-image-pro"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-imagine-video",
        display_name="Grok Imagine (Video)",
        provider="xai",
        capabilities=["video-generation"],
        context_window=0,
        input_cost_per_mtok=2.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.SLOW,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-02-20",
        is_best_for={"video-generation": "grok-imagine-video"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
    ))
    # xAI built-in capabilities
    catalog.add(ModelCatalogEntry(
        name="grok-web-search",
        display_name="Grok Web Search (Built-in)",
        provider="xai",
        capabilities=["web-search"],  # special tool, not standard text
        context_window=0,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-01",
        is_best_for={"web-search": "grok-web-search"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
        notes="Built-in web search via x_search.",
    ))
    catalog.add(ModelCatalogEntry(
        name="grok-code-execution",
        display_name="Grok Code Execution (Built-in)",
        provider="xai",
        capabilities=["code-execution", "coding"],
        context_window=0,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-01",
        is_best_for={"coding": "grok-code-execution"},
        endpoint="https://api.x.ai/v1",
        auth_type="api_key",
        auth_key_env="XAI_API_KEY",
        notes="Built-in code execution via code_execution.",
    ))

    # ========================================================================
    # MiniMax
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="minimax-m2.7",
        display_name="MiniMax-M2.7",
        provider="minimax",
        capabilities=["text", "reasoning"],
        context_window=256000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=3.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-01-15",
        is_best_for={"reasoning": "minimax-m2.7", "large-context": "minimax-m2.7", "text": "minimax-m2.7"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="minimax-m2.7-highspeed",
        display_name="MiniMax-M2.7 HighSpeed",
        provider="minimax",
        capabilities=["text", "reasoning"],
        context_window=256000,
        input_cost_per_mtok=1.5,
        output_cost_per_mtok=4.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-02-01",
        is_best_for={"fast-response": "minimax-m2.7-highspeed", "reasoning": "minimax-m2.7-highspeed"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="minimax-vl-01",
        display_name="MiniMax-VL-01",
        provider="minimax",
        capabilities=["text", "vision", "reasoning"],
        context_window=256000,
        input_cost_per_mtok=1.5,
        output_cost_per_mtok=4.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.US, RegionAvailability.GLOBAL],
        release_date="2025-02-10",
        is_best_for={"vision": "minimax-vl-01"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="speech-2.8-hd",
        display_name="Speech 2.8 HD",
        provider="minimax",
        capabilities=["text-to-speech"],
        context_window=0,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-20",
        is_best_for={"text-to-speech": "speech-2.8-hd"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="speech-2.8-turbo",
        display_name="Speech 2.8 Turbo",
        provider="minimax",
        capabilities=["text-to-speech"],
        context_window=0,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-20",
        is_best_for={"text-to-speech": "speech-2.8-turbo"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="image-01",
        display_name="Image 01",
        provider="minimax",
        capabilities=["image-generation"],
        context_window=0,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-25",
        is_best_for={"image-generation": "image-01"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="hailuo-2.3",
        display_name="Hailuo 2.3",
        provider="minimax",
        capabilities=["video-generation"],
        context_window=0,
        input_cost_per_mtok=1.5,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.SLOW,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-01",
        is_best_for={"video-generation": "hailuo-2.3"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="music-2.6",
        display_name="Music 2.6",
        provider="minimax",
        capabilities=["music-generation"],
        context_window=0,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-02-05",
        is_best_for={"music-generation": "music-2.6"},
        endpoint="https://api.minimax.chat/v1",
        auth_type="api_key",
        auth_key_env="MINIMAX_API_KEY",
    ))

    # ========================================================================
    # Z.AI / GLM
    # ========================================================================
    catalog.add(ModelCatalogEntry(
        name="glm-5.1",
        display_name="GLM-5.1",
        provider="zai",
        capabilities=["text", "reasoning", "coding"],
        context_window=128000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=3.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2025-01-10",
        is_best_for={"reasoning": "glm-5.1", "coding": "glm-5.1", "text": "glm-5.1"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="glm-5",
        display_name="GLM-5",
        provider="zai",
        capabilities=["text", "reasoning", "coding"],
        context_window=128000,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=2.5,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-12-01",
        is_best_for={"reasoning": "glm-5.1", "text": "glm-5"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="glm-4.6",
        display_name="GLM-4.6",
        provider="zai",
        capabilities=["text", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=0.6,
        output_cost_per_mtok=2.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-09-01",
        is_best_for={"text": "glm-4.6"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="glm-4.6v",
        display_name="GLM-4.6V",
        provider="zai",
        capabilities=["text", "vision", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=3.0,
        latency_tier=LatencyTier.STANDARD,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP, RegionAvailability.GLOBAL],
        release_date="2024-10-01",
        is_best_for={"vision": "glm-4.6v"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="glm-4.6v-flashx",
        display_name="GLM-4.6V-FlashX",
        provider="zai",
        capabilities=["text", "vision", "reasoning"],
        context_window=128000,
        input_cost_per_mtok=0.5,
        output_cost_per_mtok=1.5,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2024-11-01",
        is_best_for={"vision": "glm-4.6v-flashx", "fast-response": "glm-4.6v-flashx"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))
    catalog.add(ModelCatalogEntry(
        name="glm-asr-2512",
        display_name="GLM-ASR-2512",
        provider="zai",
        capabilities=["speech-to-text"],
        context_window=0,
        input_cost_per_mtok=0.05,
        output_cost_per_mtok=0.0,
        latency_tier=LatencyTier.FAST,
        region_availability=[RegionAvailability.CN, RegionAvailability.AP],
        release_date="2025-01-20",
        is_best_for={"speech-to-text": "glm-asr-2512"},
        endpoint="https://open.bigmodel.cn/api/paas/v1",
        auth_type="api_key",
        auth_key_env="ZAI_API_KEY",
    ))

    return catalog


# ---------------------------------------------------------------------------
# Module-level singleton (lazily built on first access)
# ---------------------------------------------------------------------------

_MODEL_CATALOG_BUILT: ProviderModelCatalog | None = None


def _get_global_catalog() -> ProviderModelCatalog:
    global _MODEL_CATALOG_BUILT
    if _MODEL_CATALOG_BUILT is None:
        _MODEL_CATALOG_BUILT = _build_model_catalog()
    return _MODEL_CATALOG_BUILT


# Expose the singleton
MODEL_CATALOG: ProviderModelCatalog = _get_global_catalog()


# ---------------------------------------------------------------------------
# Convenience functions that operate on the global catalog
# ---------------------------------------------------------------------------

def get_provider_names() -> list[str]:
    """Return sorted list of canonical provider names in the global catalog."""
    return MODEL_CATALOG.list_providers()


def get_models_by_provider(provider: str) -> list[ModelCatalogEntry]:
    """Return all model entries for a given provider."""
    return MODEL_CATALOG.list_models(provider)


def get_models_by_capability(capability: str) -> list[ModelCatalogEntry]:
    """Return all model entries that have the given capability."""
    return [m for m in MODEL_CATALOG.list_models() if capability in m.capabilities]


def get_best_for_role(role: str, provider: str | None = None) -> ModelCatalogEntry | None:
    """Return the best model for the given role, optionally filtered by provider."""
    return MODEL_CATALOG.best_model(role=role, provider=provider)


def load_catalog() -> ProviderModelCatalog:
    """
    Return a fresh ProviderModelCatalog instance populated with all known models.

    This creates a new instance each call (a copy of the pre-populated data).
    """
    new_catalog = ProviderModelCatalog()
    for entry in MODEL_CATALOG.list_models():
        new_catalog.add(entry)
    return new_catalog


def validate_catalog(catalog: ProviderModelCatalog) -> list[str]:
    """Validate a catalog and return a list of error messages (empty if valid)."""
    return catalog.validate()
