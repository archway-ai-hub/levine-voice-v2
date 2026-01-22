"""Integration tests for golden transcript simulations.

These tests run the same simulation scenarios as `make sim` to ensure
intent classification and capture logic work correctly.
"""

import sys
from pathlib import Path

import pytest

# Add scripts to path so we can import simulate_transcripts
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from simulate_transcripts import SCENARIOS, run_scenario


class TestGoldenTranscripts:
    """Test golden transcript scenarios."""

    @pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
    def test_scenario(self, scenario_name: str) -> None:
        """Test each scenario captures correct intent and fields."""
        config = SCENARIOS[scenario_name]
        passed, errors, userdata = run_scenario(scenario_name, config)

        # Check scenario passed
        assert passed, f"Scenario {scenario_name} failed: {errors}"

        # Verify intent was captured
        assert userdata.route_decision.intent is not None, (
            f"Scenario {scenario_name}: intent should not be None"
        )

        # Verify intent matches expected
        assert userdata.route_decision.intent == config.expected_intent, (
            f"Scenario {scenario_name}: expected intent {config.expected_intent.value}, "
            f"got {userdata.route_decision.intent.value}"
        )

        # Verify caller name was captured
        assert userdata.route_decision.caller_name == config.expected_name, (
            f"Scenario {scenario_name}: expected name '{config.expected_name}', "
            f"got '{userdata.route_decision.caller_name}'"
        )

        # Verify phone was captured (normalized to digits only)
        expected_phone = "".join(c for c in config.expected_phone if c.isdigit())
        assert userdata.route_decision.callback_phone == expected_phone, (
            f"Scenario {scenario_name}: expected phone '{expected_phone}', "
            f"got '{userdata.route_decision.callback_phone}'"
        )

        # Verify insurance type if expected
        if config.insurance_type is not None:
            assert userdata.route_decision.insurance_type == config.insurance_type, (
                f"Scenario {scenario_name}: expected insurance_type {config.insurance_type.value}, "
                f"got {userdata.route_decision.insurance_type}"
            )
