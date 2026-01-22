#!/usr/bin/env python3
"""
Golden transcript simulation for testing intent capture without LiveKit.

This script tests the intent classification and capture logic using predefined
transcript scenarios. It validates that:
1. Intent is correctly classified from the first meaningful utterance
2. Intent persists across subsequent utterances (intent persistence)
3. Caller name and phone are captured correctly
4. The route_decision object is populated as expected

Run with: uv run python scripts/simulate_transcripts.py
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import maybe_record_intent
from models import AizelleeUserData, InsuranceType, IntentCategory

# Suppress debug logging AFTER importing agent module
# The agent module calls logging.basicConfig at import time
logging.getLogger("aizellee").setLevel(logging.CRITICAL)


@dataclass
class ScenarioConfig:
    """Configuration for a single test scenario."""

    transcripts: list[str]
    expected_intent: IntentCategory
    expected_name: str
    expected_phone: str
    insurance_type: Optional[InsuranceType] = None


# Golden transcript scenarios
# Each scenario simulates a realistic call flow with intent + name + phone collection
SCENARIOS: dict[str, ScenarioConfig] = {
    "new_quote": ScenarioConfig(
        transcripts=["I need a quote", "John Smith", "5551234567", "personal"],
        expected_intent=IntentCategory.NEW_QUOTE,
        expected_name="John Smith",
        expected_phone="5551234567",
        insurance_type=InsuranceType.PERSONAL,
    ),
    "payment_or_id_dec": ScenarioConfig(
        transcripts=["I need to make a payment", "Jane Doe", "5559876543", "business"],
        expected_intent=IntentCategory.PAYMENT_OR_ID_DEC,
        expected_name="Jane Doe",
        expected_phone="5559876543",
        insurance_type=InsuranceType.BUSINESS,
    ),
    "claims": ScenarioConfig(
        transcripts=["I need to file a claim", "Bob Wilson", "5555551234", "personal"],
        expected_intent=IntentCategory.CLAIMS,
        expected_name="Bob Wilson",
        expected_phone="5555551234",
        insurance_type=InsuranceType.PERSONAL,
    ),
    "cancellation": ScenarioConfig(
        transcripts=["I want to cancel my policy", "Alice Brown", "5552223333", "business"],
        expected_intent=IntentCategory.CANCELLATION,
        expected_name="Alice Brown",
        expected_phone="5552223333",
        insurance_type=InsuranceType.BUSINESS,
    ),
    "certificates": ScenarioConfig(
        transcripts=[
            "I need a certificate of insurance",
            "Charlie Davis",
            "5554445555",
            "personal",
        ],
        expected_intent=IntentCategory.CERTIFICATES,
        expected_name="Charlie Davis",
        expected_phone="5554445555",
        insurance_type=InsuranceType.PERSONAL,
    ),
    "make_change": ScenarioConfig(
        transcripts=[
            "I need to add a vehicle to my policy",
            "Diana Miller",
            "5556667777",
            "business",
        ],
        expected_intent=IntentCategory.MAKE_CHANGE,
        expected_name="Diana Miller",
        expected_phone="5556667777",
        insurance_type=InsuranceType.BUSINESS,
    ),
    "coverage_questions": ScenarioConfig(
        transcripts=["What does my policy cover", "Eve Johnson", "5558889999", "personal"],
        expected_intent=IntentCategory.COVERAGE_QUESTIONS,
        expected_name="Eve Johnson",
        expected_phone="5558889999",
        insurance_type=InsuranceType.PERSONAL,
    ),
    "hours_location": ScenarioConfig(
        transcripts=["What are your hours", "Test User", "5550001111"],
        expected_intent=IntentCategory.HOURS_LOCATION,
        expected_name="Test User",
        expected_phone="5550001111",
    ),
}


def simulate_name_capture(userdata: AizelleeUserData, name: str) -> None:
    """
    Simulate capturing caller name.

    In the real agent, this is done via the capture_caller_name function_tool.
    Here we directly set it on route_decision.
    """
    userdata.route_decision.caller_name = name


def simulate_phone_capture(userdata: AizelleeUserData, phone: str) -> None:
    """
    Simulate capturing callback phone.

    In the real agent, this is done via the capture_callback_phone function_tool.
    Here we directly set it on route_decision.
    """
    # Normalize phone to digits only (simulating normalize_phone_number)
    digits_only = "".join(c for c in phone if c.isdigit())
    userdata.route_decision.callback_phone = digits_only


def simulate_insurance_type_capture(
    userdata: AizelleeUserData, insurance_type: InsuranceType
) -> None:
    """
    Simulate capturing insurance type.

    In the real agent, this is done via the capture_insurance_type function_tool.
    """
    userdata.route_decision.insurance_type = insurance_type


def run_scenario(name: str, config: ScenarioConfig) -> tuple[bool, list[str], AizelleeUserData]:
    """
    Run a single scenario and return (pass/fail, list of failure reasons, userdata).

    Args:
        name: Scenario name for logging
        config: Scenario configuration

    Returns:
        Tuple of (passed: bool, failures: list[str], userdata: AizelleeUserData)
    """
    failures: list[str] = []
    userdata = AizelleeUserData()

    # Process transcripts in order
    for i, transcript in enumerate(config.transcripts):
        # First transcript should be the intent statement
        if i == 0:
            maybe_record_intent(userdata, transcript)

            # After first meaningful utterance, intent should be set
            if userdata.route_decision.intent is None:
                failures.append(f"Intent is None after first utterance: '{transcript}'")
            elif userdata.route_decision.intent != config.expected_intent:
                failures.append(
                    f"Intent mismatch: expected {config.expected_intent.value}, "
                    f"got {userdata.route_decision.intent.value}"
                )

            # intent_raw_text should be set
            if not userdata.route_decision.intent_raw_text:
                failures.append("intent_raw_text is empty after intent capture")
            elif userdata.route_decision.intent_raw_text != transcript:
                failures.append(
                    f"intent_raw_text mismatch: expected '{transcript}', "
                    f"got '{userdata.route_decision.intent_raw_text}'"
                )

        # Second transcript is typically the name
        elif i == 1:
            simulate_name_capture(userdata, transcript)

            # Verify intent persistence - process transcript through maybe_record_intent
            # to ensure intent doesn't change when name is spoken
            maybe_record_intent(userdata, transcript)

            if userdata.route_decision.intent != config.expected_intent:
                failures.append(
                    f"Intent changed after name capture: "
                    f"expected {config.expected_intent.value}, "
                    f"got {userdata.route_decision.intent.value if userdata.route_decision.intent else 'None'}"
                )

        # Third transcript is typically the phone
        elif i == 2:
            simulate_phone_capture(userdata, transcript)

            # Verify intent persistence
            maybe_record_intent(userdata, transcript)

            if userdata.route_decision.intent != config.expected_intent:
                failures.append(
                    f"Intent changed after phone capture: "
                    f"expected {config.expected_intent.value}, "
                    f"got {userdata.route_decision.intent.value if userdata.route_decision.intent else 'None'}"
                )

        # Fourth transcript might be insurance type
        elif i == 3 and config.insurance_type:
            simulate_insurance_type_capture(userdata, config.insurance_type)

    # Final validations
    if userdata.route_decision.caller_name != config.expected_name:
        failures.append(
            f"Name mismatch: expected '{config.expected_name}', "
            f"got '{userdata.route_decision.caller_name}'"
        )

    expected_phone = "".join(c for c in config.expected_phone if c.isdigit())
    if userdata.route_decision.callback_phone != expected_phone:
        failures.append(
            f"Phone mismatch: expected '{expected_phone}', "
            f"got '{userdata.route_decision.callback_phone}'"
        )

    if config.insurance_type:
        if userdata.route_decision.insurance_type != config.insurance_type:
            failures.append(
                f"Insurance type mismatch: expected {config.insurance_type.value}, "
                f"got {userdata.route_decision.insurance_type.value if userdata.route_decision.insurance_type else 'None'}"
            )

    passed = len(failures) == 0
    return passed, failures, userdata


def print_route_decision(userdata: AizelleeUserData) -> None:
    """Print the route_decision state in a readable format."""
    rd = userdata.route_decision
    intent_str = rd.intent.value if rd.intent else "None"
    insurance_str = rd.insurance_type.value if rd.insurance_type else "None"

    print("    ROUTE_DECISION:")
    print(f"      intent={intent_str}")
    print(f'      intent_raw_text="{rd.intent_raw_text}"')
    print(f'      caller_name="{rd.caller_name}"')
    print(f'      callback_phone="{rd.callback_phone}"')
    print(f"      insurance_type={insurance_str}")


def main() -> int:
    """
    Run all scenarios and print summary.

    Returns:
        0 if all scenarios pass, 1 otherwise
    """
    print("=" * 60)
    print("Golden Transcript Simulation")
    print("Testing intent capture without LiveKit")
    print("=" * 60)
    print()

    results: dict[str, bool] = {}
    all_userdata: dict[str, AizelleeUserData] = {}

    for scenario_name, config in SCENARIOS.items():
        passed, failures, userdata = run_scenario(scenario_name, config)
        results[scenario_name] = passed
        all_userdata[scenario_name] = userdata

        status = "PASS" if passed else "FAIL"
        status_color = "\033[92m" if passed else "\033[91m"
        reset_color = "\033[0m"

        print(f"{status_color}{scenario_name}: {status}{reset_color}")
        print_route_decision(userdata)

        if failures:
            print("    FAILURES:")
            for failure in failures:
                print(f"      - {failure}")
        print()

    # Print summary
    print("=" * 60)
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    if passed_count == total_count:
        print(f"\033[92mSummary: {passed_count}/{total_count} scenarios passed\033[0m")
    else:
        print(f"\033[91mSummary: {passed_count}/{total_count} scenarios passed\033[0m")
        print("\nFailed scenarios:")
        for name, passed in results.items():
            if not passed:
                print(f"  - {name}")

    print("=" * 60)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
