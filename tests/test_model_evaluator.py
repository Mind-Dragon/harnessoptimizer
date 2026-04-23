from __future__ import annotations

from hermesoptimizer.model_evaluator import RoleRequirement, evaluate_models
from hermesoptimizer.sources.model_catalog import ModelCatalogEntry, ProviderModelCatalog
from hermesoptimizer.sources.provider_truth import ProviderTruthRecord, ProviderTruthStore


def _entry(
    *,
    name: str,
    provider: str = "test-provider",
    capabilities: list[str],
    context_window: int,
    is_best_for: dict[str, str] | None = None,
    display_name: str | None = None,
) -> ModelCatalogEntry:
    return ModelCatalogEntry(
        name=name,
        display_name=display_name or name,
        provider=provider,
        capabilities=capabilities,
        context_window=context_window,
        is_best_for=is_best_for,
    )


def _catalog(*entries: ModelCatalogEntry) -> ProviderModelCatalog:
    catalog = ProviderModelCatalog()
    for entry in entries:
        catalog.add(entry)
    return catalog


def _truth_store(*, unavailable_providers: list[str] | None = None) -> ProviderTruthStore:
    unavailable = set(unavailable_providers or [])
    store = ProviderTruthStore()
    for provider in {"test-provider", "alt-provider", *unavailable}:
        store.add(
            ProviderTruthRecord(
                provider=provider,
                canonical_endpoint="" if provider in unavailable else f"https://{provider}.example.com",
                known_models=[],
            )
        )
    return store


class TestModelEvaluator:
    def test_context_window_filtering_excludes_models_below_minimum(self) -> None:
        catalog = _catalog(
            _entry(name="text-128k", capabilities=["text"], context_window=128_000),
            _entry(name="text-256k", capabilities=["text"], context_window=256_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=200_000,
            ),
            catalog,
            _truth_store(),
        )

        assert [result.model for result in results] == ["text-256k"]

    def test_capability_filtering_excludes_text_only_model_when_vision_required(self) -> None:
        catalog = _catalog(
            _entry(name="text-only", capabilities=["text"], context_window=64_000),
            _entry(name="vision-text", capabilities=["text", "vision"], context_window=64_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="vision",
                required_capabilities=["text", "vision"],
                min_context_window=32_000,
            ),
            catalog,
            _truth_store(),
        )

        assert [result.model for result in results] == ["vision-text"]

    def test_user_preference_gets_top_score(self) -> None:
        catalog = _catalog(
            _entry(name="preferred-model", capabilities=["text"], context_window=64_000),
            _entry(name="other-model", capabilities=["text"], context_window=64_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=64_000,
                user_preference="preferred-model",
            ),
            catalog,
            _truth_store(),
        )

        assert results[0].model == "preferred-model"
        assert results[0].score > results[1].score

    def test_is_best_for_bonus_improves_ranking(self) -> None:
        catalog = _catalog(
            _entry(
                name="coding-best",
                capabilities=["text", "coding"],
                context_window=64_000,
                is_best_for={"coding": "coding-best"},
            ),
            _entry(name="coding-plain", capabilities=["text", "coding"], context_window=64_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="coding",
                required_capabilities=["coding"],
                min_context_window=64_000,
            ),
            catalog,
            _truth_store(),
        )

        assert results[0].model == "coding-best"
        assert results[0].score == results[1].score + 5

    def test_fast_cheap_and_no_reasoning_preferences_stack(self) -> None:
        catalog = _catalog(
            _entry(
                name="fast-mini",
                display_name="Fast Mini",
                capabilities=["text"],
                context_window=64_000,
            ),
            _entry(name="standard", capabilities=["text"], context_window=64_000),
            _entry(name="reasoner", capabilities=["text", "reasoning"], context_window=64_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=64_000,
                prefer_fast=True,
                prefer_cheap=True,
                prefer_no_reasoning=True,
            ),
            catalog,
            _truth_store(),
        )

        assert [result.model for result in results] == ["fast-mini", "standard", "reasoner"]
        assert results[0].score > results[1].score > results[2].score

    def test_returns_empty_list_when_nothing_fits(self) -> None:
        catalog = _catalog(
            _entry(name="text-only", capabilities=["text"], context_window=64_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="vision",
                required_capabilities=["vision"],
                min_context_window=128_000,
            ),
            catalog,
            _truth_store(),
        )

        assert results == []

    def test_right_sized_context_window_is_preferred(self) -> None:
        catalog = _catalog(
            _entry(name="exact-fit", capabilities=["text"], context_window=100_000),
            _entry(name="larger-fit", capabilities=["text"], context_window=150_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=100_000,
            ),
            catalog,
            _truth_store(),
        )

        assert results[0].model == "exact-fit"
        assert results[0].score == results[1].score + 1

    def test_wasteful_context_window_penalty_applies_per_two_x_over_minimum(self) -> None:
        catalog = _catalog(
            _entry(name="right-sized", capabilities=["text"], context_window=100_000),
            _entry(name="wasteful", capabilities=["text"], context_window=400_000),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=100_000,
            ),
            catalog,
            _truth_store(),
        )

        assert results[0].model == "right-sized"
        assert results[1].model == "wasteful"
        assert results[0].score == results[1].score + 3

    def test_unavailable_provider_and_zero_context_model_are_filtered(self) -> None:
        catalog = _catalog(
            _entry(name="good", provider="test-provider", capabilities=["text"], context_window=64_000),
            _entry(name="blocked", provider="alt-provider", capabilities=["text"], context_window=64_000),
            _entry(name="embedding-only", capabilities=["embedding"], context_window=0),
        )

        results = evaluate_models(
            RoleRequirement(
                role_name="general",
                required_capabilities=["text"],
                min_context_window=32_000,
            ),
            catalog,
            _truth_store(unavailable_providers=["alt-provider"]),
        )

        assert [result.model for result in results] == ["good"]
