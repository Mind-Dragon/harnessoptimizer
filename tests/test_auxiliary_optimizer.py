from __future__ import annotations

from pathlib import Path

import yaml

from hermesoptimizer.auxiliary_optimizer import (
    AUXILIARY_ROLES,
    AuxiliaryDrift,
    AuxiliaryEntry,
    auxiliary_status,
    build_role_requirements,
    check_auxiliary_drift,
    evaluate_auxiliary,
    write_drift_report,
    resolve_primary_context,
)
from hermesoptimizer.sources.model_catalog import ModelCatalogEntry, ProviderModelCatalog
from hermesoptimizer.sources.provider_truth import ProviderTruthRecord, ProviderTruthStore

ROLE_COUNT = 9



def _entry(
    *,
    provider: str,
    name: str,
    capabilities: list[str],
    context_window: int,
    display_name: str | None = None,
) -> ModelCatalogEntry:
    return ModelCatalogEntry(
        name=name,
        display_name=display_name or name,
        provider=provider,
        capabilities=capabilities,
        context_window=context_window,
    )



def _catalog() -> ProviderModelCatalog:
    catalog = ProviderModelCatalog()
    for entry in [
        _entry(provider="openai", name="primary-256k", capabilities=["text"], context_window=256_000),
        _entry(provider="openai", name="primary-128k", capabilities=["text"], context_window=128_000),
        _entry(
            provider="aux",
            name="compression-fast-256k",
            capabilities=["text"],
            context_window=256_000,
            display_name="Compression Fast 256k",
        ),
        _entry(provider="aux", name="vision-64k", capabilities=["text", "vision"], context_window=64_000),
        _entry(
            provider="aux",
            name="web-fast-128k",
            capabilities=["text"],
            context_window=128_000,
            display_name="Web Fast 128k",
        ),
        _entry(
            provider="aux",
            name="session-mini-32k",
            capabilities=["text"],
            context_window=32_000,
            display_name="Session Mini 32k",
        ),
        _entry(provider="aux", name="skills-32k", capabilities=["text"], context_window=32_000),
        _entry(
            provider="aux",
            name="approval-reasoner-128k",
            capabilities=["text", "reasoning"],
            context_window=128_000,
        ),
        _entry(
            provider="aux",
            name="mcp-fast-32k",
            capabilities=["text"],
            context_window=32_000,
            display_name="MCP Fast 32k",
        ),
        _entry(
            provider="aux",
            name="flush-mini-32k",
            capabilities=["text"],
            context_window=32_000,
            display_name="Flush Mini 32k",
        ),
        _entry(
            provider="aux",
            name="title-mini-8k",
            capabilities=["text"],
            context_window=8_000,
            display_name="Title Mini 8k",
        ),
        _entry(provider="aux", name="bad-short-16k", capabilities=["text"], context_window=16_000),
        _entry(provider="aux", name="reasoner-32k", capabilities=["text", "reasoning"], context_window=32_000),
    ]:
        catalog.add(entry)
    return catalog



def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path



def _base_config() -> dict:
    return {
        "model": {"provider": "openai", "default": "primary-256k"},
        "auxiliary": {},
    }



def _truth_store(*records: ProviderTruthRecord) -> ProviderTruthStore:
    store = ProviderTruthStore()
    for record in records:
        store.add(record)
    return store



def test_auxiliary_roles_has_expected_9_roles() -> None:
    assert len(AUXILIARY_ROLES) == ROLE_COUNT
    assert set(AUXILIARY_ROLES) == {
        "compression",
        "vision",
        "web_extract",
        "session_search",
        "skills_hub",
        "approval",
        "mcp",
        "flush_memories",
        "title_generation",
    }



def test_primary_context_resolution_from_catalog(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())

    assert resolve_primary_context("primary-256k", "openai") == 256_000



def test_primary_context_fallback_when_model_unknown(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())

    assert resolve_primary_context("missing-model", "openai") == 128_000



def test_compression_min_context_scales_with_primary_model() -> None:
    requirements = build_role_requirements(256_000)

    assert requirements["compression"].min_context_window == 256_000



def test_user_override_preserved_when_valid(tmp_path: Path, monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())
    config = _base_config()
    config["auxiliary"]["vision"] = {"provider": "aux", "model": "vision-64k"}
    path = _write_config(tmp_path, config)

    entries = {entry.role: entry for entry in evaluate_auxiliary(path)}

    assert entries["vision"].provider == "aux"
    assert entries["vision"].model == "vision-64k"
    assert entries["vision"].reason == "user override preserved"



