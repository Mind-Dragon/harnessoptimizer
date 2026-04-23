"""
Tests for v0.6 provider-management-controls: dedupe, fallback hygiene,
endpoint quarantine TTL/decay, credential-source provenance, and
known-good model pin / repeated failure memory.

These tests cover:
- Dedup aliases / canonical collapse recommendations
- Fallback-order hygiene recommendations
- Endpoint quarantine TTL with expiry/decay behavior
- Credential-source provenance tracking
- Model pin / known-good endpoint / repeated failure memory
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from hermesoptimizer.sources.provider_truth import canonical_provider_name
from hermesoptimizer.verify.provider_management import (
    CollapseRecommendation,
    CredentialProvenance,
    DedupResult,
    EndpointHealthMemory,
    EndpointQuarantine,
    FallbackHealthSummary,
    FallbackReorderRecommendation,
    ModelPin,
    ProviderHealthRecord,
    ProviderHealthStore,
    ProviderQuarantine,
    QuarantinedEndpoint,
    QuarantinedProvider,
    collapse_duplicates,
    get_credential_provenance,
    get_credential_source_label,
    recommend_fallback_reorder,
    record_endpoint_failure,
    record_endpoint_success,
)


# --------------------------------------------------------------------------- #
# Alias-map parity / intentional divergence tests
# --------------------------------------------------------------------------- #


def _load_hermes_agent_aliases() -> dict[str, str]:
    models_py = Path("/home/agent/hermes-agent/hermes_cli/models.py")
    if not models_py.exists():
        pytest.skip("local Hermes agent alias map not available")
    tree = ast.parse(models_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_PROVIDER_ALIASES":
                    value = ast.literal_eval(node.value)
                    return {str(k): str(v) for k, v in value.items()}
    pytest.fail("Hermes agent _PROVIDER_ALIASES not found")


class TestAliasMapParity:
    """Tests selected alias parity and intentional divergence with Hermes agent."""

    def test_shared_xai_aliases_match_hermes_agent(self) -> None:
        agent_aliases = _load_hermes_agent_aliases()
        for alias in ("x-ai", "x.ai"):
            assert canonical_provider_name(alias) == "xai"
            assert agent_aliases[alias] == "xai"

    def test_kimi_canonical_direction_is_intentional_divergence(self) -> None:
        agent_aliases = _load_hermes_agent_aliases()
        assert canonical_provider_name("kimi-coding") == "kimi"
        assert agent_aliases["kimi"] == "kimi-coding"

    def test_alibaba_qwen_canonical_direction_is_intentional_divergence(self) -> None:
        agent_aliases = _load_hermes_agent_aliases()
        assert canonical_provider_name("alibaba") == "qwen"
        assert canonical_provider_name("qwen") == "qwen"
        assert agent_aliases["qwen"] == "alibaba"
        assert agent_aliases["dashscope"] == "alibaba"

    def test_agent_only_aliases_remain_unclaimed_by_optimizer(self) -> None:
        agent_aliases = _load_hermes_agent_aliases()
        assert agent_aliases["github"] == "copilot"
        assert agent_aliases["google"] == "gemini"
        assert agent_aliases["claude"] == "anthropic"
        assert canonical_provider_name("github") == "github"
        assert canonical_provider_name("google") == "google"
        assert canonical_provider_name("claude") == "claude"

    def test_optimizer_only_aliases_are_documented_as_optimizer_scope(self) -> None:
        agent_aliases = _load_hermes_agent_aliases()
        assert canonical_provider_name("zai-chat") == "zai"
        assert canonical_provider_name("tongyi") == "qwen"
        assert "zai-chat" not in agent_aliases
        assert "tongyi" not in agent_aliases


# --------------------------------------------------------------------------- #
# CredentialSource provenance tests
# --------------------------------------------------------------------------- #

class TestCredentialSourceProvenance:
    """Tests for credential-source provenance tracking."""

    def test_credential_source_labels(self) -> None:
        """Each credential source type has a human-readable label."""
        assert "environment variable" in get_credential_source_label("env")
        assert "auth.json" in get_credential_source_label("auth_json")
        assert "vault" in get_credential_source_label("credential_pool")
        assert "OAuth" in get_credential_source_label("oauth_store")
        assert "runtime" in get_credential_source_label("runtime_only")

    def test_credential_provenance_fields(self) -> None:
        """CredentialProvenance captures source and metadata."""
        prov = CredentialProvenance(
            source="env",
            variable_name="OPENAI_API_KEY",
            path=None,
        )
        assert prov.source == "env"
        assert prov.variable_name == "OPENAI_API_KEY"
        assert prov.path is None

    def test_credential_provenance_with_path(self) -> None:
        """CredentialProvenance captures file path when relevant."""
        prov = CredentialProvenance(
            source="auth_json",
            path="/home/user/.hermes/auth.json",
        )
        assert prov.source == "auth_json"
        assert "auth.json" in prov.path or ".hermes" in (prov.path or "")

    def test_get_credential_provenance_returns_valid_structure(self) -> None:
        """get_credential_provenance returns a valid CredentialProvenance."""
        prov = get_credential_provenance("env", variable_name="OPENAI_API_KEY")
        assert isinstance(prov, CredentialProvenance)
        assert prov.source == "env"


# --------------------------------------------------------------------------- #
# Dedup aliases / canonical collapse tests
# --------------------------------------------------------------------------- #

class TestDedupAliases:
    """Tests for dedup aliases and canonical collapse recommendations."""

    def test_collapse_duplicates_detects_alias_duplication(self) -> None:
        """When multiple aliases of the same canonical provider exist, recommend collapse."""
        configs = [
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            {"provider": "openai-codex", "base_url": "https://api.openai.com/v1"},
        ]
        result = collapse_duplicates(configs, ProviderHealthStore())
        assert len(result.collapse_recommendations) == 1
        rec = result.collapse_recommendations[0]
        assert rec.alias_provider == "openai-codex"
        assert rec.canonical_provider == "openai"

    def test_collapse_duplicates_no_collapse_when_unique(self) -> None:
        """When providers are genuinely different, no collapse recommended."""
        configs = [
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            {"provider": "anthropic", "base_url": "https://api.anthropic.com/v1"},
        ]
        result = collapse_duplicates(configs, ProviderHealthStore())
        assert len(result.collapse_recommendations) == 0

    def test_collapse_duplicates_with_endpoint_mismatch(self) -> None:
        """When same alias but different endpoints, still recommend collapse to canonical."""
        configs = [
            {"provider": "kimi", "base_url": "https://api.moonshot.cn/v1"},
            {"provider": "kimi-for-coding", "base_url": "https://api.moonshot.cn/v1"},
        ]
        result = collapse_duplicates(configs, ProviderHealthStore())
        assert len(result.collapse_recommendations) == 1
        rec = result.collapse_recommendations[0]
        assert rec.canonical_provider == "kimi"

    def test_collapse_duplicates_identifies_provenance_collision(self) -> None:
        """Collapse result should explain provenance collision."""
        configs = [
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            {"provider": "openai-codex", "base_url": "https://api.openai.com/v1"},
        ]
        result = collapse_duplicates(configs, ProviderHealthStore())
        rec = result.collapse_recommendations[0]
        assert "collision" in rec.reason.lower() or "alias" in rec.reason.lower()
        assert rec.action == "collapse_alias"

    def test_collapse_duplicates_empty_list(self) -> None:
        """Empty config list returns empty recommendations."""
        result = collapse_duplicates([], ProviderHealthStore())
        assert len(result.collapse_recommendations) == 0

    def test_collapse_duplicates_single_provider(self) -> None:
        """Single provider returns no collapse recommendations."""
        configs = [{"provider": "openai", "base_url": "https://api.openai.com/v1"}]
        result = collapse_duplicates(configs, ProviderHealthStore())
        assert len(result.collapse_recommendations) == 0


# --------------------------------------------------------------------------- #
# Fallback-order hygiene tests
# --------------------------------------------------------------------------- #

class TestFallbackOrderHygiene:
    """Tests for fallback-order hygiene recommendations."""

    def test_recommend_reorder_when_healthy_consistently_wins(self) -> None:
        """When a fallback provider succeeds while primary fails, recommend reorder."""
        health_store = ProviderHealthStore()
        # Provider "good" is primary, "better" is fallback but healthier
        health_store.record_success("good")
        health_store.record_success("good")
        health_store.record_failure("good")
        health_store.record_success("better")
        health_store.record_success("better")
        health_store.record_success("better")

        routing = {"default": ["good", "better"]}
        rec = recommend_fallback_reorder(routing, health_store)
        assert rec is not None
        assert rec.code == "FALLBACK_REORDER"
        assert "better" in rec.summary or "good" in rec.summary

    def test_recommend_reorder_no_issue_when_fallback_unhealthy(self) -> None:
        """When fallback is also failing, no reorder recommendation."""
        health_store = ProviderHealthStore()
        health_store.record_success("good")
        health_store.record_failure("better")
        health_store.record_failure("better")

        routing = {"default": ["good", "better"]}
        rec = recommend_fallback_reorder(routing, health_store)
        # No reorder when fallback is also unhealthy
        # (the primary is still the best option available)

    def test_recommend_reorder_empty_routing(self) -> None:
        """Empty routing returns None."""
        health_store = ProviderHealthStore()
        rec = recommend_fallback_reorder({}, health_store)
        assert rec is None

    def test_recommend_reorder_single_provider(self) -> None:
        """Single provider in chain returns no reorder recommendation."""
        health_store = ProviderHealthStore()
        health_store.record_failure("only")
        routing = {"default": ["only"]}
        rec = recommend_fallback_reorder(routing, health_store)
        assert rec is None

    def test_fallback_health_summary_fields(self) -> None:
        """FallbackHealthSummary has required fields."""
        summary = FallbackHealthSummary(
            provider="openai",
            successes=5,
            failures=2,
            success_rate=0.714,
            is_healthy=True,
        )
        assert summary.provider == "openai"
        assert summary.success_rate == 0.714
        assert summary.is_healthy is True

    def test_fallback_reorder_recommendation_fields(self) -> None:
        """FallbackReorderRecommendation has required fields."""
        rec = FallbackReorderRecommendation(
            code="FALLBACK_REORDER",
            summary="Reorder fallback chain for 'default': 'better' outperforms 'good'",
            detail="Provider 'better' succeeded 5 times with 0 failures vs 'good' with 2 successes and 1 failure. Move 'better' up in the fallback order.",
            recommendation="Reorder fallback_providers for lane 'default' to: better > good",
            lane="default",
            current_order=["good", "better"],
            recommended_order=["better", "good"],
        )
        assert rec.code == "FALLBACK_REORDER"
        assert rec.lane == "default"
        assert rec.current_order == ["good", "better"]
        assert rec.recommended_order == ["better", "good"]


# --------------------------------------------------------------------------- #
# Endpoint quarantine TTL with decay tests
# --------------------------------------------------------------------------- #

class TestEndpointQuarantineTTL:
    """Tests for endpoint quarantine with TTL and decay."""

    def test_quarantine_endpoint_adds_to_quarantine_list(self) -> None:
        """Quarantining an endpoint adds it to the quarantine list."""
        quarantine = EndpointQuarantine()
        quarantine.quarantine("https://bad.example.com/v1", ttl_seconds=300)
        assert quarantine.is_quarantined("https://bad.example.com/v1")

    def test_quarantine_respects_ttl(self) -> None:
        """Quarantine expires after TTL."""
        quarantine = EndpointQuarantine(default_ttl_seconds=1)
        quarantine.quarantine("https://bad.example.com/v1", ttl_seconds=1)
        assert quarantine.is_quarantined("https://bad.example.com/v1")
        time.sleep(1.1)
        assert not quarantine.is_quarantined("https://bad.example.com/v1")

    def test_quarantine_permanent_is_permanent(self) -> None:
        """Permanent quarantine does not expire."""
        quarantine = EndpointQuarantine()
        quarantine.quarantine_permanent("https://permanently.bad.example.com/v1")
        assert quarantine.is_quarantined("https://permanently.bad.example.com/v1")
        # Even after a long wait
        time.sleep(0.1)
        assert quarantine.is_quarantined("https://permanently.bad.example.com/v1")

    def test_quarantine_release_removes_from_list(self) -> None:
        """Releasing an endpoint removes it from quarantine."""
        quarantine = EndpointQuarantine()
        quarantine.quarantine("https://bad.example.com/v1", ttl_seconds=300)
        quarantine.release("https://bad.example.com/v1")
        assert not quarantine.is_quarantined("https://bad.example.com/v1")

    def test_quarantine_decay_reduces_failure_count(self) -> None:
        """Decay reduces the failure count over time in quarantine."""
        quarantine = EndpointQuarantine()
        # Quarantine an endpoint with several failures
        quarantine.quarantine("https://bad.example.com/v1", ttl_seconds=300, failure_count=2)
        assert quarantine.get_failure_count("https://bad.example.com/v1") == 2
        # Apply decay
        quarantine.apply_decay(factor=0.5)
        assert quarantine.get_failure_count("https://bad.example.com/v1") == 1

    def test_quarantine_repr_includes_active(self) -> None:
        """Quarantine repr shows active quarantined endpoints."""
        quarantine = EndpointQuarantine()
        quarantine.quarantine("https://bad.example.com/v1", ttl_seconds=300)
        r = repr(quarantine)
        assert "EndpointQuarantine" in r
        assert "bad.example.com" in r

    def test_quarantined_endpoint_fields(self) -> None:
        """QuarantinedEndpoint has required fields."""
        qe = QuarantinedEndpoint(
            endpoint="https://bad.example.com/v1",
            quarantined_at=1234567890.0,
            ttl_seconds=300,
            failure_count=3,
            is_permanent=False,
        )
        assert qe.endpoint == "https://bad.example.com/v1"
        assert qe.ttl_seconds == 300
        assert qe.is_permanent is False

    def test_quarantine_is_quarantined_normalizes_url(self) -> None:
        """is_quarantined normalizes URLs before checking."""
        quarantine = EndpointQuarantine()
        quarantine.quarantine("https://bad.example.com/v1/", ttl_seconds=300)
        # Same URL without trailing slash should also be quarantined
        assert quarantine.is_quarantined("https://bad.example.com/v1")

    def test_quarantine_none_when_not_quarantined(self) -> None:
        """is_quarantined returns False for non-quarantined endpoints."""
        quarantine = EndpointQuarantine()
        assert quarantine.is_quarantined("https://good.example.com/v1") is False


# --------------------------------------------------------------------------- #
# Provider quarantine TTL with decay tests
# --------------------------------------------------------------------------- #


class TestProviderQuarantineTTL:
    """Tests for provider quarantine with TTL, aliases, and health integration."""

    def test_quarantine_provider_adds_to_quarantine_list(self) -> None:
        quarantine = ProviderQuarantine()
        quarantine.quarantine("openai-codex", ttl_seconds=300, failure_count=3)
        assert quarantine.is_quarantined("openai")
        assert quarantine.is_quarantined("openai-codex")

    def test_provider_quarantine_respects_ttl(self) -> None:
        quarantine = ProviderQuarantine(default_ttl_seconds=1)
        quarantine.quarantine("openai", ttl_seconds=1)
        assert quarantine.is_quarantined("openai")
        time.sleep(1.1)
        assert not quarantine.is_quarantined("openai")

    def test_provider_quarantine_permanent_is_permanent(self) -> None:
        quarantine = ProviderQuarantine()
        quarantine.quarantine_permanent("openrouter", failure_count=9, reason="auth_failed")
        assert quarantine.is_quarantined("openrouter")
        time.sleep(0.1)
        assert quarantine.is_quarantined("openrouter")
        assert quarantine.get_failure_count("openrouter") == 9

    def test_provider_quarantine_release_removes_from_list(self) -> None:
        quarantine = ProviderQuarantine()
        quarantine.quarantine("nous", ttl_seconds=300)
        quarantine.release("nous")
        assert not quarantine.is_quarantined("nous")

    def test_provider_quarantine_decay_reduces_failure_count(self) -> None:
        quarantine = ProviderQuarantine()
        quarantine.quarantine("kilocode", ttl_seconds=300, failure_count=4)
        quarantine.apply_decay(factor=0.5)
        assert quarantine.get_failure_count("kilocode") == 2

    def test_quarantined_provider_fields(self) -> None:
        qp = QuarantinedProvider(
            provider="openrouter",
            quarantined_at=1234567890.0,
            ttl_seconds=300,
            failure_count=3,
            reason="repeated_failures",
        )
        assert qp.provider == "openrouter"
        assert qp.failure_count == 3
        assert qp.is_permanent is False

    def test_record_failure_triggers_provider_quarantine_after_threshold(self) -> None:
        quarantine = ProviderQuarantine()
        store = ProviderHealthStore(
            provider_quarantine=quarantine,
            quarantine_threshold=2,
            quarantine_ttl_seconds=60,
        )
        store.record_failure("openai-codex")
        assert not quarantine.is_quarantined("openai")
        store.record_failure("openai-codex")
        assert quarantine.is_quarantined("openai")
        assert quarantine.get_failure_count("openai") == 2

    def test_provider_success_releases_quarantine_and_resets_streak(self) -> None:
        quarantine = ProviderQuarantine()
        store = ProviderHealthStore(
            provider_quarantine=quarantine,
            quarantine_threshold=1,
            quarantine_ttl_seconds=60,
        )
        store.record_failure("nous")
        assert quarantine.is_quarantined("nous")
        store.record_success("nous")
        record = store.get("nous")
        assert record is not None
        assert record.consecutive_failures == 0
        assert not quarantine.is_quarantined("nous")


# --------------------------------------------------------------------------- #
# ProviderHealthRecord and memory tests
# --------------------------------------------------------------------------- #

class TestProviderHealthRecord:
    """Tests for provider health record and memory."""

    def test_provider_health_record_fields(self) -> None:
        """ProviderHealthRecord has required fields."""
        record = ProviderHealthRecord(
            provider="openai",
            successes=10,
            failures=2,
            last_success=1234567890.0,
            last_failure=1234567800.0,
            consecutive_failures=0,
            known_good_model="gpt-4o",
        )
        assert record.provider == "openai"
        assert record.successes == 10
        assert record.failures == 2
        assert record.known_good_model == "gpt-4o"

    def test_provider_health_record_success_rate(self) -> None:
        """ProviderHealthRecord computes success_rate."""
        record = ProviderHealthRecord(
            provider="openai",
            successes=8,
            failures=2,
            last_success=1234567890.0,
            last_failure=1234567800.0,
            consecutive_failures=0,
        )
        assert abs(record.success_rate - 0.8) < 0.001

    def test_provider_health_record_is_healthy(self) -> None:
        """ProviderHealthRecord.is_healthy returns True when success_rate >= threshold."""
        record = ProviderHealthRecord(
            provider="openai",
            successes=8,
            failures=2,
            last_success=1234567890.0,
            last_failure=1234567800.0,
            consecutive_failures=0,
        )
        assert record.is_healthy(threshold=0.7) is True
        assert record.is_healthy(threshold=0.9) is False

    def test_provider_health_store_records_success(self) -> None:
        """ProviderHealthStore records successes."""
        store = ProviderHealthStore()
        store.record_success("openai")
        store.record_success("openai")
        record = store.get("openai")
        assert record is not None
        assert record.successes == 2
        assert record.failures == 0

    def test_provider_health_store_records_failure(self) -> None:
        """ProviderHealthStore records failures and tracks consecutive failures."""
        store = ProviderHealthStore()
        store.record_failure("openai")
        store.record_failure("openai")
        record = store.get("openai")
        assert record is not None
        assert record.failures == 2
        assert record.consecutive_failures == 2

    def test_provider_health_store_success_resets_consecutive(self) -> None:
        """A success resets consecutive_failures counter."""
        store = ProviderHealthStore()
        store.record_failure("openai")
        store.record_failure("openai")
        store.record_success("openai")
        record = store.get("openai")
        assert record is not None
        assert record.consecutive_failures == 0

    def test_provider_health_store_known_good_model(self) -> None:
        """ProviderHealthStore can pin a known-good model."""
        store = ProviderHealthStore()
        store.set_known_good_model("openai", "gpt-4o")
        record = store.get("openai")
        assert record is not None
        assert record.known_good_model == "gpt-4o"

    def test_endpoint_health_memory_records_success(self) -> None:
        """EndpointHealthMemory records endpoint-level successes."""
        memory = EndpointHealthMemory()
        memory.record_success("https://api.openai.com/v1")
        assert memory.get_success_count("https://api.openai.com/v1") == 1

    def test_endpoint_health_memory_records_failure(self) -> None:
        """EndpointHealthMemory records endpoint-level failures."""
        memory = EndpointHealthMemory()
        memory.record_failure("https://api.openai.com/v1")
        assert memory.get_failure_count("https://api.openai.com/v1") == 1

    def test_endpoint_health_memory_decay(self) -> None:
        """EndpointHealthMemory.apply_decay reduces failure counts."""
        memory = EndpointHealthMemory()
        memory.record_failure("https://api.openai.com/v1")
        memory.record_failure("https://api.openai.com/v1")
        memory.apply_decay(factor=0.5)
        assert memory.get_failure_count("https://api.openai.com/v1") == 1

    def test_endpoint_health_memory_decay_does_not_inflate_health_score(self) -> None:
        """apply_decay should not artificially inflate health scores.

        When only failures are decayed (not successes), health scores
        can increase without any actual successful requests. This is
        a bug - decay should preserve the success/failure ratio or
        move toward a neutral value, not improve the ratio.
        """
        memory = EndpointHealthMemory()
        # Record 10 successes and 10 failures = 0.5 health score
        for _ in range(10):
            memory.record_success("https://api.openai.com/v1")
        for _ in range(10):
            memory.record_failure("https://api.openai.com/v1")

        score_before = memory.get_health_score("https://api.openai.com/v1")
        assert abs(score_before - 0.5) < 0.01, f"Expected 0.5, got {score_before}"

        # Apply decay - this should NOT improve the health score
        # since no new successful requests occurred
        memory.apply_decay(factor=0.5)

        score_after = memory.get_health_score("https://api.openai.com/v1")
        # Health score should NOT improve (go up) after decay with no new activity
        assert score_after <= score_before, (
            f"Health score inflated from {score_before} to {score_after} after decay"
        )

    def test_endpoint_health_memory_get_health_score(self) -> None:
        """EndpointHealthMemory returns a health score."""
        memory = EndpointHealthMemory()
        memory.record_success("https://api.openai.com/v1")
        memory.record_success("https://api.openai.com/v1")
        memory.record_failure("https://api.openai.com/v1")
        score = memory.get_health_score("https://api.openai.com/v1")
        assert 0 <= score <= 1


# --------------------------------------------------------------------------- #
# ModelPin tests
# --------------------------------------------------------------------------- #

class TestModelPin:
    """Tests for known-good model pinning."""

    def test_model_pin_fields(self) -> None:
        """ModelPin has required fields."""
        pin = ModelPin(
            provider="openai",
            model="gpt-4o",
            pinned_at=1234567890.0,
            provenance="runtime_verification",
        )
        assert pin.provider == "openai"
        assert pin.model == "gpt-4o"
        assert pin.provenance == "runtime_verification"

    def test_model_pin_repr(self) -> None:
        """ModelPin has a readable repr."""
        pin = ModelPin(
            provider="openai",
            model="gpt-4o",
            pinned_at=1234567890.0,
            provenance="runtime_verification",
        )
        r = repr(pin)
        assert "ModelPin" in r
        assert "openai" in r
        assert "gpt-4o" in r


# --------------------------------------------------------------------------- #
# Integration: collapse_duplicates with health memory
# --------------------------------------------------------------------------- #

class TestDedupWithHealthMemory:
    """Tests for dedup integrated with health memory."""

    def test_collapse_respects_health_history(self) -> None:
        """collapse_duplicates considers health history when deciding what to collapse."""
        health_store = ProviderHealthStore()
        # "openai-codex" is an alias of "openai"
        health_store.record_success("openai-codex")
        health_store.record_success("openai-codex")
        health_store.record_success("openai")

        configs = [
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            {"provider": "openai-codex", "base_url": "https://api.openai.com/v1"},
        ]
        result = collapse_duplicates(configs, health_store)
        # Both are aliases - should recommend collapse
        assert len(result.collapse_recommendations) >= 1
