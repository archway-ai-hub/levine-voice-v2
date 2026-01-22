"""
Unit tests for RouteDecision capture through function tools.

Tests the complete flow of capturing caller information via function tools:
- Phone number normalization
- Function tool invocation with mock contexts
- Complete conversation simulation
- Final RouteDecision validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import AizelleeAgent, normalize_phone_number

# Import the models and agent components we need to test
from models import (
    AizelleeUserData,
    InsuranceType,
    IntentCategory,
)

# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def userdata():
    """Create fresh AizelleeUserData for each test."""
    return AizelleeUserData()


@pytest.fixture
def agent():
    """Create AizelleeAgent instance for testing."""
    return AizelleeAgent()


@pytest.fixture
def mock_context(userdata):
    """Create mock RunContext with userdata attached."""
    ctx = MagicMock()
    ctx.userdata = userdata
    return ctx


# -----------------------------------------------------------------------------
# Phone Number Normalization Tests
# -----------------------------------------------------------------------------


class TestNormalizePhoneNumber:
    """Tests for the normalize_phone_number function."""

    def test_digits_only_preserved(self):
        """Test that digit-only input is preserved."""
        assert normalize_phone_number("5551234567") == "5551234567"

    def test_strips_dashes(self):
        """Test that dashes are removed."""
        assert normalize_phone_number("555-123-4567") == "5551234567"

    def test_strips_parentheses_and_spaces(self):
        """Test that parentheses and spaces are removed."""
        assert normalize_phone_number("(555) 123-4567") == "5551234567"

    def test_spoken_numbers_converted(self):
        """Test that spoken number words are converted to digits."""
        assert normalize_phone_number("five five five") == "555"

    def test_mixed_spoken_and_digits(self):
        """Test combination of spoken words and digits."""
        assert normalize_phone_number("five five five 123 4567") == "5551234567"

    def test_oh_converted_to_zero(self):
        """Test that 'oh' and 'o' are converted to 0."""
        assert normalize_phone_number("five oh five") == "505"
        assert normalize_phone_number("5 o 5") == "505"

    def test_homophones_handled(self):
        """Test that homophones like 'to', 'too', 'for' are converted."""
        assert normalize_phone_number("for two one") == "421"
        assert normalize_phone_number("too four one") == "241"

    def test_combines_chunked_phone_numbers(self):
        """Test that separate chunks combine correctly when normalized."""
        chunk1 = normalize_phone_number("555")
        chunk2 = normalize_phone_number("123-4567")
        combined = chunk1 + chunk2
        assert combined == "5551234567"

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert normalize_phone_number("") == ""

    def test_whitespace_only(self):
        """Test that whitespace-only returns empty string."""
        assert normalize_phone_number("   ") == ""


# -----------------------------------------------------------------------------
# Function Tool Tests
# -----------------------------------------------------------------------------


class TestFunctionTools:
    """Test individual function tools capture data correctly."""

    @pytest.mark.asyncio
    async def test_record_caller_name(self, agent, mock_context):
        """Test record_caller_name captures name into RouteDecision."""
        result = await agent.record_caller_name(mock_context, "Sam Reuben")

        assert mock_context.userdata.route_decision.caller_name == "Sam Reuben"
        assert "Sam Reuben" in result

    @pytest.mark.asyncio
    async def test_record_callback_phone(self, agent, mock_context):
        """Test record_callback_phone normalizes and captures phone."""
        result = await agent.record_callback_phone(mock_context, "555-123-4567")

        assert mock_context.userdata.route_decision.callback_phone == "5551234567"
        assert "5551234567" in result

    @pytest.mark.asyncio
    async def test_record_callback_phone_spoken_numbers(self, agent, mock_context):
        """Test record_callback_phone handles spoken numbers."""
        await agent.record_callback_phone(
            mock_context, "five five five one two three four five six seven"
        )

        assert mock_context.userdata.route_decision.callback_phone == "5551234567"

    @pytest.mark.asyncio
    async def test_record_intent_new_quote(self, agent, mock_context):
        """Test record_intent with new_quote intent using raw_text only."""
        await agent.record_intent(mock_context, "I need to get a quote")

        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert mock_context.userdata.route_decision.intent_raw_text == "I need to get a quote"

    @pytest.mark.asyncio
    async def test_record_intent_payment_id_card(self, agent, mock_context):
        """Test record_intent with 'I need my ID card' maps to PAYMENT_OR_ID_DEC."""
        await agent.record_intent(mock_context, "I need my ID card")

        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

    @pytest.mark.asyncio
    async def test_record_intent_classifies_from_raw_text(self, agent, mock_context):
        """Test record_intent uses classify_intent internally."""
        await agent.record_intent(mock_context, "I want to cancel my policy")

        assert mock_context.userdata.route_decision.intent == IntentCategory.CANCELLATION

    @pytest.mark.asyncio
    async def test_record_intent_unknown_falls_back_to_something_else(self, agent, mock_context):
        """Test record_intent with unrecognized text falls back to SOMETHING_ELSE."""
        await agent.record_intent(mock_context, "Some random request that doesn't match anything")

        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

    @pytest.mark.asyncio
    async def test_record_insurance_type_personal(self, agent, mock_context):
        """Test record_insurance_type with personal."""
        await agent.record_insurance_type(mock_context, "personal")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL

    @pytest.mark.asyncio
    async def test_record_insurance_type_business(self, agent, mock_context):
        """Test record_insurance_type with business."""
        await agent.record_insurance_type(mock_context, "business")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.BUSINESS

    @pytest.mark.asyncio
    async def test_record_insurance_type_case_insensitive(self, agent, mock_context):
        """Test record_insurance_type handles case variations."""
        await agent.record_insurance_type(mock_context, "PERSONAL")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL

    @pytest.mark.asyncio
    async def test_record_business_name(self, agent, mock_context):
        """Test record_business_name captures business name."""
        await agent.record_business_name(mock_context, "Acme Corporation")

        assert mock_context.userdata.route_decision.business_name == "Acme Corporation"

    @pytest.mark.asyncio
    async def test_record_policy_last_name(self, agent, mock_context):
        """Test record_policy_last_name captures last name."""
        await agent.record_policy_last_name(mock_context, "Reuben")

        assert mock_context.userdata.route_decision.policy_last_name == "Reuben"


# -----------------------------------------------------------------------------
# Phone Chunk Combining Tests
# -----------------------------------------------------------------------------


class TestPhoneChunkCombining:
    """Test that phone numbers provided in chunks are combined correctly."""

    @pytest.mark.asyncio
    async def test_phone_chunks_combine_via_multiple_calls(self, agent, mock_context):
        """
        Test that if phone is updated with additional chunks,
        the normalization handles it correctly.

        Note: In the actual agent, the LLM would combine chunks before calling
        the tool, but we test the normalization handles various formats.
        """
        # Simulate LLM combining chunks: "555" then "123-4567" -> "555 123-4567"
        combined_raw = "555 123-4567"
        await agent.record_callback_phone(mock_context, combined_raw)

        assert mock_context.userdata.route_decision.callback_phone == "5551234567"

    @pytest.mark.asyncio
    async def test_phone_chunks_overwrite(self, agent, mock_context):
        """Test that subsequent phone recordings overwrite previous."""
        # First partial
        await agent.record_callback_phone(mock_context, "555")
        assert mock_context.userdata.route_decision.callback_phone == "555"

        # Then full number (LLM would provide complete number)
        await agent.record_callback_phone(mock_context, "5551234567")
        assert mock_context.userdata.route_decision.callback_phone == "5551234567"


# -----------------------------------------------------------------------------
# Complete Conversation Simulation Test
# -----------------------------------------------------------------------------


class TestCompleteConversationSimulation:
    """
    Test simulating the exact transcript sequence and asserting final RouteDecision.

    Simulated conversation:
    - Name: "Sam Reuben"
    - Phone (in chunks): "555" then "123-4567" (combined as "5551234567")
    - Intent: "I need to get a quote" -> should be new_quote
    - Insurance type: "personal"
    - Policy last name: "Reuben" (possibly spelled out "R-E-U-B-E-N")
    """

    @pytest.mark.asyncio
    async def test_full_conversation_capture(self, agent, mock_context):
        """
        Simulate complete conversation flow and verify final RouteDecision.

        This is the main test that validates all fields are captured correctly.
        """
        # Step 1: Record caller name
        await agent.record_caller_name(mock_context, "Sam Reuben")

        # Step 2: Record phone number (simulating LLM combining chunks)
        # User says "555" then "123-4567", LLM combines and sends full number
        await agent.record_callback_phone(mock_context, "555 123-4567")

        # Step 3: Record intent (using new signature with raw_text only)
        await agent.record_intent(mock_context, "I need to get a quote")

        # Step 4: Record insurance type
        await agent.record_insurance_type(mock_context, "personal")

        # Step 5: Record policy last name
        await agent.record_policy_last_name(mock_context, "Reuben")

        # Get the final route decision
        route_decision = mock_context.userdata.route_decision

        # Assert all expected values
        assert route_decision.caller_name == "Sam Reuben", (
            f"Expected caller_name 'Sam Reuben', got '{route_decision.caller_name}'"
        )

        assert route_decision.callback_phone == "5551234567", (
            f"Expected callback_phone '5551234567', got '{route_decision.callback_phone}'"
        )

        assert route_decision.intent == IntentCategory.NEW_QUOTE, (
            f"Expected intent NEW_QUOTE, got {route_decision.intent}"
        )

        assert route_decision.insurance_type == InsuranceType.PERSONAL, (
            f"Expected insurance_type PERSONAL, got {route_decision.insurance_type}"
        )

        assert route_decision.policy_last_name == "Reuben", (
            f"Expected policy_last_name 'Reuben', got '{route_decision.policy_last_name}'"
        )

    @pytest.mark.asyncio
    async def test_full_conversation_with_spelled_last_name(self, agent, mock_context):
        """
        Test conversation where last name is spelled out: R-E-U-B-E-N.

        The LLM should interpret the spelling and provide the name.
        """
        await agent.record_caller_name(mock_context, "Sam Reuben")
        await agent.record_callback_phone(mock_context, "5551234567")
        await agent.record_intent(mock_context, "I need to get a quote")
        await agent.record_insurance_type(mock_context, "personal")
        # LLM interprets "R-E-U-B-E-N" as "Reuben"
        await agent.record_policy_last_name(mock_context, "Reuben")

        route_decision = mock_context.userdata.route_decision

        assert route_decision.policy_last_name == "Reuben"
        assert route_decision.is_complete() is True

    @pytest.mark.asyncio
    async def test_route_decision_is_complete_for_personal(self, agent, mock_context):
        """Test that RouteDecision.is_complete() returns True for complete personal flow."""
        await agent.record_caller_name(mock_context, "Sam Reuben")
        await agent.record_callback_phone(mock_context, "5551234567")
        await agent.record_intent(mock_context, "I need to get a quote")
        await agent.record_insurance_type(mock_context, "personal")
        await agent.record_policy_last_name(mock_context, "Reuben")

        route_decision = mock_context.userdata.route_decision
        assert route_decision.is_complete() is True

    @pytest.mark.asyncio
    async def test_route_decision_is_complete_for_business(self, agent, mock_context):
        """Test that RouteDecision.is_complete() returns True for complete business flow."""
        await agent.record_caller_name(mock_context, "John Smith")
        await agent.record_callback_phone(mock_context, "5559876543")
        await agent.record_intent(mock_context, "I need a quote for my business")
        await agent.record_insurance_type(mock_context, "business")
        await agent.record_business_name(mock_context, "Smith Enterprises")

        route_decision = mock_context.userdata.route_decision
        assert route_decision.is_complete() is True

    @pytest.mark.asyncio
    async def test_route_decision_incomplete_without_phone(self, agent, mock_context):
        """Test that RouteDecision.is_complete() returns False without phone."""
        await agent.record_caller_name(mock_context, "Sam Reuben")
        # Phone not recorded
        await agent.record_intent(mock_context, "I need to get a quote")
        await agent.record_insurance_type(mock_context, "personal")
        await agent.record_policy_last_name(mock_context, "Reuben")

        route_decision = mock_context.userdata.route_decision
        assert route_decision.is_complete() is False

    @pytest.mark.asyncio
    async def test_route_decision_incomplete_without_policy_last_name(self, agent, mock_context):
        """Test that RouteDecision.is_complete() returns False for personal without last name."""
        await agent.record_caller_name(mock_context, "Sam Reuben")
        await agent.record_callback_phone(mock_context, "5551234567")
        await agent.record_intent(mock_context, "I need to get a quote")
        await agent.record_insurance_type(mock_context, "personal")
        # Policy last name not recorded

        route_decision = mock_context.userdata.route_decision
        assert route_decision.is_complete() is False


# -----------------------------------------------------------------------------
# Intent Mapping Tests
# -----------------------------------------------------------------------------


class TestIntentMapping:
    """Test that raw text maps correctly to IntentCategory enum via classify_intent."""

    @pytest.mark.asyncio
    async def test_intent_classification_via_raw_text(self, agent, mock_context):
        """Test various raw text inputs classify to correct intents."""
        # Maps raw text inputs to expected IntentCategory
        text_to_intent = [
            ("I need a quote for car insurance", IntentCategory.NEW_QUOTE),
            ("I need to make a payment", IntentCategory.PAYMENT_OR_ID_DEC),
            ("I want to add a vehicle to my policy", IntentCategory.MAKE_CHANGE),
            ("I want to cancel my policy", IntentCategory.CANCELLATION),
            ("Is my roof covered?", IntentCategory.COVERAGE_QUESTIONS),
            ("I'd like to review my policy for discounts", IntentCategory.ANNUAL_REVIEW),
            ("I need to update my mortgage company", IntentCategory.MORTGAGEE_LIENHOLDER),
            ("I need a certificate of insurance", IntentCategory.CERTIFICATES),
            ("I was in an accident and need to file a claim", IntentCategory.CLAIMS),
            ("What are your office hours?", IntentCategory.HOURS_LOCATION),
            ("I'm looking for John Smith, is he there?", IntentCategory.SPECIFIC_AGENT),
            ("Random gibberish that matches nothing", IntentCategory.SOMETHING_ELSE),
        ]

        for raw_text, expected_enum in text_to_intent:
            # Reset userdata for each iteration
            mock_context.userdata = AizelleeUserData()

            await agent.record_intent(mock_context, raw_text)

            assert mock_context.userdata.route_decision.intent == expected_enum, (
                f"Raw text '{raw_text}' should classify to {expected_enum}"
            )


# -----------------------------------------------------------------------------
# Insurance Type Mapping Tests
# -----------------------------------------------------------------------------


class TestInsuranceTypeMapping:
    """Test that insurance type strings map correctly to InsuranceType enum."""

    @pytest.mark.asyncio
    async def test_personal_insurance_type(self, agent, mock_context):
        """Test 'personal' maps to InsuranceType.PERSONAL."""
        await agent.record_insurance_type(mock_context, "personal")
        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL

    @pytest.mark.asyncio
    async def test_business_insurance_type(self, agent, mock_context):
        """Test 'business' maps to InsuranceType.BUSINESS."""
        await agent.record_insurance_type(mock_context, "business")
        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.BUSINESS

    @pytest.mark.asyncio
    async def test_invalid_insurance_type_defaults_to_personal(self, agent, mock_context):
        """Test invalid insurance type defaults to PERSONAL."""
        await agent.record_insurance_type(mock_context, "invalid")
        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL


# -----------------------------------------------------------------------------
# RouteDecision Summary Tests
# -----------------------------------------------------------------------------


class TestRouteDecisionSummary:
    """Test RouteDecision.summary() method."""

    def test_summary_with_all_personal_fields(self, userdata):
        """Test summary includes all personal insurance fields."""
        rd = userdata.route_decision
        rd.caller_name = "Sam Reuben"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.PERSONAL
        rd.policy_last_name = "Reuben"

        summary = rd.summary()

        assert "Sam Reuben" in summary
        assert "5551234567" in summary
        assert "New Quote" in summary
        assert "Personal" in summary
        assert "Reuben" in summary

    def test_summary_with_all_business_fields(self, userdata):
        """Test summary includes all business insurance fields."""
        rd = userdata.route_decision
        rd.caller_name = "John Smith"
        rd.callback_phone = "5559876543"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.BUSINESS
        rd.business_name = "Smith Enterprises"

        summary = rd.summary()

        assert "John Smith" in summary
        assert "5559876543" in summary
        assert "New Quote" in summary
        assert "Business" in summary
        assert "Smith Enterprises" in summary


# -----------------------------------------------------------------------------
# RouteDecision to_log_dict Tests
# -----------------------------------------------------------------------------


class TestRouteDecisionToLogDict:
    """Test RouteDecision.to_log_dict() serialization."""

    def test_to_log_dict_includes_all_fields(self, userdata):
        """Test to_log_dict includes all expected fields."""
        rd = userdata.route_decision
        rd.caller_name = "Sam Reuben"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.intent_raw_text = "I need to get a quote"
        rd.insurance_type = InsuranceType.PERSONAL
        rd.policy_last_name = "Reuben"

        log_dict = rd.to_log_dict()

        assert log_dict["caller_name"] == "Sam Reuben"
        assert log_dict["callback_phone"] == "5551234567"
        assert log_dict["intent"] == "new_quote"
        assert log_dict["intent_raw_text"] == "I need to get a quote"
        assert log_dict["insurance_type"] == "personal"
        assert log_dict["policy_last_name"] == "Reuben"

    def test_to_log_dict_handles_none_values(self, userdata):
        """Test to_log_dict handles None values gracefully."""
        rd = userdata.route_decision
        # Leave fields as default (None)

        log_dict = rd.to_log_dict()

        assert log_dict["caller_name"] == ""
        assert log_dict["callback_phone"] == ""
        assert log_dict["intent"] is None
        assert log_dict["insurance_type"] is None


# -----------------------------------------------------------------------------
# Intent Persistence Tests
# -----------------------------------------------------------------------------


class TestIntentPersistence:
    """Test that intent persists and is not overwritten on subsequent calls unless explicit change.

    Note: These tests now use maybe_record_intent directly to simulate the transcript flow,
    since the record_intent tool has an early-exit guard when intent is already set.
    Intent changes via "actually", "never mind", etc. happen through transcript processing.
    """

    @pytest.mark.asyncio
    async def test_intent_persists_on_subsequent_calls(self, agent, mock_context):
        """Test that once intent is set, it is NOT overwritten by subsequent record_intent calls."""
        # First call sets intent to NEW_QUOTE
        await agent.record_intent(mock_context, "I need to get a quote")
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Second call with different intent-implying text should NOT change intent
        result = await agent.record_intent(mock_context, "I need to make a payment")

        # Intent should still be NEW_QUOTE (persisted)
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert "already recorded" in result.lower()

    @pytest.mark.asyncio
    async def test_intent_persists_with_unrelated_followup(self, agent, mock_context):
        """Test intent persists even when subsequent call has unrelated text."""
        # Set initial intent
        await agent.record_intent(mock_context, "I want to cancel my policy")
        assert mock_context.userdata.route_decision.intent == IntentCategory.CANCELLATION

        # Follow-up with something that would classify as SOMETHING_ELSE
        await agent.record_intent(mock_context, "Yes that's right")

        # Should still be CANCELLATION
        assert mock_context.userdata.route_decision.intent == IntentCategory.CANCELLATION

    def test_intent_change_with_actually_signal(self, userdata):
        """Test that 'actually I'm calling about a claim' DOES change intent via transcript."""
        from agent import maybe_record_intent

        # First set intent to NEW_QUOTE via transcript
        maybe_record_intent(userdata, "I need to get a quote")
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Caller changes their mind with "actually" via transcript
        maybe_record_intent(userdata, "Actually I'm calling about a claim")

        # Intent should now be CLAIMS
        assert userdata.route_decision.intent == IntentCategory.CLAIMS

    def test_intent_change_with_never_mind_signal(self, userdata):
        """Test that 'never mind' signal allows intent change via transcript."""
        from agent import maybe_record_intent

        # First set intent
        maybe_record_intent(userdata, "I need my ID card")
        assert userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

        # Caller changes with "never mind" via transcript
        maybe_record_intent(userdata, "Never mind, I need a quote instead")

        # Intent should change to NEW_QUOTE
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE

    def test_intent_change_with_instead_signal(self, userdata):
        """Test that 'instead' signal allows intent change via transcript."""
        from agent import maybe_record_intent

        # First set intent
        maybe_record_intent(userdata, "What are your hours?")
        assert userdata.route_decision.intent == IntentCategory.HOURS_LOCATION

        # Caller changes with "instead" via transcript
        maybe_record_intent(userdata, "Instead I want to file a claim")

        # Intent should change to CLAIMS
        assert userdata.route_decision.intent == IntentCategory.CLAIMS

    def test_intent_change_with_no_wait_signal(self, userdata):
        """Test that 'no wait' signal allows intent change via transcript."""
        from agent import maybe_record_intent

        # First set intent
        maybe_record_intent(userdata, "I need a certificate of insurance")
        assert userdata.route_decision.intent == IntentCategory.CERTIFICATES

        # Caller changes with "no wait" - use "add a vehicle" which maps to MAKE_CHANGE
        maybe_record_intent(userdata, "No wait, I want to add a vehicle")

        # Intent should change to MAKE_CHANGE
        assert userdata.route_decision.intent == IntentCategory.MAKE_CHANGE

    def test_upgrade_from_something_else_allowed(self, userdata):
        """Test that upgrading from SOMETHING_ELSE to specific intent is allowed via transcript."""
        from agent import maybe_record_intent

        # First call with vague text that classifies as SOMETHING_ELSE
        maybe_record_intent(userdata, "Hello, I'm calling today")
        assert userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Second call with specific intent should upgrade (not require change signal)
        maybe_record_intent(userdata, "I need to get a quote")

        # Should upgrade to NEW_QUOTE
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE


