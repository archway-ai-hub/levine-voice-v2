"""
Unit tests for RouteDecision capture through function tools.

Tests the complete flow of capturing caller information via function tools:
- Phone number normalization
- Function tool invocation with mock contexts
- Complete conversation simulation
- Final RouteDecision validation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass, field

# Import the models and agent components we need to test
from models import (
    AizelleeUserData,
    RouteDecision,
    IntentCategory,
    InsuranceType,
    ConversationState,
)
from agent import AizelleeAgent, normalize_phone_number


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
        result = await agent.record_callback_phone(mock_context, "five five five one two three four five six seven")

        assert mock_context.userdata.route_decision.callback_phone == "5551234567"

    @pytest.mark.asyncio
    async def test_record_intent_new_quote(self, agent, mock_context):
        """Test record_intent with new_quote intent using raw_text only."""
        result = await agent.record_intent(
            mock_context,
            "I need to get a quote"
        )

        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE
        assert mock_context.userdata.route_decision.intent_raw_text == "I need to get a quote"

    @pytest.mark.asyncio
    async def test_record_intent_payment_id_card(self, agent, mock_context):
        """Test record_intent with 'I need my ID card' maps to PAYMENT_OR_ID_DEC."""
        result = await agent.record_intent(
            mock_context,
            "I need my ID card"
        )

        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

    @pytest.mark.asyncio
    async def test_record_intent_classifies_from_raw_text(self, agent, mock_context):
        """Test record_intent uses classify_intent internally."""
        result = await agent.record_intent(
            mock_context,
            "I want to cancel my policy"
        )

        assert mock_context.userdata.route_decision.intent == IntentCategory.CANCELLATION

    @pytest.mark.asyncio
    async def test_record_intent_unknown_falls_back_to_something_else(self, agent, mock_context):
        """Test record_intent with unrecognized text falls back to SOMETHING_ELSE."""
        result = await agent.record_intent(
            mock_context,
            "Some random request that doesn't match anything"
        )

        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

    @pytest.mark.asyncio
    async def test_record_insurance_type_personal(self, agent, mock_context):
        """Test record_insurance_type with personal."""
        result = await agent.record_insurance_type(mock_context, "personal")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL

    @pytest.mark.asyncio
    async def test_record_insurance_type_business(self, agent, mock_context):
        """Test record_insurance_type with business."""
        result = await agent.record_insurance_type(mock_context, "business")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.BUSINESS

    @pytest.mark.asyncio
    async def test_record_insurance_type_case_insensitive(self, agent, mock_context):
        """Test record_insurance_type handles case variations."""
        result = await agent.record_insurance_type(mock_context, "PERSONAL")

        assert mock_context.userdata.route_decision.insurance_type == InsuranceType.PERSONAL

    @pytest.mark.asyncio
    async def test_record_business_name(self, agent, mock_context):
        """Test record_business_name captures business name."""
        result = await agent.record_business_name(mock_context, "Acme Corporation")

        assert mock_context.userdata.route_decision.business_name == "Acme Corporation"

    @pytest.mark.asyncio
    async def test_record_policy_last_name(self, agent, mock_context):
        """Test record_policy_last_name captures last name."""
        result = await agent.record_policy_last_name(mock_context, "Reuben")

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
        assert route_decision.caller_name == "Sam Reuben", \
            f"Expected caller_name 'Sam Reuben', got '{route_decision.caller_name}'"

        assert route_decision.callback_phone == "5551234567", \
            f"Expected callback_phone '5551234567', got '{route_decision.callback_phone}'"

        assert route_decision.intent == IntentCategory.NEW_QUOTE, \
            f"Expected intent NEW_QUOTE, got {route_decision.intent}"

        assert route_decision.insurance_type == InsuranceType.PERSONAL, \
            f"Expected insurance_type PERSONAL, got {route_decision.insurance_type}"

        assert route_decision.policy_last_name == "Reuben", \
            f"Expected policy_last_name 'Reuben', got '{route_decision.policy_last_name}'"

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

            assert mock_context.userdata.route_decision.intent == expected_enum, \
                f"Raw text '{raw_text}' should classify to {expected_enum}"


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
    """Test that intent persists and is not overwritten on subsequent calls unless explicit change."""

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

    @pytest.mark.asyncio
    async def test_intent_change_with_actually_signal(self, agent, mock_context):
        """Test that 'actually I'm calling about a claim' DOES change intent."""
        # First set intent to NEW_QUOTE
        await agent.record_intent(mock_context, "I need to get a quote")
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

        # Caller changes their mind with "actually"
        await agent.record_intent(mock_context, "Actually I'm calling about a claim")
        
        # Intent should now be CLAIMS
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS

    @pytest.mark.asyncio
    async def test_intent_change_with_never_mind_signal(self, agent, mock_context):
        """Test that 'never mind' signal allows intent change."""
        # First set intent
        await agent.record_intent(mock_context, "I need my ID card")
        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC

        # Caller changes with "never mind"
        await agent.record_intent(mock_context, "Never mind, I need a quote instead")
        
        # Intent should change to NEW_QUOTE
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE

    @pytest.mark.asyncio
    async def test_intent_change_with_instead_signal(self, agent, mock_context):
        """Test that 'instead' signal allows intent change."""
        # First set intent
        await agent.record_intent(mock_context, "What are your hours?")
        assert mock_context.userdata.route_decision.intent == IntentCategory.HOURS_LOCATION

        # Caller changes with "instead"
        await agent.record_intent(mock_context, "Instead I want to file a claim")
        
        # Intent should change to CLAIMS
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS

    @pytest.mark.asyncio
    async def test_intent_change_with_no_wait_signal(self, agent, mock_context):
        """Test that 'no wait' signal allows intent change."""
        # First set intent
        await agent.record_intent(mock_context, "I need a certificate of insurance")
        assert mock_context.userdata.route_decision.intent == IntentCategory.CERTIFICATES

        # Caller changes with "no wait" - use "add a vehicle" which maps to MAKE_CHANGE
        await agent.record_intent(mock_context, "No wait, I want to add a vehicle")
        
        # Intent should change to MAKE_CHANGE
        assert mock_context.userdata.route_decision.intent == IntentCategory.MAKE_CHANGE

    @pytest.mark.asyncio
    async def test_upgrade_from_something_else_allowed(self, agent, mock_context):
        """Test that upgrading from SOMETHING_ELSE to specific intent is allowed."""
        # First call with vague text that classifies as SOMETHING_ELSE
        await agent.record_intent(mock_context, "Hello, I'm calling today")
        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Second call with specific intent should upgrade (not require change signal)
        await agent.record_intent(mock_context, "I need to get a quote")
        
        # Should upgrade to NEW_QUOTE
        assert mock_context.userdata.route_decision.intent == IntentCategory.NEW_QUOTE


