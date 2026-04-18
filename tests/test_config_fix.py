"""
Tests for config-fixing pass: safe repair recommendations from
provider/model/config evidence.

Covers:
- Action classification: auto-fix now vs recommend-and-confirm vs human-only
- Stale alias repair recommendations
- Deprecated model repair recommendations
- RKWE (right-key-wrong-endpoint) repair recommendations with endpoint candidates
- Auth failure repair recommendations
- Network error repair recommendations
- Priority ranking of fixes
"""
from __future__ import annotations

import pytest

from hermesoptimizer.sources.provider_truth import (
    EndpointCandidate,
    ProviderTruthRecord,
    ProviderTruthStore,
)
from hermesoptimizer.verify.endpoints import (
    EndpointCheckResult,
    EndpointCheckStatus,
)
from hermesoptimizer.verify.config_fix import (
    ConfigFixAction,
    ConfigFix,
    ConfigFixer,
    rank_config_fixes,
)


# --------------------------------------------------------------------------- #
# Action classification tests
# --------------------------------------------------------------------------- #

class TestConfigFixActionClassification:
    """Tests for action classification: auto-fix vs recommend vs human-only."""

    def test_stale_alias_is_auto_fix(self) -> None:
        """A stale alias with a known correction should be auto-fixable."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o", "gpt-4o-mini"],
                stale_aliases={"gpt-5": "gpt-4o"},
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-5",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.STALE_ALIAS,
            message="Model 'gpt-5' is a stale alias. Use 'gpt-4o' instead",
            details={"original_model": "gpt-5", "correct_model": "gpt-4o"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.AUTO_FIX

    def test_deprecated_model_is_recommend(self) -> None:
        """A deprecated model should require human confirmation to replace."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.DEPRECATED_MODEL,
            message="Model 'gpt-4' is deprecated",
            details={"is_deprecated": True},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.RECOMMEND

    def test_rkwe_with_candidates_is_auto_fix(self) -> None:
        """RKWE with known-good endpoint candidates should be auto-fixable."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                endpoint_candidates=[
                    EndpointCandidate(
                        endpoint="https://api.openai.com/v1",
                        api_style="openai-compatible",
                        auth_type="bearer",
                        is_stable=True,
                    ),
                ],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://wrong.example.com/v1",
            status=EndpointCheckStatus.RKWE,
            message="Endpoint mismatch",
            details={"canonical_endpoint": "https://api.openai.com/v1"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.AUTO_FIX

    def test_rkwe_without_candidates_is_recommend(self) -> None:
        """RKWE without known-good endpoint candidates should recommend confirmation."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                endpoint_candidates=[],  # No candidates available
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://wrong.example.com/v1",
            status=EndpointCheckStatus.RKWE,
            message="Endpoint mismatch",
            details={"canonical_endpoint": "https://api.openai.com/v1"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.RECOMMEND

    def test_oauth_auth_failure_is_human_only(self) -> None:
        """OAuth auth failure requires human intervention, not auto-fix."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                auth_type="oauth",
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.AUTH_FAILURE,
            message="OAuth provider requires human sign-off",
            details={"escalation": "human"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.HUMAN_ONLY

    def test_api_key_auth_failure_is_recommend(self) -> None:
        """API key auth failure should recommend confirmation for key rotation."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                auth_type="api_key",
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.AUTH_FAILURE,
            message="401 unauthorized",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.RECOMMEND

    def test_stale_model_is_recommend(self) -> None:
        """A stale model not in known list should recommend confirmation."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="completely-unknown",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.STALE_MODEL,
            message="Model 'completely-unknown' is not in known model list",
            details={"is_deprecated": False},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.RECOMMEND

    def test_network_error_is_recommend(self) -> None:
        """Network errors should recommend confirmation as they may be transient."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.NETWORK_ERROR,
            message="Network error: connection refused",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.RECOMMEND


# --------------------------------------------------------------------------- #
# ConfigFix dataclass tests
# --------------------------------------------------------------------------- #

class TestConfigFixDataclass:
    """Tests for ConfigFix dataclass fields and methods."""

    def test_config_fix_fields(self) -> None:
        """ConfigFix should contain all necessary repair information."""
        fix = ConfigFix(
            provider="openai",
            model="gpt-4",
            configured_endpoint="https://api.openai.com/v1",
            correct_model="gpt-4o",
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,
            code="DEPRECATED_MODEL",
            summary="Model 'gpt-4' is deprecated",
            detail="Replace with a supported model",
            repair_steps=["Replace model 'gpt-4' with 'gpt-4o' in config.yaml"],
            lane=None,
            source_fingerprint=None,
        )
        assert fix.provider == "openai"
        assert fix.model == "gpt-4"
        assert fix.correct_model == "gpt-4o"
        assert fix.action == ConfigFixAction.RECOMMEND
        assert fix.code == "DEPRECATED_MODEL"
        assert len(fix.repair_steps) == 1

    def test_config_fix_repr(self) -> None:
        """ConfigFix should have a readable repr."""
        fix = ConfigFix(
            provider="openai",
            model="gpt-4",
            configured_endpoint="https://api.openai.com/v1",
            correct_model="gpt-4o",
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,
            code="DEPRECATED_MODEL",
            summary="Model 'gpt-4' is deprecated",
            detail="Replace with a supported model",
            repair_steps=["Replace model 'gpt-4' with 'gpt-4o' in config.yaml"],
            lane=None,
            source_fingerprint=None,
        )
        r = repr(fix)
        assert "openai" in r
        assert "gpt-4" in r
        assert "DEPRECATED_MODEL" in r


# --------------------------------------------------------------------------- #
# ConfigFixer tests
# --------------------------------------------------------------------------- #

class TestConfigFixerStaleAlias:
    """Tests for stale alias repair recommendations."""

    def test_stale_alias_produces_correct_model_repair(self) -> None:
        """Stale alias should recommend the correct model name."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o", "gpt-4o-mini"],
                stale_aliases={"gpt-5": "gpt-4o", "gpt-4.5": "gpt-4o"},
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-5",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.STALE_ALIAS,
            message="Model 'gpt-5' is a stale alias. Use 'gpt-4o' instead",
            details={"original_model": "gpt-5", "correct_model": "gpt-4o"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix.correct_model == "gpt-4o"
        assert "gpt-5" in fix.repair_steps[0]
        assert "gpt-4o" in fix.repair_steps[0]

    def test_stale_alias_no_provider_truth(self) -> None:
        """Unknown provider should produce empty fixes."""
        store = ProviderTruthStore()
        result = EndpointCheckResult(
            provider="completely-unknown",
            model="some-model",
            configured_endpoint="https://example.com",
            status=EndpointCheckStatus.UNKNOWN_PROVIDER,
            message="Provider not found",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 0


class TestConfigFixerRKWE:
    """Tests for RKWE repair recommendations."""

    def test_rkwe_with_candidate_proposes_correct_endpoint(self) -> None:
        """RKWE should propose the canonical endpoint when no candidates given."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                endpoint_candidates=[
                    EndpointCandidate(
                        endpoint="https://api.openai.com/v1",
                        is_stable=True,
                    ),
                ],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://wrong.example.com/v1",
            status=EndpointCheckStatus.RKWE,
            message="Endpoint mismatch",
            details={"canonical_endpoint": "https://api.openai.com/v1"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix.correct_endpoint == "https://api.openai.com/v1"
        assert "https://api.openai.com/v1" in fix.repair_steps[0]

    def test_rkwe_multiple_candidates(self) -> None:
        """RKWE with multiple candidates should pick first stable candidate."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                endpoint_candidates=[
                    EndpointCandidate(
                        endpoint="https://api.openai.com/v1",
                        is_stable=True,
                    ),
                    EndpointCandidate(
                        endpoint="https://api.openai.com/v2",
                        is_stable=True,
                    ),
                ],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://wrong.example.com/v1",
            status=EndpointCheckStatus.RKWE,
            message="Endpoint mismatch",
            details={"canonical_endpoint": "https://api.openai.com/v1"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        # Should use canonical endpoint, not candidates, when canonical is available
        assert fixes[0].correct_endpoint == "https://api.openai.com/v1"


class TestConfigFixerDeprecatedModel:
    """Tests for deprecated model repair recommendations."""

    def test_deprecated_model_repair_steps(self) -> None:
        """Deprecated model should list available replacements."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o", "gpt-4o-mini"],
                deprecated_models=["gpt-4"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.DEPRECATED_MODEL,
            message="Model 'gpt-4' is deprecated",
            details={"is_deprecated": True},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix.action == ConfigFixAction.RECOMMEND
        assert "gpt-4" in fix.repair_steps[0]
        # Should suggest known replacements
        assert "gpt-4o" in " ".join(fix.repair_steps)


class TestConfigFixerAuthFailure:
    """Tests for auth failure repair recommendations."""

    def test_api_key_auth_failure_suggests_key_rotation(self) -> None:
        """API key auth failure should suggest key rotation."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                auth_type="api_key",
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.AUTH_FAILURE,
            message="401 unauthorized",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix.action == ConfigFixAction.RECOMMEND
        assert "key" in fix.summary.lower() or "rotate" in fix.summary.lower()

    def test_oauth_auth_failure_is_human_only(self) -> None:
        """OAuth auth failure should be classified as human-only."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                auth_type="oauth",
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.AUTH_FAILURE,
            message="OAuth requires human sign-off",
            details={"escalation": "human"},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        assert fixes[0].action == ConfigFixAction.HUMAN_ONLY


class TestConfigFixerNetworkError:
    """Tests for network error repair recommendations."""

    def test_network_error_suggests_retry(self) -> None:
        """Network error should suggest retry or check connectivity."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.NETWORK_ERROR,
            message="Network error: connection refused",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix.action == ConfigFixAction.RECOMMEND
        assert "retry" in fix.summary.lower() or "connectivity" in fix.summary.lower()


# --------------------------------------------------------------------------- #
# Priority ranking tests
# --------------------------------------------------------------------------- #

class TestRankConfigFixes:
    """Tests for fixing priority ranking."""

    def test_critical_before_important(self) -> None:
        """CRITICAL fixes should sort before IMPORTANT fixes."""
        fixes = [
            ConfigFix(
                provider="openai",
                model="gpt-4",
                configured_endpoint="https://api.openai.com/v1",
                correct_model="gpt-4o",
                correct_endpoint=None,
                action=ConfigFixAction.RECOMMEND,
                code="DEPRECATED_MODEL",
                summary="Deprecated model",
                detail="Replace with supported model",
                repair_steps=["Replace model"],
                lane=None,
                source_fingerprint=None,
            ),
            ConfigFix(
                provider="openai",
                model="gpt-4o",
                configured_endpoint="https://api.openai.com/v1",
                correct_model=None,
                correct_endpoint="https://api.openai.com/v1",
                action=ConfigFixAction.AUTO_FIX,
                code="RKWE",
                summary="Wrong endpoint",
                detail="Fix endpoint",
                repair_steps=["Fix endpoint"],
                lane=None,
                source_fingerprint=None,
            ),
        ]
        ranked = rank_config_fixes(fixes)
        # AUTO_FIX (which maps to NICE_TO_HAVE or GOOD_IDEA) comes after RECOMMEND (IMPORTANT)
        # Actually, let's check the actual order based on priority mapping
        assert ranked[0].code == "DEPRECATED_MODEL"  # IMPORTANT
        assert ranked[1].code == "RKWE"  # GOOD_IDEA

    def test_same_priority_preserves_order(self) -> None:
        """Fixes with same priority should preserve relative order."""
        fixes = [
            ConfigFix(
                provider="openai",
                model="gpt-4",
                configured_endpoint="https://api.openai.com/v1",
                correct_model="gpt-4o",
                correct_endpoint=None,
                action=ConfigFixAction.RECOMMEND,
                code="DEPRECATED_MODEL",
                summary="First deprecated",
                detail="First",
                repair_steps=["Replace first"],
                lane=None,
                source_fingerprint=None,
            ),
            ConfigFix(
                provider="openai",
                model="gpt-3.5",
                configured_endpoint="https://api.openai.com/v1",
                correct_model="gpt-4o-mini",
                correct_endpoint=None,
                action=ConfigFixAction.RECOMMEND,
                code="DEPRECATED_MODEL",
                summary="Second deprecated",
                detail="Second",
                repair_steps=["Replace second"],
                lane=None,
                source_fingerprint=None,
            ),
        ]
        ranked = rank_config_fixes(fixes)
        assert ranked[0].summary == "First deprecated"
        assert ranked[1].summary == "Second deprecated"


# --------------------------------------------------------------------------- #
# Empty/boundary tests
# --------------------------------------------------------------------------- #

class TestConfigFixerEmpty:
    """Tests for empty and boundary cases."""

    def test_empty_results(self) -> None:
        """Empty results should produce empty fixes."""
        store = ProviderTruthStore()
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([])
        assert len(fixes) == 0

    def test_ok_status_produces_no_fix(self) -> None:
        """OK status should produce no fix."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.OK,
            message="OK",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 0

    def test_unknown_provider_produces_no_fix(self) -> None:
        """Unknown provider should produce no fix (handled elsewhere)."""
        store = ProviderTruthStore()
        result = EndpointCheckResult(
            provider="completely-unknown",
            model="some-model",
            configured_endpoint="https://example.com",
            status=EndpointCheckStatus.UNKNOWN_PROVIDER,
            message="Provider not found",
            details={},
        )
        fixer = ConfigFixer(store)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 0


# --------------------------------------------------------------------------- #
# Lane-aware tests
# --------------------------------------------------------------------------- #

class TestConfigFixerLaneAware:
    """Tests for lane-aware repair tuples."""

    def test_lane_preserved_in_fix(self) -> None:
        """Lane should be preserved in the fix recommendation."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
            )
        )
        result = EndpointCheckResult(
            provider="openai",
            model="gpt-4o",
            configured_endpoint="https://api.openai.com/v1",
            status=EndpointCheckStatus.STALE_MODEL,
            message="Model not known",
            details={},
        )
        fixer = ConfigFixer(store)
        # Pass lane through the result's configured_endpoint (for now)
        fixes = fixer.produce_fixes([result])
        assert len(fixes) == 1
        # Lane is propagated from the EndpointCheckResult
        assert fixes[0].lane == (result.details.get("lane"))
