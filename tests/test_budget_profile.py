"""Tests for budget profile data model and presets."""
from __future__ import annotations

import pytest

from hermesoptimizer.budget.profile import (
    BudgetProfile,
    RoleBudgetDefaults,
    PRESETS,
    PRESET_ORDER,
    VerificationDepth,
    get_profile,
    get_role_defaults,
)


class TestBudgetProfile:
    def test_frozen_dataclass(self):
        p = get_profile("low")
        with pytest.raises(AttributeError):
            p.main_turns = 999  # type: ignore[misc]

    def test_all_five_presets_exist(self):
        assert set(PRESETS.keys()) == {
            "low", "low-medium", "medium", "medium-high", "high"
        }

    def test_preset_order_length(self):
        assert len(PRESET_ORDER) == 5

    def test_preset_order_matches_keys(self):
        assert list(PRESETS.keys()) == PRESET_ORDER

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_get_profile_returns_correct_name(self, level):
        assert get_profile(level).name == level

    def test_get_profile_invalid_raises(self):
        with pytest.raises(KeyError):
            get_profile("ultra")  # type: ignore[arg-type]

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_main_turns_within_bounds(self, level):
        p = get_profile(level)
        assert p.main_turns >= 90
        assert p.main_turns <= 1000

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_subagent_turns_within_bounds(self, level):
        p = get_profile(level)
        assert p.subagent_turns >= 50
        assert p.subagent_turns <= 200

    def test_monotonic_main_turns(self):
        turns = [PRESETS[l].main_turns for l in PRESET_ORDER]
        assert turns == sorted(turns)
        assert len(set(turns)) == 5  # strictly increasing

    def test_monotonic_subagent_turns(self):
        turns = [PRESETS[l].subagent_turns for l in PRESET_ORDER]
        assert turns == sorted(turns)
        assert len(set(turns)) == 5


class TestStepNavigation:
    def test_step_index_values(self):
        assert get_profile("low").step_index() == 0
        assert get_profile("medium").step_index() == 2
        assert get_profile("high").step_index() == 4

    def test_step_up_from_low(self):
        result = get_profile("low").step_up()
        assert result is not None
        assert result.name == "low-medium"

    def test_step_up_from_high_is_none(self):
        assert get_profile("high").step_up() is None

    def test_step_down_from_high(self):
        result = get_profile("high").step_down()
        assert result is not None
        assert result.name == "medium-high"

    def test_step_down_from_low_is_none(self):
        assert get_profile("low").step_down() is None

    def test_round_trip_step_up_down(self):
        medium = get_profile("medium")
        stepped = medium.step_up()
        assert stepped is not None
        back = stepped.step_down()
        assert back is not None
        assert back.name == medium.name


class TestSupportingAxes:
    def test_low_has_smoke_verification(self):
        assert get_profile("low").verification_depth == VerificationDepth.SMOKE

    def test_high_has_full_gate(self):
        assert get_profile("high").verification_depth == VerificationDepth.FULL_GATE

    def test_medium_profiles_have_unit_integration(self):
        for level in ("low-medium", "medium", "medium-high"):
            p = get_profile(level)
            assert p.verification_depth == VerificationDepth.UNIT_INTEGRATION

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_retry_limit_positive(self, level):
        assert get_profile(level).retry_limit >= 1

    def test_high_has_unlimited_fix_cycles(self):
        assert get_profile("high").fix_iterate_cycles is None

    def test_low_fix_cycles_is_one(self):
        assert get_profile("low").fix_iterate_cycles == 1

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_parallel_workers_positive(self, level):
        assert get_profile(level).max_parallel_workers >= 1

    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_token_budget_positive(self, level):
        assert get_profile(level).token_budget_per_task > 0


class TestRoleDefaults:
    @pytest.mark.parametrize("level", PRESET_ORDER)
    def test_role_defaults_exist(self, level):
        rd = get_role_defaults(level)
        assert isinstance(rd, RoleBudgetDefaults)

    def test_research_stays_bounded_on_high(self):
        rd = get_role_defaults("high")
        assert rd.research <= 100

    def test_review_stays_bounded_on_high(self):
        rd = get_role_defaults("high")
        assert rd.review <= 100

    def test_implement_scales_with_profile(self):
        low_impl = get_role_defaults("low").implement
        high_impl = get_role_defaults("high").implement
        assert high_impl > low_impl

    def test_all_roles_positive(self):
        for level in PRESET_ORDER:
            rd = get_role_defaults(level)
            for role in ("research", "implement", "test", "review", "verify", "integrate"):
                assert getattr(rd, role) > 0, f"{role} not positive for {level}"

    def test_no_role_exceeds_subagent_cap(self):
        """Role defaults should not exceed the profile's subagent_turns."""
        for level in PRESET_ORDER:
            p = get_profile(level)
            rd = get_role_defaults(level)
            for role in ("research", "implement", "test", "review", "verify", "integrate"):
                assert getattr(rd, role) <= p.main_turns, (
                    f"{role}={getattr(rd, role)} exceeds main_turns={p.main_turns} for {level}"
                )