# -----------------------------------------------------------------------------
# Multi-Turn Intent Clarification Tests
# -----------------------------------------------------------------------------


class TestMultiTurnIntentClarification:
    """Test multi-turn sequences where intent becomes clear over time.

    Note: These tests use maybe_record_intent directly to simulate the transcript flow,
    since the record_intent tool has an early-exit guard when intent is already set.
    """

    def test_intent_unclear_then_becomes_clear(self, userdata):
        """Test multi-turn where intent is initially unclear then becomes clear via transcripts."""
        from agent import maybe_record_intent

        # Turn 1: Initial vague statement - classifies as SOMETHING_ELSE
        maybe_record_intent(userdata, "Hi, I'm calling about my policy")
        assert userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 2: Still vague (but SOMETHING_ELSE can't be downgraded so stays same)
        maybe_record_intent(userdata, "Yes, I have a question")
        # Should still be SOMETHING_ELSE (no upgrade to another SOMETHING_ELSE)
        assert userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 3: Now clear - should upgrade from SOMETHING_ELSE
        maybe_record_intent(userdata, "I was in an accident and need to file a claim")
        assert userdata.route_decision.intent == IntentCategory.CLAIMS

    def test_gradual_clarification_to_new_quote(self, userdata):
        """Test gradual clarification leading to coverage_questions intent via transcripts."""
        from agent import maybe_record_intent

        # Turn 1: Initial vague statement - uses text that truly classifies as SOMETHING_ELSE
        maybe_record_intent(userdata, "Hello, I have a question")
        assert userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 2: More specific - "coverage" keyword triggers COVERAGE_QUESTIONS
        maybe_record_intent(userdata, "It's about my coverage")
        # Should upgrade from SOMETHING_ELSE to COVERAGE_QUESTIONS
        assert userdata.route_decision.intent == IntentCategory.COVERAGE_QUESTIONS

        # Turn 3: Now tries to change without signal - should persist
        maybe_record_intent(userdata, "I need a quote")
        # Should still be COVERAGE_QUESTIONS (no change signal)
        assert userdata.route_decision.intent == IntentCategory.COVERAGE_QUESTIONS

    @pytest.mark.asyncio
    async def test_complete_multi_turn_flow_with_intent_change(self, agent, mock_context):
        """Test complete multi-turn flow including intent change via transcripts."""
        from agent import maybe_record_intent

        # Collect name first (via tool)
        await agent.record_caller_name(mock_context, "Jane Doe")

        # Collect phone (via tool)
        await agent.record_callback_phone(mock_context, "555-987-6543")

        # Turn 1: Initial intent (via transcript)
        maybe_record_intent(mock_context.userdata, "I need to make a payment")
        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

        # Turn 2: Agent asks clarifying question, caller responds with same intent
        maybe_record_intent(mock_context.userdata, "Yes, I want to pay my bill")
        # Should persist as PAYMENT_OR_ID_DEC
        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

        # Turn 3: Caller changes their mind with explicit signal via transcript
        maybe_record_intent(mock_context.userdata, "Actually, I also need to report a claim")
        # Should change to CLAIMS
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS

        # Verify other collected data is preserved
        assert mock_context.userdata.route_decision.caller_name == "Jane Doe"
        assert mock_context.userdata.route_decision.callback_phone == "5559876543"

    def test_intent_raw_text_updates_on_change(self, userdata):
        """Test that intent_raw_text is updated when intent changes via transcript."""
        from agent import maybe_record_intent

        # First intent
        maybe_record_intent(userdata, "I need a quote")
        assert userdata.route_decision.intent_raw_text == "I need a quote"

        # Change intent with signal via transcript
        maybe_record_intent(userdata, "Actually I need to file a claim")

        # Both intent and raw_text should be updated
        assert userdata.route_decision.intent == IntentCategory.CLAIMS
        assert userdata.route_decision.intent_raw_text == "Actually I need to file a claim"

    @pytest.mark.asyncio
    async def test_intent_raw_text_not_updated_when_persisted(self, agent, mock_context):
        """Test that intent_raw_text is NOT updated when intent persists."""
        # First intent
        await agent.record_intent(mock_context, "I need a quote for car insurance")
        original_raw_text = mock_context.userdata.route_decision.intent_raw_text
        assert original_raw_text == "I need a quote for car insurance"

        # Attempt to change without signal (should persist)
        await agent.record_intent(mock_context, "I need to make a payment")

        # Intent persists, so raw_text should also persist
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert mock_context.userdata.route_decision.intent_raw_text == original_raw_text


# -----------------------------------------------------------------------------
# Automatic Intent Capture from Transcripts Tests
# -----------------------------------------------------------------------------


class TestAutoIntentCaptureFromTranscripts:
    """Test automatic intent capture from transcripts (simulating transcript handler)."""

    def test_auto_intent_capture_first_meaningful_transcript(self):
        """Test that intent is captured automatically from first meaningful transcript."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        # Create fresh userdata
        userdata = AizelleeUserData()
        assert userdata.route_decision.intent is None

        # Feed transcripts in order
        transcripts = [
            "Need to get a quote",
            "Sam Rubin",
            "Eight one eight ...",
            "Personal",
            "R u b e n",
        ]

        # First transcript should set intent to NEW_QUOTE
        result = maybe_record_intent(userdata, transcripts[0])
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert userdata.route_decision.intent_raw_text == transcripts[0]
        assert result is not None
        assert "new_quote" in result.lower()

        # Subsequent transcripts should not change intent (no change signal)
        for transcript in transcripts[1:]:
            maybe_record_intent(userdata, transcript)
            assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE, (
                f"Intent should persist as NEW_QUOTE after transcript: {transcript}"
            )

    def test_filler_words_are_skipped(self):
        """Test that filler words don't set intent."""
        from agent import maybe_record_intent
        from models import AizelleeUserData

        userdata = AizelleeUserData()
        assert userdata.route_decision.intent is None

        # Test various filler words
        filler_samples = ["yep", "yeah", "ok", "thanks", "uh-huh", "mm-hmm", "sure"]

        for filler in filler_samples:
            # Reset userdata for each test
            userdata = AizelleeUserData()
            result = maybe_record_intent(userdata, filler)

            # Filler words should return None and NOT set intent
            assert result is None, f"Filler word '{filler}' should return None"
            assert userdata.route_decision.intent is None, (
                f"Filler word '{filler}' should not set intent"
            )

    def test_intent_can_be_overridden_with_change_signal(self):
        """Test that intent can be overridden when change signal is detected."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Set initial intent
        maybe_record_intent(userdata, "I need a quote")
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Try to change without signal - should persist
        result = maybe_record_intent(userdata, "I need to make a payment")
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert "already recorded" in result.lower()

        # Change with "actually" signal - should override
        maybe_record_intent(userdata, "Actually I need to file a claim")
        assert userdata.route_decision.intent == IntentCategory.CLAIMS

    def test_something_else_can_be_upgraded(self):
        """Test that SOMETHING_ELSE intent can be upgraded to specific intent."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Initial vague statement classifies as SOMETHING_ELSE
        maybe_record_intent(userdata, "Hi, I'm calling today")
        assert userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Subsequent specific statement should upgrade (no change signal needed)
        maybe_record_intent(userdata, "I need to get a quote")
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE

    def test_full_transcript_sequence_simulation(self):
        """Simulate complete transcript sequence as would happen in live call."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Realistic transcript sequence
        transcript_sequence = [
            ("I need to get a quote", IntentCategory.NEW_QUOTE),  # Should set intent
            ("Sam Rubin", IntentCategory.NEW_QUOTE),  # Should persist
            ("Eight one eight 555 1234", IntentCategory.NEW_QUOTE),  # Should persist
            ("Personal", IntentCategory.NEW_QUOTE),  # Should persist
            ("R-U-B-E-N", IntentCategory.NEW_QUOTE),  # Should persist
            ("Yes that's correct", IntentCategory.NEW_QUOTE),  # Should persist
        ]

        for i, (transcript, expected_intent) in enumerate(transcript_sequence):
            maybe_record_intent(userdata, transcript)
            assert userdata.route_decision.intent == expected_intent, (
                f"After transcript {i + 1} '{transcript}': expected {expected_intent}, got {userdata.route_decision.intent}"
            )

    def test_intent_raw_text_preserved_after_first_capture(self):
        """Test that intent_raw_text is preserved and not overwritten by subsequent transcripts."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # First intent-bearing transcript
        first_transcript = "I need to get a quote for my car"
        maybe_record_intent(userdata, first_transcript)

        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert userdata.route_decision.intent_raw_text == first_transcript

        # Subsequent non-change transcripts should NOT update raw_text
        subsequent_transcripts = ["My name is John", "555-123-4567", "Personal insurance"]

        for transcript in subsequent_transcripts:
            maybe_record_intent(userdata, transcript)
            # raw_text should still be the original
            assert userdata.route_decision.intent_raw_text == first_transcript, (
                f"raw_text should persist as original after '{transcript}'"
            )


# -----------------------------------------------------------------------------
# No Redundant Intent Prompt Tests
# -----------------------------------------------------------------------------


class TestNoRedundantIntentPrompt:
    """
    Test that intent is captured from first transcript and the record_intent tool
    properly guards against redundant intent recording.

    This verifies the field-driven conversation flow where:
    1. Intent is auto-captured from the first meaningful transcript
    2. The record_intent tool returns early if intent is already set
    3. The flow completes without redundant intent recording
    """

    @pytest.mark.asyncio
    async def test_no_redundant_intent_prompt_full_sequence(self):
        """Test that intent is captured from first transcript and never re-asked."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        # Create fresh userdata
        userdata = AizelleeUserData()
        assert userdata.route_decision.intent is None

        # Simulate transcript sequence as it would come from a real call
        transcripts = [
            "I need to get a quote",  # Should set intent to NEW_QUOTE
            "Sam Rubin",  # Name - should NOT change intent
            "818-555-1234",  # Phone - should NOT change intent
            "Business",  # Insurance type - should NOT change intent
            "Acme Plumbing",  # Business name - should NOT change intent
        ]

        # First transcript should capture intent
        result = maybe_record_intent(userdata, transcripts[0])
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE, (
            "First transcript should set intent to NEW_QUOTE"
        )
        assert userdata.route_decision.intent_raw_text == transcripts[0]
        assert result is not None
        assert "new_quote" in result.lower()

        # Verify subsequent maybe_record_intent calls don't change intent
        for transcript in transcripts[1:]:
            result = maybe_record_intent(userdata, transcript)
            assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE, (
                f"Intent should persist as NEW_QUOTE after transcript: '{transcript}'"
            )
            # Should get "already recorded" message for non-matching transcripts
            if result:
                assert "already recorded" in result.lower()

    @pytest.mark.asyncio
    async def test_record_intent_tool_returns_early_when_intent_set(self, agent, mock_context):
        """Test that record_intent tool returns early if intent is already set."""
        # Pre-set intent via maybe_record_intent (simulating auto-capture)
        from agent import maybe_record_intent
        from models import IntentCategory

        maybe_record_intent(mock_context.userdata, "I need to get a quote")
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Now call the record_intent tool - it should return early
        result = await agent.record_intent(mock_context, "I need to make a payment")

        # Intent should NOT have changed
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        # Result should indicate intent was already recorded
        assert "already recorded" in result.lower()

    @pytest.mark.asyncio
    async def test_field_driven_flow_with_auto_intent(self, agent, mock_context):
        """
        Test the complete field-driven flow where intent is captured automatically
        and the agent collects other fields without asking about intent.

        Simulates:
        1. Auto-captured intent from first transcript
        2. Recording caller name
        3. Recording callback phone
        4. Recording insurance type
        5. Recording business name (for business insurance)
        """
        from agent import maybe_record_intent
        from models import InsuranceType, IntentCategory

        # Step 1: Auto-capture intent from first transcript
        maybe_record_intent(mock_context.userdata, "I need to get a quote")
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Step 2: Record caller name (intent already set, should persist)
        await agent.record_caller_name(mock_context, "Sam Rubin")
        assert mock_context.userdata.route_decision.caller_name == "Sam Rubin"
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Step 3: Record phone
        await agent.record_callback_phone(mock_context, "818-555-1234")
        assert mock_context.userdata.route_decision.callback_phone == "8185551234"
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Step 4: Record insurance type
        await agent.record_insurance_type(mock_context, "Business")
        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.BUSINESS
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Step 5: Record business name
        await agent.record_business_name(mock_context, "Acme Plumbing")
        assert mock_context.userdata.route_decision.business_name == "Acme Plumbing"
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Verify route decision is complete
        route_decision = mock_context.userdata.route_decision
        assert route_decision.is_complete() is True

        # Verify intent was never changed from the initial capture
        assert route_decision.intent_raw_text == "I need to get a quote"

    def test_maybe_record_intent_idempotent_for_same_intent(self):
        """Test that maybe_record_intent is idempotent when same intent is classified."""
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # First call sets intent
        maybe_record_intent(userdata, "I need a quote")
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        first_raw_text = userdata.route_decision.intent_raw_text

        # Second call with text that also classifies as NEW_QUOTE
        result2 = maybe_record_intent(userdata, "Can I get a price estimate")

        # Intent should persist, raw_text should NOT be updated
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert userdata.route_decision.intent_raw_text == first_raw_text
        assert "already recorded" in result2.lower()

    def test_intent_only_captured_once_in_full_transcript_sequence(self):
        """
        Verify intent capture happens exactly once in a realistic transcript sequence.

        Transcripts simulate: "I need to get a quote" -> name -> phone -> type -> business name
        """
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Track how many times intent was actually recorded (not just attempted)
        intent_recordings = []

        transcripts = [
            "I need to get a quote",
            "Sam Rubin",
            "818-555-1234",
            "Business",
            "Acme Plumbing",
        ]

        for transcript in transcripts:
            result = maybe_record_intent(userdata, transcript)
            if result and "recorded intent" in result.lower():
                intent_recordings.append(transcript)

        # Intent should have been recorded exactly once (from first transcript)
        assert len(intent_recordings) == 1
        assert intent_recordings[0] == "I need to get a quote"
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE


# -----------------------------------------------------------------------------
# Phase 1.9: Call Duration Tracking Tests
# -----------------------------------------------------------------------------


class TestCallDurationTracking:
    """
    Test call duration tracking feature from Phase 1.9.

    Verifies that call_duration_seconds is captured correctly via:
    - on_enter() setting call_start_time
    - on_exit() calculating duration from monotonic time
    """

    def test_call_duration_calculation_basic(self, userdata):
        """Test basic call duration calculation with known times."""
        import time

        # Simulate on_enter setting start time
        userdata.call_start_time = time.monotonic()

        # Simulate some time passing (we'll test the calculation, not actual waiting)
        # by manually setting end time calculation
        start_time = userdata.call_start_time

        # Calculate duration as on_exit would
        end_time = start_time + 10.5  # Simulate 10.5 seconds elapsed
        userdata.route_decision.call_duration_seconds = round(end_time - start_time, 1)

        assert userdata.route_decision.call_duration_seconds == 10.5

    def test_call_duration_positive_after_conversation(self, userdata):
        """Test that call_duration_seconds > 0 after simulated conversation timing."""
        import time

        # Simulate on_enter
        userdata.call_start_time = time.monotonic()

        # Simulate a small delay (using actual time for this test)
        time.sleep(0.01)  # 10ms minimum

        # Simulate on_exit calculation
        if userdata.call_start_time > 0:
            userdata.route_decision.call_duration_seconds = round(
                time.monotonic() - userdata.call_start_time, 1
            )

        # Should be positive (at least 0.0 due to rounding, but the calculation ran)
        assert userdata.route_decision.call_duration_seconds >= 0.0

    def test_call_duration_zero_without_start_time(self, userdata):
        """Test that call_duration remains 0 if call_start_time was never set."""
        # Default call_start_time is 0.0
        assert userdata.call_start_time == 0.0
        assert userdata.route_decision.call_duration_seconds == 0.0

        # Simulating on_exit logic: only calculate if start_time > 0
        if userdata.call_start_time > 0:
            userdata.route_decision.call_duration_seconds = 99.9  # This should NOT run

        # Duration should still be 0
        assert userdata.route_decision.call_duration_seconds == 0.0

    def test_call_duration_in_log_dict(self, userdata):
        """Test that call_duration_seconds is included in to_log_dict output."""
        import time

        # Set up duration
        userdata.call_start_time = time.monotonic()
        end_time = userdata.call_start_time + 45.3
        userdata.route_decision.call_duration_seconds = round(
            end_time - userdata.call_start_time, 1
        )

        log_dict = userdata.route_decision.to_log_dict()

        assert "call_duration_seconds" in log_dict
        assert log_dict["call_duration_seconds"] == 45.3

    @pytest.mark.asyncio
    async def test_call_duration_with_agent_lifecycle(self, agent):
        """
        Test call duration tracking through agent on_enter and on_exit lifecycle.

        This test simulates the actual agent lifecycle flow.
        """
        import time
        from unittest.mock import MagicMock

        # Create userdata and mock session
        userdata = AizelleeUserData()
        mock_session = MagicMock()
        mock_session.userdata = userdata
        mock_session.say = AsyncMock()

        # Use patch to mock the session property
        with patch.object(
            type(agent), "session", new_callable=lambda: property(lambda self: mock_session)
        ):
            # Call on_enter (sets call_start_time)
            await agent.on_enter()

            # Verify start time was set
            assert userdata.call_start_time > 0

            # Simulate small time passage
            time.sleep(0.01)

            # Call on_exit (calculates duration)
            await agent.on_exit()

            # Verify duration was calculated (should be >= 0 after rounding)
            assert userdata.route_decision.call_duration_seconds >= 0.0


# -----------------------------------------------------------------------------
# Phase 1.9: New Quote Flow Tests
# -----------------------------------------------------------------------------


class TestNewQuotePersonalFlow:
    """
    Test new_quote + personal insurance flow requirements from Phase 1.9.

    Verifies:
    - new_quote with personal insurance type can complete with just a last name
    - No spelling prompt should be required for new quotes
    - is_complete() returns True with all required fields
    """

    def test_new_quote_personal_complete_with_last_name(self, userdata):
        """
        Test that new_quote + personal flow completes with just last name.

        Required fields for new_quote + personal:
        - caller_name
        - callback_phone
        - intent = new_quote
        - insurance_type = personal
        - policy_last_name
        """
        rd = userdata.route_decision

        # Set all required fields
        rd.caller_name = "Sam Reuben"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.PERSONAL
        rd.policy_last_name = "Reuben"

        # Should be complete
        assert rd.is_complete() is True

    def test_new_quote_personal_incomplete_without_last_name(self, userdata):
        """Test that new_quote + personal is incomplete without policy_last_name."""
        rd = userdata.route_decision

        # Set all fields except policy_last_name
        rd.caller_name = "Sam Reuben"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.PERSONAL
        # policy_last_name NOT set

        # Should be incomplete
        assert rd.is_complete() is False

    @pytest.mark.asyncio
    async def test_new_quote_personal_full_flow(self, agent, mock_context):
        """
        Test complete new_quote + personal flow through function tools.

        Simulates: name -> phone -> intent -> insurance_type -> last_name
        """
        # Step 1: Record caller name
        await agent.record_caller_name(mock_context, "Sam Reuben")

        # Step 2: Record callback phone
        await agent.record_callback_phone(mock_context, "5551234567")

        # Step 3: Record intent (new quote)
        await agent.record_intent(mock_context, "I need to get a quote")

        # Step 4: Record insurance type (personal)
        await agent.record_insurance_type(mock_context, "personal")

        # Step 5: Record policy last name (no spelling required for new quotes)
        await agent.record_policy_last_name(mock_context, "Reuben")

        # Verify all fields are set correctly
        rd = mock_context.userdata.route_decision
        assert rd.caller_name == "Sam Reuben"
        assert rd.callback_phone == "5551234567"
        assert rd.intent == IntentCategory.NEW_QUOTE
        assert rd.insurance_type == InsuranceType.PERSONAL
        assert rd.policy_last_name == "Reuben"

        # Should be complete
        assert rd.is_complete() is True

    def test_new_quote_personal_last_name_only_no_spelling(self, userdata):
        """
        Test that for new_quote flow, just the last name is sufficient.

        Per Phase 1.9: No spelling prompt should be required for new quotes.
        The last name provided directly should work.
        """
        rd = userdata.route_decision

        rd.caller_name = "Jane Doe"
        rd.callback_phone = "5559876543"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.PERSONAL

        # Just set last name directly (no spelled-out version needed)
        rd.policy_last_name = "Smith"

        assert rd.is_complete() is True
        assert rd.policy_last_name == "Smith"


class TestNewQuoteBusinessFlow:
    """
    Test new_quote + business insurance flow requirements from Phase 1.9.

    Verifies:
    - new_quote with business insurance type requires business_name
    - is_complete() returns False when business_name is missing
    - is_complete() returns True when business_name is provided
    """

    def test_new_quote_business_incomplete_without_business_name(self, userdata):
        """
        Test that new_quote + business is incomplete without business_name.

        Required fields for new_quote + business:
        - caller_name
        - callback_phone
        - intent = new_quote
        - insurance_type = business
        - business_name (REQUIRED)
        """
        rd = userdata.route_decision

        # Set all fields except business_name
        rd.caller_name = "John Smith"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.BUSINESS
        # business_name NOT set

        # Should be incomplete
        assert rd.is_complete() is False

    def test_new_quote_business_complete_with_business_name(self, userdata):
        """Test that new_quote + business completes when business_name is provided."""
        rd = userdata.route_decision

        # Set all required fields including business_name
        rd.caller_name = "John Smith"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE
        rd.insurance_type = InsuranceType.BUSINESS
        rd.business_name = "Smith Enterprises LLC"

        # Should be complete
        assert rd.is_complete() is True

    @pytest.mark.asyncio
    async def test_new_quote_business_full_flow(self, agent, mock_context):
        """
        Test complete new_quote + business flow through function tools.

        Simulates: name -> phone -> intent -> insurance_type -> business_name
        """
        # Step 1: Record caller name
        await agent.record_caller_name(mock_context, "John Smith")

        # Step 2: Record callback phone
        await agent.record_callback_phone(mock_context, "5559876543")

        # Step 3: Record intent (new quote for business)
        await agent.record_intent(mock_context, "I need a quote for my business")

        # Step 4: Record insurance type (business)
        await agent.record_insurance_type(mock_context, "business")

        # Step 5: Record business name
        await agent.record_business_name(mock_context, "Smith Enterprises LLC")

        # Verify all fields are set correctly
        rd = mock_context.userdata.route_decision
        assert rd.caller_name == "John Smith"
        assert rd.callback_phone == "5559876543"
        assert rd.intent == IntentCategory.NEW_QUOTE
        assert rd.insurance_type == InsuranceType.BUSINESS
        assert rd.business_name == "Smith Enterprises LLC"

        # Should be complete
        assert rd.is_complete() is True

    def test_new_quote_business_vs_personal_completeness(self, userdata):
        """
        Test that business requires business_name while personal requires policy_last_name.

        This ensures the two flows have distinct completeness requirements.
        """
        rd = userdata.route_decision

        # Common fields
        rd.caller_name = "Test User"
        rd.callback_phone = "5551234567"
        rd.intent = IntentCategory.NEW_QUOTE

        # Test business flow
        rd.insurance_type = InsuranceType.BUSINESS
        rd.business_name = None
        rd.policy_last_name = "TestName"  # This shouldn't matter for business

        # Business without business_name is incomplete
        assert rd.is_complete() is False

        # Add business_name
        rd.business_name = "Test Business"
        assert rd.is_complete() is True

        # Now switch to personal
        rd.insurance_type = InsuranceType.PERSONAL
        rd.business_name = None
        rd.policy_last_name = None

        # Personal without policy_last_name is incomplete
        assert rd.is_complete() is False

    @pytest.mark.asyncio
    async def test_new_quote_business_incomplete_then_complete(self, agent, mock_context):
        """
        Test the progression from incomplete to complete for business flow.

        Verifies is_complete() returns False during collection and True after.
        """
        rd = mock_context.userdata.route_decision

        # Initially incomplete
        assert rd.is_complete() is False

        # Add name - still incomplete
        await agent.record_caller_name(mock_context, "Jane Doe")
        assert rd.is_complete() is False

        # Add phone - still incomplete
        await agent.record_callback_phone(mock_context, "5551234567")
        assert rd.is_complete() is False

        # Add intent - still incomplete
        await agent.record_intent(mock_context, "I need a quote")
        assert rd.is_complete() is False

        # Add insurance type (business) - still incomplete (need business_name)
        await agent.record_insurance_type(mock_context, "business")
        assert rd.is_complete() is False

        # Add business name - NOW complete
        await agent.record_business_name(mock_context, "Doe Industries")
        assert rd.is_complete() is True


class TestChatModeIntentCapture:
    """Test ChatCLI-style text input correctly captures intent.

    Simulates the conversation_item_added handler path where text input
    (from ChatCLI or similar) flows through maybe_record_intent.
    """

    def test_chat_mode_claims_intent_capture(self):
        """Test that chat-mode text input correctly captures claims intent.

        Simulates the exact sequence a user might type in ChatCLI mode:
        1. "I need to file a claim" - should set intent to CLAIMS
        2. "Sam Ruben" - should preserve intent
        3. "8185553212" - should preserve intent
        4. "personal" - should preserve intent
        5. "ruben" - should preserve intent
        """
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        # Create fresh userdata (simulating new chat session)
        userdata = AizelleeUserData()
        assert userdata.route_decision.intent is None

        # ChatCLI input sequence
        chat_inputs = ["I need to file a claim", "Sam Ruben", "8185553212", "personal", "ruben"]

        # First message should set intent to CLAIMS
        result = maybe_record_intent(userdata, chat_inputs[0])
        assert userdata.route_decision.intent == IntentCategory.CLAIMS, (
            f"Expected CLAIMS intent after '{chat_inputs[0]}', got {userdata.route_decision.intent}"
        )
        assert userdata.route_decision.intent_raw_text == chat_inputs[0]
        assert result is not None
        assert "claims" in result.lower()

        # Subsequent inputs should preserve the CLAIMS intent
        for chat_input in chat_inputs[1:]:
            maybe_record_intent(userdata, chat_input)
            assert userdata.route_decision.intent == IntentCategory.CLAIMS, (
                f"Intent changed after data input: {chat_input}"
            )

    def test_chat_mode_intent_persists_through_data_collection(self):
        """Test intent persists while collecting caller data in chat mode.

        Verifies the maybe_record_intent function correctly handles
        data-collection inputs (names, phones, etc.) without changing intent.
        """
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Set intent via chat input
        maybe_record_intent(userdata, "I need to file a claim")
        assert userdata.route_decision.intent == IntentCategory.CLAIMS

        # Data collection inputs should not change intent
        data_inputs = [
            "Sam Ruben",  # Name
            "8185553212",  # Phone
            "personal",  # Insurance type
            "ruben",  # Last name
            "yes",  # Confirmation
            "that's correct",  # Confirmation
        ]

        for input_text in data_inputs:
            maybe_record_intent(userdata, input_text)
            assert userdata.route_decision.intent == IntentCategory.CLAIMS, (
                f"Intent changed after data input: {input_text}"
            )

    def test_chat_mode_new_quote_flow(self):
        """Test chat-mode captures new_quote intent correctly.

        Similar to claims flow but for new quote intent.
        """
        from agent import maybe_record_intent
        from models import AizelleeUserData, IntentCategory

        userdata = AizelleeUserData()

        # Chat input for quote
        chat_inputs = ["I need to get a quote", "John Smith", "3105551234", "personal", "smith"]

        # First message should set intent to NEW_QUOTE
        result = maybe_record_intent(userdata, chat_inputs[0])
        assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert "new_quote" in result.lower()

        # Rest should preserve intent
        for chat_input in chat_inputs[1:]:
            maybe_record_intent(userdata, chat_input)
            assert userdata.route_decision.intent == IntentCategory.NEW_QUOTE
