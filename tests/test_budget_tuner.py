from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from hermesoptimizer.budget.profile import PRESETS, ProfileLevel, get_profile
from hermesoptimizer.budget.recommender import BudgetRecommendation
from hermesoptimizer.budget.tuner import apply_recommendation, set_profile, write_budget_section


class TestWriteBudgetSection:
    @pytest.mark.parametrize("level", list(PRESETS.keys()))
    def test_returns_correct_dict_for_each_profile_level(self, level: ProfileLevel):
        """write_budget_section returns the expected dict for every profile level."""
        profile = get_profile(level)
        result = write_budget_section(level)

        assert result["profile"] == profile.name
        assert result["main_turns"] == profile.main_turns
        assert result["subagent_turns"] == profile.subagent_turns
        assert result["retry_limit"] == profile.retry_limit
        assert result["fix_iterate_cycles"] == profile.fix_iterate_cycles
        assert result["max_parallel_workers"] == profile.max_parallel_workers
        assert result["token_budget_per_task"] == profile.token_budget_per_task
        assert result["verification_depth"] == profile.verification_depth.value

    def test_with_role_overrides(self):
        """role_overrides are included in the output dict."""
        overrides = {"implement": 300, "test": 150}
        result = write_budget_section("medium", role_overrides=overrides)

        assert "role_overrides" in result
        assert result["role_overrides"] == overrides

    def test_without_role_overrides_no_role_overrides_key(self):
        """When no role_overrides are given, the key is absent."""
        result = write_budget_section("low")
        assert "role_overrides" not in result


class TestSetProfile:
    def test_dry_run_returns_changes_without_modifying_file(self, tmp_path: Path):
        """dry_run=True returns changes dict but does not write the file."""
        config_file = tmp_path / "config.yaml"

        result = set_profile(config_file, "medium", dry_run=True)

        assert result["dry_run"] is True
        assert result["path"] == str(config_file)
        assert "profile" in result["changes"]
        assert not config_file.exists()

    def test_dry_run_false_writes_to_file(self, tmp_path: Path):
        """dry_run=False writes the updated YAML to disk."""
        config_file = tmp_path / "config.yaml"

        result = set_profile(config_file, "medium", dry_run=False)

        assert result["dry_run"] is False
        assert config_file.exists()
        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["turn_budget"]["profile"] == "medium"

    def test_set_profile_with_no_role_overrides(self, tmp_path: Path):
        """set_profile writes the correct profile fields to the config."""
        config_file = tmp_path / "config.yaml"

        set_profile(config_file, "low-medium", dry_run=False)

        with config_file.open() as f:
            config = yaml.safe_load(f)
        tb = config["turn_budget"]
        assert tb["profile"] == "low-medium"
        assert tb["main_turns"] == PRESETS["low-medium"].main_turns
        assert "role_overrides" not in tb

    def test_set_profile_with_role_overrides(self, tmp_path: Path):
        """role_overrides are written under turn_budget:role_overrides:"""
        config_file = tmp_path / "config.yaml"
        overrides = {"implement": 300, "review": 150}

        set_profile(config_file, "high", role_overrides=overrides, dry_run=False)

        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["turn_budget"]["role_overrides"] == overrides

    def test_nonexistent_config_file_created(self, tmp_path: Path):
        """If the config file doesn't exist, it is created with just turn_budget."""
        config_file = tmp_path / "new_config.yaml"
        assert not config_file.exists()

        set_profile(config_file, "medium", dry_run=False)

        assert config_file.exists()
        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert "turn_budget" in config

    def test_existing_config_other_sections_preserved(self, tmp_path: Path):
        """Existing top-level keys outside turn_budget are preserved."""
        config_file = tmp_path / "config.yaml"
        existing = {"other_section": {"foo": 123}, "another": "value"}
        with config_file.open("w") as f:
            yaml.safe_dump(existing, f)

        set_profile(config_file, "low", dry_run=False)

        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["other_section"] == {"foo": 123}
        assert config["another"] == "value"
        assert config["turn_budget"]["profile"] == "low"


class TestApplyRecommendation:
    def test_dry_run_returns_changes_without_modifying_file(self, tmp_path: Path):
        """dry_run=True returns changes dict but does not write the file."""
        config_file = tmp_path / "config.yaml"

        rec = BudgetRecommendation(
            current_profile="low",
            recommended_profile="medium",
            confidence=0.85,
            reasoning="Test",
            main_turns=500,
            subagent_turns=100,
        )

        result = apply_recommendation(config_file, rec, dry_run=True)

        assert result["dry_run"] is True
        assert not config_file.exists()

    def test_dry_run_false_writes_to_file(self, tmp_path: Path):
        """dry_run=False writes the recommendation to disk."""
        config_file = tmp_path / "config.yaml"

        rec = BudgetRecommendation(
            current_profile="low",
            recommended_profile="medium-high",
            confidence=0.9,
            reasoning="High utilization",
            main_turns=750,
            subagent_turns=150,
        )

        result = apply_recommendation(config_file, rec, dry_run=False)

        assert result["dry_run"] is False
        assert config_file.exists()
        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["turn_budget"]["profile"] == "medium-high"

    def test_recommendation_with_role_overrides(self, tmp_path: Path):
        """role_overrides from recommendation are written to config."""
        config_file = tmp_path / "config.yaml"
        overrides = {"implement": 300}

        rec = BudgetRecommendation(
            current_profile="medium",
            recommended_profile="medium",
            confidence=0.7,
            reasoning="Minor adjustment",
            main_turns=500,
            subagent_turns=100,
            role_overrides=overrides,
        )

        apply_recommendation(config_file, rec, dry_run=False)

        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["turn_budget"]["role_overrides"] == overrides

    def test_nonexistent_config_file_created(self, tmp_path: Path):
        """apply_recommendation creates the file if it doesn't exist."""
        config_file = tmp_path / "new.yaml"
        assert not config_file.exists()

        rec = BudgetRecommendation(
            current_profile="low",
            recommended_profile="high",
            confidence=0.5,
            reasoning="Test",
            main_turns=1000,
            subagent_turns=200,
        )
        apply_recommendation(config_file, rec, dry_run=False)

        assert config_file.exists()

    def test_existing_config_other_sections_preserved(self, tmp_path: Path):
        """apply_recommendation preserves existing top-level sections."""
        config_file = tmp_path / "config.yaml"
        existing = {"top": {"key": "val"}}
        with config_file.open("w") as f:
            yaml.safe_dump(existing, f)

        rec = BudgetRecommendation(
            current_profile="low",
            recommended_profile="medium",
            confidence=0.8,
            reasoning="Step up",
            main_turns=500,
            subagent_turns=100,
        )
        apply_recommendation(config_file, rec, dry_run=False)

        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config["top"] == {"key": "val"}
        assert config["turn_budget"]["profile"] == "medium"
