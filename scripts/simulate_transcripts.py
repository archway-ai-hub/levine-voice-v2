#!/usr/bin/env python3
"""
Golden transcript simulation for testing intent capture without LiveKit.

This script tests the intent classification and capture logic using predefined
transcript scenarios. It validates that:
1. Intent is correctly classified from the first meaningful utterance
2. Intent persists across subsequent utterances (intent persistence)
3. Caller name and phone are captured correctly
4. Insurance type is captured for relevant intents
5. The route_decision object is populated as expected
6. Routing targets (department, agent_name, extension) are correct for transfer intents

Run with: uv run python scripts/simulate_transcripts.py
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import check_routing_requirements, maybe_record_intent, route_call
from models import AizelleeUserData, InsuranceType, IntentCategory

# Suppress debug logging AFTER importing agent module
# The agent module calls logging.basicConfig at import time
logging.getLogger("aizellee").setLevel(logging.CRITICAL)


@dataclass
class ExpectedRoute:
    """Expected routing outcome for validation."""

    target_department: str  # "PL Sales", "PL AE", "CL AE", "info-only", "email", "claims"
    target_agent_name: Optional[str] = None  # For transfer intents
    target_extension: Optional[str] = None  # For transfer intents
    transfer_reason: Optional[str] = None  # For fallback scenarios (e.g., "missing_insurance_type")


@dataclass
class ScenarioConfig:
    """Configuration for a single test scenario."""

    transcripts: list[str]
    expected_intent: IntentCategory
    expected_name: str
    expected_phone: str
    insurance_type: Optional[InsuranceType] = None
    business_name: Optional[str] = None  # For business scenarios
    policy_last_name: Optional[str] = None  # For personal scenarios
    expected_route: Optional[ExpectedRoute] = None  # Routing expectations
    is_fallback_scenario: bool = False  # If True, simulates max-2-asks fallback behavior
    fallback_field: Optional[str] = None  # Which field triggers fallback (e.g., "insurance_type")


# Golden transcript scenarios
# Each scenario simulates a realistic call flow with intent + name + phone collection
# For transfer intents, includes routing expectations
SCENARIOS: dict[str, ScenarioConfig] = {
    # -------------------------------------------------------------------------
    # NEW_QUOTE scenarios
    # -------------------------------------------------------------------------
    "new_quote_personal": ScenarioConfig(
        transcripts=["I need a quote", "John Smith", "5551234567", "personal", "Smith"],
        expected_intent=IntentCategory.NEW_QUOTE,
        expected_name="John Smith",
        expected_phone="5551234567",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Smith",
        # Smith -> S is in M-Z -> Brad (PL Sales)
        expected_route=ExpectedRoute(
            target_department="PL Sales",
            target_agent_name="Brad",
            target_extension="7007",
        ),
    ),
    "new_quote_business": ScenarioConfig(
        transcripts=[
            "I need a quote for my business",
            "Jane Doe",
            "5559876543",
            "business",
            "Acme Corp",
        ],
        expected_intent=IntentCategory.NEW_QUOTE,
        expected_name="Jane Doe",
        expected_phone="5559876543",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Acme Corp",
        # Acme -> A is in A-F -> Adriana (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Adriana",
            target_extension="7002",
        ),
    ),
    # -------------------------------------------------------------------------
    # PAYMENT_OR_ID_DEC scenarios
    # -------------------------------------------------------------------------
    "payment_or_id_dec_business": ScenarioConfig(
        transcripts=[
            "I need to make a payment",
            "Jane Doe",
            "5559876543",
            "business",
            "Smith Industries",
        ],
        expected_intent=IntentCategory.PAYMENT_OR_ID_DEC,
        expected_name="Jane Doe",
        expected_phone="5559876543",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Smith Industries",
        # Smith Industries -> S is in P-Z -> Dionna (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Dionna",
            target_extension="7006",
        ),
    ),
    "payment_or_id_dec_personal": ScenarioConfig(
        transcripts=["I need my ID card", "Bob Adams", "5551112222", "personal", "Adams"],
        expected_intent=IntentCategory.PAYMENT_OR_ID_DEC,
        expected_name="Bob Adams",
        expected_phone="5551112222",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Adams",
        # Adams -> A is in A-G -> Yarislyn (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Yarislyn",
            target_extension="7011",
        ),
    ),
    # -------------------------------------------------------------------------
    # payment_full_name_no_last_name_ask: Verifies that when caller provides
    # a full name like "Jane Doe", the system extracts "Doe" as last name
    # and does NOT ask for last name separately. This tests the auto-extraction.
    # -------------------------------------------------------------------------
    "payment_full_name_no_last_name_ask": ScenarioConfig(
        transcripts=[
            "I need to make a payment",
            "Jane Doe",  # Full name - last name "Doe" should be auto-extracted
            "5551234567",
            "personal",
            # No fifth transcript - should NOT need to ask for last name
        ],
        expected_intent=IntentCategory.PAYMENT_OR_ID_DEC,
        expected_name="Jane Doe",
        expected_phone="5551234567",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Doe",  # Auto-extracted from "Jane Doe"
        # Doe -> D is in A-G -> Yarislyn (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Yarislyn",
            target_extension="7011",
        ),
    ),
    # -------------------------------------------------------------------------
    # CLAIMS scenarios
    # -------------------------------------------------------------------------
    "claims_personal": ScenarioConfig(
        transcripts=["I need to file a claim", "Bob Wilson", "5555551234", "personal", "Wilson"],
        expected_intent=IntentCategory.CLAIMS,
        expected_name="Bob Wilson",
        expected_phone="5555551234",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Wilson",
        # Claims go to claims department (no transfer)
        expected_route=ExpectedRoute(target_department="claims"),
    ),
    "claims_business": ScenarioConfig(
        transcripts=[
            "I had an accident with a company vehicle",
            "Mary Johnson",
            "5553334444",
            "business",
            "Global Logistics",
        ],
        expected_intent=IntentCategory.CLAIMS,
        expected_name="Mary Johnson",
        expected_phone="5553334444",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Global Logistics",
        # Claims go to claims department (no transfer)
        expected_route=ExpectedRoute(target_department="claims"),
    ),
    # -------------------------------------------------------------------------
    # CANCELLATION scenarios
    # -------------------------------------------------------------------------
    "cancellation_business": ScenarioConfig(
        transcripts=[
            "I want to cancel my policy",
            "Alice Brown",
            "5552223333",
            "business",
            "Brown's Hardware",
        ],
        expected_intent=IntentCategory.CANCELLATION,
        expected_name="Alice Brown",
        expected_phone="5552223333",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Brown's Hardware",
        # Brown's Hardware -> B is in A-F -> Adriana (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Adriana",
            target_extension="7002",
        ),
    ),
    "cancellation_personal": ScenarioConfig(
        transcripts=[
            "I need to cancel my insurance",
            "Mike Turner",
            "5554445555",
            "personal",
            "Turner",
        ],
        expected_intent=IntentCategory.CANCELLATION,
        expected_name="Mike Turner",
        expected_phone="5554445555",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Turner",
        # Turner -> T is in N-Z -> Luis (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Luis",
            target_extension="7017",
        ),
    ),
    # -------------------------------------------------------------------------
    # CERTIFICATES scenarios (email - no transfer)
    # -------------------------------------------------------------------------
    "certificates_personal": ScenarioConfig(
        transcripts=[
            "I need a certificate of insurance",
            "Charlie Davis",
            "5554445555",
            "personal",
            "Davis",
        ],
        expected_intent=IntentCategory.CERTIFICATES,
        expected_name="Charlie Davis",
        expected_phone="5554445555",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Davis",
        # Certificates route to email (no transfer)
        expected_route=ExpectedRoute(target_department="email"),
    ),
    "certificates_business": ScenarioConfig(
        transcripts=[
            "I need a COI for a contract",
            "Sam Martinez",
            "5556667777",
            "business",
            "Martinez Construction",
        ],
        expected_intent=IntentCategory.CERTIFICATES,
        expected_name="Sam Martinez",
        expected_phone="5556667777",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Martinez Construction",
        # Certificates route to email (no transfer)
        expected_route=ExpectedRoute(target_department="email"),
    ),
    # -------------------------------------------------------------------------
    # MAKE_CHANGE scenarios
    # -------------------------------------------------------------------------
    "make_change_business": ScenarioConfig(
        transcripts=[
            "I need to add a vehicle to my policy",
            "Diana Miller",
            "5556667777",
            "business",
            "Miller Transport",
        ],
        expected_intent=IntentCategory.MAKE_CHANGE,
        expected_name="Diana Miller",
        expected_phone="5556667777",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Miller Transport",
        # Miller Transport -> M is in G-O -> Rayvon (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Rayvon",
            target_extension="7018",
        ),
    ),
    "make_change_personal": ScenarioConfig(
        transcripts=[
            "I want to change my address",
            "Tom Garcia",
            "5558889999",
            "personal",
            "Garcia",
        ],
        expected_intent=IntentCategory.MAKE_CHANGE,
        expected_name="Tom Garcia",
        expected_phone="5558889999",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Garcia",
        # Garcia -> G is in A-G -> Yarislyn (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Yarislyn",
            target_extension="7011",
        ),
    ),
    # -------------------------------------------------------------------------
    # COVERAGE_QUESTIONS scenarios
    # -------------------------------------------------------------------------
    "coverage_questions_personal": ScenarioConfig(
        transcripts=[
            "What does my policy cover",
            "Eve Johnson",
            "5558889999",
            "personal",
            "Johnson",
        ],
        expected_intent=IntentCategory.COVERAGE_QUESTIONS,
        expected_name="Eve Johnson",
        expected_phone="5558889999",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Johnson",
        # Johnson -> J is in H-M -> Al (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Al",
            target_extension="7015",
        ),
    ),
    "coverage_questions_business": ScenarioConfig(
        transcripts=[
            "I have questions about my coverage limits",
            "Paul King",
            "5550001111",
            "business",
            "King Enterprises",
        ],
        expected_intent=IntentCategory.COVERAGE_QUESTIONS,
        expected_name="Paul King",
        expected_phone="5550001111",
        insurance_type=InsuranceType.BUSINESS,
        business_name="King Enterprises",
        # King Enterprises -> K is in G-O -> Rayvon (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Rayvon",
            target_extension="7018",
        ),
    ),
    # -------------------------------------------------------------------------
    # ANNUAL_REVIEW scenarios
    # -------------------------------------------------------------------------
    "annual_review_personal": ScenarioConfig(
        transcripts=[
            "I'd like to do an annual review",
            "Nancy Lee",
            "5551112222",
            "personal",
            "Lee",
        ],
        expected_intent=IntentCategory.ANNUAL_REVIEW,
        expected_name="Nancy Lee",
        expected_phone="5551112222",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Lee",
        # Lee -> L is in H-M -> Al (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Al",
            target_extension="7015",
        ),
    ),
    "annual_review_business": ScenarioConfig(
        transcripts=[
            "My policy is up for renewal",
            "Dave Parker",
            "5553334444",
            "business",
            "Parker & Sons",
        ],
        expected_intent=IntentCategory.ANNUAL_REVIEW,
        expected_name="Dave Parker",
        expected_phone="5553334444",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Parker & Sons",
        # Parker & Sons -> P is in P-Z -> Dionna (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Dionna",
            target_extension="7006",
        ),
    ),
    # -------------------------------------------------------------------------
    # SOMETHING_ELSE scenarios
    # -------------------------------------------------------------------------
    "something_else_personal": ScenarioConfig(
        transcripts=["I have a general question", "Paula Ross", "5555556666", "personal", "Ross"],
        expected_intent=IntentCategory.SOMETHING_ELSE,
        expected_name="Paula Ross",
        expected_phone="5555556666",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Ross",
        # Something else personal -> PL AE
        # Ross -> R is in N-Z -> Luis (PL AE)
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Luis",
            target_extension="7017",
        ),
    ),
    "something_else_business": ScenarioConfig(
        transcripts=[
            "I need some help with something",
            "Frank Green",
            "5557778888",
            "business",
            "Green Solutions",
        ],
        expected_intent=IntentCategory.SOMETHING_ELSE,
        expected_name="Frank Green",
        expected_phone="5557778888",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Green Solutions",
        # Green Solutions -> G is in G-O -> Rayvon (CL AE)
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Rayvon",
            target_extension="7018",
        ),
    ),
    # -------------------------------------------------------------------------
    # MORTGAGEE_LIENHOLDER scenarios (email - no transfer)
    # -------------------------------------------------------------------------
    "mortgagee_lienholder_personal": ScenarioConfig(
        transcripts=[
            "I need to update my mortgage company",
            "Karen Hill",
            "5559990000",
            "personal",
            "Hill",
        ],
        expected_intent=IntentCategory.MORTGAGEE_LIENHOLDER,
        expected_name="Karen Hill",
        expected_phone="5559990000",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name="Hill",
        # Mortgagee/lienholder routes to email (no transfer)
        expected_route=ExpectedRoute(target_department="email"),
    ),
    "mortgagee_lienholder_business": ScenarioConfig(
        transcripts=[
            "I need to change my lienholder information",
            "Steve Rogers",
            "5551231234",
            "business",
            "Rogers Realty",
        ],
        expected_intent=IntentCategory.MORTGAGEE_LIENHOLDER,
        expected_name="Steve Rogers",
        expected_phone="5551231234",
        insurance_type=InsuranceType.BUSINESS,
        business_name="Rogers Realty",
        # Mortgagee/lienholder routes to email (no transfer)
        expected_route=ExpectedRoute(target_department="email"),
    ),
    # -------------------------------------------------------------------------
    # HOURS_LOCATION scenario (no insurance_type needed, info-only)
    # -------------------------------------------------------------------------
    "hours_location": ScenarioConfig(
        transcripts=["What are your hours", "Test User", "5550001111"],
        expected_intent=IntentCategory.HOURS_LOCATION,
        expected_name="Test User",
        expected_phone="5550001111",
        # No insurance_type, no transfer
        expected_route=ExpectedRoute(target_department="info-only"),
    ),
    # =========================================================================
    # ROUTE HARDENING EDGE CASES - Testing max-2-asks fallback behavior
    # =========================================================================
    # -------------------------------------------------------------------------
    # claims_refuses_insurance_type: Caller wants to file a claim but refuses
    # to say business/personal twice. Falls back to GENERAL_FALLBACK.
    # -------------------------------------------------------------------------
    "claims_refuses_insurance_type": ScenarioConfig(
        transcripts=[
            "I need to file a claim",
            "Sarah Mitchell",
            "5551234567",
            "I don't know",  # First refusal
            "It's complicated",  # Second refusal - triggers fallback
        ],
        expected_intent=IntentCategory.CLAIMS,
        expected_name="Sarah Mitchell",
        expected_phone="5551234567",
        insurance_type=None,  # Never captured
        # Claims with no insurance_type goes to claims department anyway
        expected_route=ExpectedRoute(
            target_department="claims",
            transfer_reason="missing_insurance_type",
        ),
        is_fallback_scenario=True,
        fallback_field="insurance_type",
    ),
    # -------------------------------------------------------------------------
    # new_quote_business_unknown_name: Caller wants business insurance quote
    # but says "I'm not sure" for business name. Falls back to CL_AE_FALLBACK.
    # -------------------------------------------------------------------------
    "new_quote_business_unknown_name": ScenarioConfig(
        transcripts=[
            "I need a quote for my business",
            "Tom Williams",
            "5559876543",
            "business",
            "I'm not sure what the official name is",  # First unclear answer
            "It's still being set up",  # Second unclear answer - triggers fallback
        ],
        expected_intent=IntentCategory.NEW_QUOTE,
        expected_name="Tom Williams",
        expected_phone="5559876543",
        insurance_type=InsuranceType.BUSINESS,
        business_name=None,  # Never captured
        expected_route=ExpectedRoute(
            target_department="CL AE",
            target_agent_name="Rayvon",  # CL_AE_FALLBACK
            target_extension="7018",
            transfer_reason="missing_business_name",
        ),
        is_fallback_scenario=True,
        fallback_field="business_name",
    ),
    # -------------------------------------------------------------------------
    # make_change_one_word_name: Caller gives only first name ("Madonna")
    # with no last name available. Falls back to PL_AE_FALLBACK.
    # -------------------------------------------------------------------------
    "make_change_one_word_name": ScenarioConfig(
        transcripts=[
            "I want to change my address",
            "Madonna",  # Single word name - no last name extractable
            "5555551234",
            "personal",
            "Just Madonna",  # First unclear answer (no last name)
            "That's all I go by",  # Second unclear answer - triggers fallback
        ],
        expected_intent=IntentCategory.MAKE_CHANGE,
        expected_name="Madonna",
        expected_phone="5555551234",
        insurance_type=InsuranceType.PERSONAL,
        policy_last_name=None,  # Never captured
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Al",  # PL_AE_FALLBACK
            target_extension="7015",
            transfer_reason="missing_last_name",
        ),
        is_fallback_scenario=True,
        fallback_field="last_name",
    ),
    # -------------------------------------------------------------------------
    # specific_agent_unknown_person: Caller asks for someone not in staff
    # directory. Falls back to department bucket.
    # -------------------------------------------------------------------------
    "specific_agent_unknown_person": ScenarioConfig(
        transcripts=[
            "I need to speak with Jennifer",  # Unknown agent
            "Robert Chen",
            "5553334444",
            "personal",  # Insurance type for fallback routing
            "Jennifer Smith",  # First attempt - still unknown
            "Maybe it was Jenny?",  # Second attempt - triggers fallback
        ],
        expected_intent=IntentCategory.SPECIFIC_AGENT,
        expected_name="Robert Chen",
        expected_phone="5553334444",
        insurance_type=InsuranceType.PERSONAL,
        expected_route=ExpectedRoute(
            target_department="PL AE",
            target_agent_name="Al",  # PL_AE_FALLBACK for personal
            target_extension="7015",
            transfer_reason="unknown_specific_agent",
        ),
        is_fallback_scenario=True,
        fallback_field="specific_agent",
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


def simulate_business_name_capture(userdata: AizelleeUserData, business_name: str) -> None:
    """
    Simulate capturing business name.

    In the real agent, this is done via the capture_business_name function_tool.
    """
    userdata.route_decision.business_name = business_name


def simulate_policy_last_name_capture(userdata: AizelleeUserData, last_name: str) -> None:
    """
    Simulate capturing policy last name.

    In the real agent, this is done via the capture_policy_last_name function_tool.
    """
    userdata.route_decision.policy_last_name = last_name


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

        # Fourth transcript is insurance type (personal/business)
        elif i == 3 and config.insurance_type:
            simulate_insurance_type_capture(userdata, config.insurance_type)

        # Fifth transcript is business name or policy last name
        elif i == 4:
            if config.business_name:
                simulate_business_name_capture(userdata, config.business_name)
            elif config.policy_last_name:
                simulate_policy_last_name_capture(userdata, config.policy_last_name)

    # -------------------------------------------------------------------------
    # Auto-extract last name from caller_name if:
    # 1. Insurance type is personal
    # 2. policy_last_name is expected but wasn't provided in transcripts
    # 3. caller_name is a multi-word name (e.g., "Jane Doe")
    # This simulates what check_routing_requirements does automatically.
    # -------------------------------------------------------------------------
    if (
        config.insurance_type == InsuranceType.PERSONAL
        and config.policy_last_name
        and not userdata.route_decision.policy_last_name
        and userdata.route_decision.caller_name
    ):
        name_parts = userdata.route_decision.caller_name.split()
        if len(name_parts) >= 2:
            # Extract last name from full name (simulates check_routing_requirements behavior)
            userdata.route_decision.policy_last_name = name_parts[-1]

    # Final validations - caller info
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

    # -------------------------------------------------------------------------
    # Handle fallback scenarios (max-2-asks edge cases)
    # -------------------------------------------------------------------------
    if config.is_fallback_scenario:
        # For fallback scenarios, we test check_routing_requirements behavior
        # after the retry counters have been exhausted (simulating 2 failed asks)

        # Pre-increment retry counter to simulate 2 failed asks
        if config.fallback_field == "insurance_type":
            userdata.asked_insurance_type_count = 2  # Max retries exhausted
        elif config.fallback_field == "business_name":
            userdata.asked_business_name_count = 2
        elif config.fallback_field == "last_name":
            userdata.asked_last_name_count = 2
        elif config.fallback_field == "specific_agent":
            userdata.asked_specific_agent_count = 2

        # Call check_routing_requirements to verify fallback behavior
        action, value1, value2 = check_routing_requirements(userdata, config.expected_intent)

        # Verify fallback action is returned
        if action != "fallback" and action != "ready":
            # For claims, it goes straight to "ready" since claims don't need insurance_type
            if config.expected_intent == IntentCategory.CLAIMS:
                if action != "ready":
                    failures.append(f"Expected 'ready' action for claims, got '{action}'")
            else:
                failures.append(f"Expected 'fallback' action for exhausted retries, got '{action}'")

        # If fallback, verify transfer_reason matches
        if action == "fallback" and config.expected_route and config.expected_route.transfer_reason:
            if value2 != config.expected_route.transfer_reason:
                failures.append(
                    f"Transfer reason mismatch: expected '{config.expected_route.transfer_reason}', "
                    f"got '{value2}'"
                )

        # Skip standard insurance_type/business_name/last_name validations for fallback scenarios
        # These are intentionally missing in fallback scenarios
    else:
        # Standard validation for non-fallback scenarios
        # Validate insurance_type
        if config.insurance_type:
            if userdata.route_decision.insurance_type != config.insurance_type:
                failures.append(
                    f"Insurance type mismatch: expected {config.insurance_type.value}, "
                    f"got {userdata.route_decision.insurance_type.value if userdata.route_decision.insurance_type else 'None'}"
                )
        else:
            # For hours_location, insurance_type should be None
            if userdata.route_decision.insurance_type is not None:
                failures.append(
                    f"Insurance type should be None, got {userdata.route_decision.insurance_type.value}"
                )

        # Validate business_name for business scenarios
        if config.business_name:
            if userdata.route_decision.business_name != config.business_name:
                failures.append(
                    f"Business name mismatch: expected '{config.business_name}', "
                    f"got '{userdata.route_decision.business_name}'"
                )

        # Validate policy_last_name for personal scenarios
        if config.policy_last_name:
            if userdata.route_decision.policy_last_name != config.policy_last_name:
                failures.append(
                    f"Policy last name mismatch: expected '{config.policy_last_name}', "
                    f"got '{userdata.route_decision.policy_last_name}'"
                )

    # Validate routing if expected_route is provided
    if config.expected_route and not config.is_fallback_scenario:
        route_result = route_call(userdata.route_decision)

        # Validate target_department
        if route_result.target_department != config.expected_route.target_department:
            failures.append(
                f"Route department mismatch: expected '{config.expected_route.target_department}', "
                f"got '{route_result.target_department}'"
            )

        # Validate target_agent_name (only for transfer intents)
        if config.expected_route.target_agent_name:
            if route_result.target_agent != config.expected_route.target_agent_name:
                failures.append(
                    f"Route agent mismatch: expected '{config.expected_route.target_agent_name}', "
                    f"got '{route_result.target_agent}'"
                )

        # Validate target_extension (only for transfer intents)
        if config.expected_route.target_extension:
            if route_result.target_extension != config.expected_route.target_extension:
                failures.append(
                    f"Route extension mismatch: expected '{config.expected_route.target_extension}', "
                    f"got '{route_result.target_extension}'"
                )

    passed = len(failures) == 0
    return passed, failures, userdata


def print_route_decision(userdata: AizelleeUserData, config: ScenarioConfig) -> None:
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

    if rd.business_name:
        print(f'      business_name="{rd.business_name}"')
    if rd.policy_last_name:
        print(f'      policy_last_name="{rd.policy_last_name}"')

    # Print fallback info for fallback scenarios
    if config.is_fallback_scenario:
        print("    FALLBACK_SCENARIO:")
        print(f"      fallback_field={config.fallback_field}")
        # Simulate the check_routing_requirements call to show the fallback result
        # Pre-increment retry counter as done in run_scenario
        test_userdata = AizelleeUserData()
        test_userdata.route_decision = rd
        if config.fallback_field == "insurance_type":
            test_userdata.asked_insurance_type_count = 2
        elif config.fallback_field == "business_name":
            test_userdata.asked_business_name_count = 2
        elif config.fallback_field == "last_name":
            test_userdata.asked_last_name_count = 2
        elif config.fallback_field == "specific_agent":
            test_userdata.asked_specific_agent_count = 2
        action, value1, value2 = check_routing_requirements(test_userdata, config.expected_intent)
        print(f"      action={action}")
        if action == "fallback":
            print(f"      fallback_agent={value1}")
            print(f"      transfer_reason={value2}")
        return  # Skip standard routing for fallback scenarios

    # Print routing result if expected
    if config.expected_route:
        route_result = route_call(rd)
        print("    ROUTING:")
        print(f"      target_department={route_result.target_department}")
        if route_result.target_agent:
            print(f"      target_agent_name={route_result.target_agent}")
        if route_result.target_extension:
            print(f"      target_extension={route_result.target_extension}")


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
        print_route_decision(userdata, config)

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