def test_user_override_flagged_when_invalid(tmp_path: Path, monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())
    config = _base_config()
    config["auxiliary"]["vision"] = {"provider": "aux", "model": "bad-short-16k"}
    path = _write_config(tmp_path, config)

    status = auxiliary_status(path)
    entries = {entry.role: entry for entry in evaluate_auxiliary(path)}

    assert status["vision"]["constraint_pass"] is False
    assert "fails constraints" in status["vision"]["finding"]
    assert entries["vision"].model == "vision-64k"
    assert entries["vision"].reason == "replacement recommended; explicit auxiliary model failed constraints"



def test_auto_selected_when_no_user_setting(tmp_path: Path, monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())
    path = _write_config(tmp_path, _base_config())

    entries = {entry.role: entry for entry in evaluate_auxiliary(path)}

    assert entries["title_generation"].model == "title-mini-8k"
    assert entries["title_generation"].reason.startswith("[AUXILIARY_AUTO_SELECTED]")



def test_evaluate_auxiliary_returns_entries_for_all_9_roles(tmp_path: Path, monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())
    path = _write_config(tmp_path, _base_config())

    entries = evaluate_auxiliary(path)

    assert len(entries) == ROLE_COUNT
    assert {entry.role for entry in entries} == set(AUXILIARY_ROLES)



def test_auxiliary_status_shows_constraint_pass_fail(tmp_path: Path, monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "MODEL_CATALOG", _catalog())
    config = _base_config()
    config["auxiliary"]["vision"] = {"provider": "aux", "model": "vision-64k"}
    config["auxiliary"]["approval"] = {"provider": "aux", "model": "skills-32k"}
    path = _write_config(tmp_path, config)

    status = auxiliary_status(path)

    assert status["vision"]["constraint_pass"] is True
    assert status["vision"]["finding"] == "user override preserved"
    assert status["approval"]["constraint_pass"] is False
    assert "fails constraints" in status["approval"]["finding"]



def test_stale_model_produces_drift_finding(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    store = _truth_store(
        ProviderTruthRecord(
            provider="aux",
            canonical_endpoint="https://api.aux.example/v1",
            known_models=["vision-64k"],
            stale_aliases={"vision-32k": "vision-64k"},
        )
    )
    monkeypatch.setattr(auxiliary_optimizer, "ProviderTruthStore", lambda: store)

    drifts = check_auxiliary_drift(
        [
            AuxiliaryEntry(
                role="vision",
                provider="aux",
                model="vision-32k",
                reason="configured auxiliary entry",
                evaluator_score=0,
                evaluator_rationale=[],
            )
        ]
    )

    assert len(drifts) == 1
    assert drifts[0].severity == "warning"
    assert "stale alias" in drifts[0].issue



def test_live_model_passes_clean(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    store = _truth_store(
        ProviderTruthRecord(
            provider="aux",
            canonical_endpoint="https://api.aux.example/v1",
            known_models=["vision-64k"],
        )
    )
    monkeypatch.setattr(auxiliary_optimizer, "ProviderTruthStore", lambda: store)

    drifts = check_auxiliary_drift(
        [
            AuxiliaryEntry(
                role="vision",
                provider="aux",
                model="vision-64k",
                reason="configured auxiliary entry",
                evaluator_score=0,
                evaluator_rationale=[],
            )
        ]
    )

    assert drifts == []



def test_dead_provider_produces_drift_finding(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    store = _truth_store(
        ProviderTruthRecord(
            provider="aux",
            canonical_endpoint="",
            known_models=["vision-64k"],
        )
    )
    monkeypatch.setattr(auxiliary_optimizer, "ProviderTruthStore", lambda: store)

    drifts = check_auxiliary_drift(
        [
            AuxiliaryEntry(
                role="vision",
                provider="aux",
                model="vision-64k",
                reason="configured auxiliary entry",
                evaluator_score=0,
                evaluator_rationale=[],
            )
        ]
    )

    assert len(drifts) == 1
    assert drifts[0].severity == "error"
    assert "unavailable" in drifts[0].issue



def test_drift_json_written_correctly(tmp_path: Path) -> None:
    path = tmp_path / "auxiliary-drift.json"
    drifts = [
        AuxiliaryDrift(
            role="vision",
            provider="aux",
            model="vision-32k",
            issue="model 'vision-32k' is a stale alias for 'vision-64k'",
            severity="warning",
        )
    ]

    write_drift_report(drifts, path)

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload == [
        {
            "role": "vision",
            "provider": "aux",
            "model": "vision-32k",
            "issue": "model 'vision-32k' is a stale alias for 'vision-64k'",
            "severity": "warning",
        }
    ]



def test_empty_auxiliary_no_drift(monkeypatch) -> None:
    import hermesoptimizer.auxiliary_optimizer as auxiliary_optimizer

    monkeypatch.setattr(auxiliary_optimizer, "ProviderTruthStore", ProviderTruthStore)

    assert check_auxiliary_drift([]) == []
