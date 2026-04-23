from __future__ import annotations

from dataclasses import dataclass, field
from math import log2

from hermesoptimizer.sources.model_catalog import MODEL_CATALOG, ModelCatalogEntry, ProviderModelCatalog
from hermesoptimizer.sources.provider_truth import ProviderTruthStore


@dataclass(slots=True)
class RoleRequirement:
    role_name: str
    required_capabilities: list[str] = field(default_factory=list)
    min_context_window: int = 0
    prefer_fast: bool = False
    prefer_cheap: bool = False
    prefer_no_reasoning: bool = False
    max_context_window: int | None = None
    exclude_providers: list[str] = field(default_factory=list)
    user_preference: str | None = None


@dataclass(slots=True)
class EvaluatedModel:
    provider: str
    model: str
    score: int
    rationale: list[str] = field(default_factory=list)
    context_window: int = 0
    capabilities: list[str] = field(default_factory=list)


def evaluate_models(
    requirement: RoleRequirement,
    catalog: ProviderModelCatalog = MODEL_CATALOG,
    truth_store: ProviderTruthStore | None = None,
) -> list[EvaluatedModel]:
    store = truth_store or ProviderTruthStore()
    excluded_providers = {provider.strip().lower() for provider in requirement.exclude_providers}
    required_capabilities = list(dict.fromkeys(requirement.required_capabilities))

    evaluated: list[EvaluatedModel] = []
    for entry in catalog.list_models():
        if not _meets_requirements(
            entry,
            required_capabilities=required_capabilities,
            min_context_window=requirement.min_context_window,
            max_context_window=requirement.max_context_window,
            excluded_providers=excluded_providers,
            truth_store=store,
        ):
            continue

        score, rationale = _score_entry(entry, requirement, required_capabilities)
        evaluated.append(
            EvaluatedModel(
                provider=entry.provider,
                model=entry.name,
                score=score,
                rationale=rationale,
                context_window=entry.context_window,
                capabilities=list(entry.capabilities),
            )
        )

    return sorted(
        evaluated,
        key=lambda item: (-item.score, item.context_window, item.provider, item.model),
    )


def _meets_requirements(
    entry: ModelCatalogEntry,
    *,
    required_capabilities: list[str],
    min_context_window: int,
    max_context_window: int | None,
    excluded_providers: set[str],
    truth_store: ProviderTruthStore,
) -> bool:
    capabilities = set(entry.capabilities)
    if any(capability not in capabilities for capability in required_capabilities):
        return False

    if entry.context_window < min_context_window:
        return False

    if max_context_window is not None and entry.context_window > max_context_window:
        return False

    if entry.provider in excluded_providers:
        return False

    provider_record = truth_store.get(entry.provider)
    if provider_record is not None and not provider_record.canonical_endpoint:
        return False

    if entry.context_window == 0:
        return False

    return True


def _score_entry(
    entry: ModelCatalogEntry,
    requirement: RoleRequirement,
    required_capabilities: list[str],
) -> tuple[int, list[str]]:
    score = 0
    rationale: list[str] = []

    if _matches_user_preference(requirement.user_preference, entry):
        score += 10
        rationale.append("matches user preference (+10)")

    if _is_best_for_requirement(entry, requirement.role_name, required_capabilities):
        score += 5
        rationale.append("best-for match (+5)")

    capability_points = 3 * len(required_capabilities)
    if capability_points:
        score += capability_points
        rationale.append(f"required capability matches (+{capability_points})")

    if requirement.prefer_fast and "reasoning" not in entry.capabilities:
        score += 2
        rationale.append("non-reasoning model favored for speed (+2)")

    if requirement.prefer_cheap and _is_small_or_mini_variant(entry):
        score += 2
        rationale.append("small/mini variant favored for cost (+2)")

    if requirement.prefer_no_reasoning and "reasoning" in entry.capabilities:
        score -= 2
        rationale.append("reasoning capability penalized (-2)")

    if requirement.min_context_window > 0 and entry.context_window == requirement.min_context_window:
        score += 1
        rationale.append("right-sized context window (+1)")

    waste_penalty = _wasteful_context_penalty(entry.context_window, requirement.min_context_window)
    if waste_penalty:
        score -= waste_penalty
        rationale.append(f"wasteful excess context (-{waste_penalty})")

    if not rationale:
        rationale.append("meets baseline requirements")

    return score, rationale


def _matches_user_preference(user_preference: str | None, entry: ModelCatalogEntry) -> bool:
    if not user_preference:
        return False

    normalized = user_preference.strip().lower()
    provider_model = f"{entry.provider}/{entry.name}".lower()
    provider_colon_model = f"{entry.provider}:{entry.name}".lower()
    return normalized in {
        entry.name.lower(),
        entry.provider.lower(),
        provider_model,
        provider_colon_model,
    }


def _is_best_for_requirement(
    entry: ModelCatalogEntry,
    role_name: str,
    required_capabilities: list[str],
) -> bool:
    if not entry.is_best_for:
        return False

    keys_to_check = [role_name, *required_capabilities]
    return any(entry.is_best_for.get(key) == entry.name for key in keys_to_check)


def _is_small_or_mini_variant(entry: ModelCatalogEntry) -> bool:
    tokens = {
        "mini",
        "small",
        "nano",
        "lite",
        "flash",
        "haiku",
        "tiny",
        "compact",
        "highspeed",
    }
    haystacks = [entry.name.lower(), entry.display_name.lower()]
    return any(token in haystack for haystack in haystacks for token in tokens)


def _wasteful_context_penalty(context_window: int, min_context_window: int) -> int:
    if min_context_window <= 0 or context_window <= min_context_window:
        return 0

    ratio = context_window / min_context_window
    if ratio < 2:
        return 0

    return int(log2(ratio))


__all__ = [
    "EvaluatedModel",
    "RoleRequirement",
    "evaluate_models",
]