# -----------------------------------------------------------------------------
# Multi-Turn Intent Clarification Tests
# -----------------------------------------------------------------------------


class TestMultiTurnIntentClarification:
    """Test multi-turn sequences where intent becomes clear over time."""

    @pytest.mark.asyncio
    async def test_intent_unclear_then_becomes_clear(self, agent, mock_context):
        """Test multi-turn where intent is initially unclear then becomes clear."""
        # Turn 1: Vague opening - classifies as SOMETHING_ELSE
        await agent.record_intent(mock_context, "Hi, I'm calling about my policy")
        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 2: Still vague
        await agent.record_intent(mock_context, "Yes, I have a question")
        # Should still be SOMETHING_ELSE (no upgrade to another SOMETHING_ELSE)
        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 3: Now clear - should upgrade from SOMETHING_ELSE
        await agent.record_intent(mock_context, "I was in an accident and need to file a claim")
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS

    @pytest.mark.asyncio
    async def test_gradual_clarification_to_new_quote(self, agent, mock_context):
        """Test gradual clarification leading to coverage_questions intent."""
        # Turn 1: Initial vague statement - uses text that truly classifies as SOMETHING_ELSE
        await agent.record_intent(mock_context, "Hello, I have a question")
        assert mock_context.userdata.route_decision.intent == IntentCategory.SOMETHING_ELSE

        # Turn 2: More specific - "coverage" keyword triggers COVERAGE_QUESTIONS
        await agent.record_intent(mock_context, "It's about my coverage")
        # Should upgrade from SOMETHING_ELSE to COVERAGE_QUESTIONS
        assert mock_context.userdata.route_decision.intent == IntentCategory.COVERAGE_QUESTIONS

        # Turn 3: Now tries to change without signal - should persist
        await agent.record_intent(mock_context, "I need a quote")
        # Should still be COVERAGE_QUESTIONS (no change signal)
        assert mock_context.userdata.route_decision.intent == IntentCategory.COVERAGE_QUESTIONS

    @pytest.mark.asyncio
    async def test_complete_multi_turn_flow_with_intent_change(self, agent, mock_context):
        """Test complete multi-turn flow including intent change."""
        # Collect name first
        await agent.record_caller_name(mock_context, "Jane Doe")
        
        # Collect phone
        await agent.record_callback_phone(mock_context, "555-987-6543")
        
        # Turn 1: Initial intent
        await agent.record_intent(mock_context, "I need to make a payment")
        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC
        
        # Turn 2: Agent asks clarifying question, caller responds with same intent
        await agent.record_intent(mock_context, "Yes, I want to pay my bill")
        # Should persist as PAYMENT_OR_ID_DEC
        assert mock_context.userdata.route_decision.intent == IntentCategory.PAYMENT_OR_ID_DEC
        
        # Turn 3: Caller changes their mind with explicit signal
        await agent.record_intent(mock_context, "Actually, I also need to report a claim")
        # Should change to CLAIMS
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS
        
        # Verify other collected data is preserved
        assert mock_context.userdata.route_decision.caller_name == "Jane Doe"
        assert mock_context.userdata.route_decision.callback_phone == "5559876543"

    @pytest.mark.asyncio
    async def test_intent_raw_text_updates_on_change(self, agent, mock_context):
        """Test that intent_raw_text is updated when intent changes."""
        # First intent
        await agent.record_intent(mock_context, "I need a quote")
        assert mock_context.userdata.route_decision.intent_raw_text == "I need a quote"
        
        # Change intent with signal
        await agent.record_intent(mock_context, "Actually I need to file a claim")
        
        # Both intent and raw_text should be updated
        assert mock_context.userdata.route_decision.intent == IntentCategory.CLAIMS
        assert mock_context.userdata.route_decision.intent_raw_text == "Actually I need to file a claim"

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
