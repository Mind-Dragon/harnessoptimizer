"""
Tests for provider-truth rework: explicit regions, transport, and repair candidates.

Covers:
- ProviderTruthRecord with regions, transport, and endpoint_candidates fields
- EndpointCandidate dataclass for repair candidate endpoints
- ProviderTruthStore.get_repair_candidates() method
- Integration with provider endpoint catalog for repair candidates
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.sources.provider_truth import (
    EndpointCandidate,
    ProviderTruthRecord,
    ProviderTruthStore,
    canonical_provider_name,
    dump_provider_truth,
    load_provider_truth,
)


# -------------------------------------------------------------------------- #
# EndpointCandidate tests
# -------------------------------------------------------------------------- #

class TestEndpointCandidate:
    def test_endpoint_candidate_creation(self) -> None:
        cand = EndpointCandidate(
            endpoint="https://api.openai.com/v1",
            api_style="openai-compatible",
            auth_type="bearer",
            region_scope=["us", "global"],
            is_stable=True,
        )
        assert cand.endpoint == "https://api.openai.com/v1"
        assert cand.api_style == "openai-compatible"
        assert cand.auth_type == "bearer"
        assert cand.region_scope == ["us", "global"]
        assert cand.is_stable is True

    def test_endpoint_candidate_equality(self) -> None:
        cand1 = EndpointCandidate(
            endpoint="https://api.openai.com/v1",
            api_style="openai-compatible",
            auth_type="bearer",
            region_scope=["us"],
            is_stable=True,
        )
        cand2 = EndpointCandidate(
            endpoint="https://api.openai.com/v1",
            api_style="openai-compatible",
            auth_type="bearer",
            region_scope=["us"],
            is_stable=True,
        )
        assert cand1 == cand2

    def test_endpoint_candidate_repr(self) -> None:
        cand = EndpointCandidate(
            endpoint="https://api.openai.com/v1",
            api_style="openai-compatible",
            auth_type="bearer",
            region_scope=["us"],
            is_stable=True,
        )
        r = repr(cand)
        assert "EndpointCandidate" in r
        assert "api.openai.com" in r


# -------------------------------------------------------------------------- #
# ProviderTruthRecord with new fields
# -------------------------------------------------------------------------- #

class TestProviderTruthRecordNewFields:
    def test_record_with_regions_and_transport(self) -> None:
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            regions=["us", "eu", "global"],
            transport="https",
            known_models=["gpt-4o"],
        )
        assert rec.regions == ["us", "eu", "global"]
        assert rec.transport == "https"

    def test_record_with_endpoint_candidates(self) -> None:
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=True,
            ),
        ]
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            endpoint_candidates=candidates,
        )
        assert len(rec.endpoint_candidates) == 2
        assert rec.endpoint_candidates[0].endpoint == "https://api.openai.com/v1"
        assert rec.endpoint_candidates[1].region_scope == ["eu"]

    def test_record_defaults_for_new_fields(self) -> None:
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
        )
        assert rec.regions == []
        assert rec.transport == ""
        assert rec.endpoint_candidates == []

    def test_record_is_available_in_region(self) -> None:
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            regions=["us", "eu"],
        )
        assert rec.is_available_in_region("us") is True
        assert rec.is_available_in_region("eu") is True
        assert rec.is_available_in_region("cn") is False

    def test_record_is_transport_secure(self) -> None:
        rec_https = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            transport="https",
        )
        rec_http = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="http://internal.example.com/v1",
            transport="http",
        )
        assert rec_https.is_transport_secure() is True
        assert rec_http.is_transport_secure() is False

    def test_record_get_stable_candidates(self) -> None:
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=False,
            ),
            EndpointCandidate(
                endpoint="https://backup.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us"],
                is_stable=True,
            ),
        ]
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            endpoint_candidates=candidates,
        )
        stable = rec.get_stable_candidates()
        assert len(stable) == 2
        assert all(c.is_stable for c in stable)

    def test_record_get_candidates_for_region(self) -> None:
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=True,
            ),
        ]
        rec = ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            endpoint_candidates=candidates,
        )
        eu_candidates = rec.get_candidates_for_region("eu")
        assert len(eu_candidates) == 1
        assert eu_candidates[0].endpoint == "https://api.openai.eu/v1"


# -------------------------------------------------------------------------- #
# ProviderTruthStore.get_repair_candidates tests
# -------------------------------------------------------------------------- #

class TestProviderTruthStoreRepairCandidates:
    def test_get_repair_candidates_empty_store(self) -> None:
        store = ProviderTruthStore()
        candidates = store.get_repair_candidates("openai")
        assert candidates == []

    def test_get_repair_candidates_unknown_provider(self) -> None:
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
            )
        )
        candidates = store.get_repair_candidates("unknown")
        assert candidates == []

    def test_get_repair_candidates_returns_endpoint_candidates(self) -> None:
        store = ProviderTruthStore()
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=True,
            ),
        ]
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                endpoint_candidates=candidates,
            )
        )
        repair_candidates = store.get_repair_candidates("openai")
        assert len(repair_candidates) == 2
        assert repair_candidates[0].endpoint == "https://api.openai.com/v1"
        assert repair_candidates[1].endpoint == "https://api.openai.eu/v1"

    def test_get_repair_candidates_filters_unstable(self) -> None:
        store = ProviderTruthStore()
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://beta.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us"],
                is_stable=False,
            ),
        ]
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                endpoint_candidates=candidates,
            )
        )
        repair_candidates = store.get_repair_candidates("openai", stable_only=True)
        assert len(repair_candidates) == 1
        assert repair_candidates[0].endpoint == "https://api.openai.com/v1"

    def test_get_repair_candidates_for_region(self) -> None:
        store = ProviderTruthStore()
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=True,
            ),
        ]
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                endpoint_candidates=candidates,
            )
        )
        eu_candidates = store.get_repair_candidates("openai", region="eu")
        assert len(eu_candidates) == 1
        assert eu_candidates[0].endpoint == "https://api.openai.eu/v1"


# -------------------------------------------------------------------------- #
# Round-trip with new fields
# -------------------------------------------------------------------------- #

class TestProviderTruthReworkRoundtrip:
    def test_roundtrip_with_regions_and_transport(self, tmp_path: Path) -> None:
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                regions=["us", "eu", "global"],
                transport="https",
                known_models=["gpt-4o"],
                auth_type="bearer",
            )
        )
        path = tmp_path / "truth.yaml"
        dump_provider_truth(store, path)
        loaded = load_provider_truth(path)
        rec = loaded.get("openai")
        assert rec is not None
        assert rec.regions == ["us", "eu", "global"]
        assert rec.transport == "https"
        assert rec.auth_type == "bearer"

    def test_roundtrip_with_endpoint_candidates(self, tmp_path: Path) -> None:
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us", "global"],
                is_stable=True,
            ),
            EndpointCandidate(
                endpoint="https://api.openai.eu/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["eu"],
                is_stable=True,
            ),
        ]
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                endpoint_candidates=candidates,
            )
        )
        path = tmp_path / "truth.yaml"
        dump_provider_truth(store, path)
        loaded = load_provider_truth(path)
        rec = loaded.get("openai")
        assert rec is not None
        assert len(rec.endpoint_candidates) == 2
        assert rec.endpoint_candidates[0].endpoint == "https://api.openai.com/v1"
        assert rec.endpoint_candidates[1].region_scope == ["eu"]

    def test_roundtrip_endpoint_candidates_have_required_fields(self, tmp_path: Path) -> None:
        """Ensure endpoint_candidates serialize with all required fields."""
        candidates = [
            EndpointCandidate(
                endpoint="https://api.openai.com/v1",
                api_style="openai-compatible",
                auth_type="bearer",
                region_scope=["us"],
                is_stable=True,
            ),
        ]
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                endpoint_candidates=candidates,
            )
        )
        path = tmp_path / "truth.yaml"
        dump_provider_truth(store, path)
        text = path.read_text(encoding="utf-8")
        assert "endpoint_candidates" in text
        assert "https://api.openai.com/v1" in text
        assert "api_style" in text
        assert "is_stable" in text


# -------------------------------------------------------------------------- #
# Canonical provider name resolution still works
# -------------------------------------------------------------------------- #

class TestProviderTruthReworkCanonicalResolution:
    def test_alias_lookup_still_works_with_new_fields(self) -> None:
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="bailian",
                canonical_endpoint="https://dashscope.aliyuncs.com/api/v1",
                regions=["cn", "global"],
                transport="https",
                known_models=["qwen3.6-plus"],
                endpoint_candidates=[
                    EndpointCandidate(
                        endpoint="https://dashscope.aliyuncs.com/api/v1",
                        api_style="openai-compatible",
                        auth_type="bearer",
                        region_scope=["cn", "global"],
                        is_stable=True,
                    ),
                ],
            )
        )
        # Alias should resolve to canonical
        assert store.get("qwen") is not None
        rec = store.get("qwen")
        assert rec is not None
        assert rec.canonical_endpoint == "https://dashscope.aliyuncs.com/api/v1"
        assert rec.regions == ["cn", "global"]
        assert len(rec.endpoint_candidates) == 1

    def test_dup_canonical_family_still_rejected_with_new_fields(self) -> None:
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="kimi",
                canonical_endpoint="https://api.moonshot.cn/v1",
                regions=["cn"],
                transport="https",
            )
        )
        with pytest.raises(ValueError):
            store.add(
                ProviderTruthRecord(
                    provider="kimi-for-coding",
                    canonical_endpoint="https://api.moonshot.cn/v1",
                    regions=["cn"],
                    transport="https",
                )
            )
