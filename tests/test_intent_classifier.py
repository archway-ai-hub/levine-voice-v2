"""
Unit tests for the intent classifier function.

Tests the classify_intent function which maps user input to one of 12 intent categories.
"""

import pytest

from models import classify_intent


class TestClassifyIntent:
    """Tests for the classify_intent function."""

    # --- Test each intent category ---

    def test_new_quote_intent(self):
        """Test new_quote intent is detected."""
        assert classify_intent("I need a quote for car insurance") == "new_quote"

    def test_new_quote_intent_alternate_phrasing(self):
        """Test 'I need to get a quote.' maps to new_quote."""
        assert classify_intent("I need to get a quote.") == "new_quote"

    def test_payment_or_id_dec_intent(self):
        """Test payment_or_id_dec intent is detected."""
        assert classify_intent("I need to make a payment") == "payment_or_id_dec"

    def test_payment_or_id_dec_intent_id_card(self):
        """Test 'I need my ID card' maps to payment_or_id_dec."""
        assert classify_intent("I need my ID card") == "payment_or_id_dec"

    def test_make_change_intent(self):
        """Test make_change intent is detected."""
        assert classify_intent("I want to add a vehicle to my policy") == "make_change"

    def test_cancellation_intent(self):
        """Test cancellation intent is detected."""
        assert classify_intent("I want to cancel my policy") == "cancellation"

    def test_coverage_questions_intent(self):
        """Test coverage_questions intent is detected."""
        assert classify_intent("Is my roof covered under my policy?") == "coverage_questions"

    def test_annual_review_intent(self):
        """Test annual_review intent is detected."""
        assert classify_intent("I'd like to review my policy for discounts") == "annual_review"

    def test_mortgagee_lienholder_intent(self):
        """Test mortgagee_lienholder intent is detected."""
        assert classify_intent("I need to update my mortgage company") == "mortgagee_lienholder"

    def test_certificates_intent(self):
        """Test certificates intent is detected."""
        assert classify_intent("I need a certificate of insurance") == "certificates"

    def test_claims_intent(self):
        """Test claims intent is detected."""
        assert classify_intent("I was in an accident and need to file a claim") == "claims"

    def test_hours_location_intent(self):
        """Test hours_location intent is detected."""
        assert classify_intent("What are your office hours?") == "hours_location"

    def test_specific_agent_intent(self):
        """Test specific_agent intent is detected."""
        assert classify_intent("I'm looking for John Smith, is he there?") == "specific_agent"

    def test_something_else_fallback(self):
        """Test something_else is returned for unknown input."""
        assert classify_intent("Random gibberish that matches nothing") == "something_else"

    # --- Test case insensitivity ---

    def test_case_insensitivity_uppercase(self):
        """Test classifier handles uppercase input."""
        assert classify_intent("I NEED A QUOTE") == "new_quote"

    def test_case_insensitivity_mixed_case(self):
        """Test classifier handles mixed case input."""
        assert classify_intent("I Want To CANCEL My Policy") == "cancellation"

    # --- Edge cases ---

    def test_empty_string_returns_something_else(self):
        """Test empty string returns something_else."""
        assert classify_intent("") == "something_else"

    def test_whitespace_only_returns_something_else(self):
        """Test whitespace-only input returns something_else."""
        assert classify_intent("   ") == "something_else"

    def test_input_with_extra_whitespace(self):
        """Test input with leading/trailing whitespace is handled."""
        assert classify_intent("  I need a quote  ") == "new_quote"


class TestIntentKeywordVariations:
    """Test various keyword variations for each intent."""

    def test_new_quote_variations(self):
        """Test multiple keywords that should map to new_quote."""
        assert classify_intent("how much for auto insurance") == "new_quote"
        assert classify_intent("can i get an estimate") == "new_quote"
        assert classify_intent("need a new policy") == "new_quote"

    def test_payment_variations(self):
        """Test multiple keywords that should map to payment_or_id_dec."""
        assert classify_intent("i need my id card") == "payment_or_id_dec"
        assert classify_intent("can you send me my insurance card") == "payment_or_id_dec"
        assert classify_intent("i need my declaration page") == "payment_or_id_dec"

    def test_claims_variations(self):
        """Test multiple keywords that should map to claims."""
        assert classify_intent("there was damage to my car") == "claims"
        assert classify_intent("i had an incident") == "claims"
        assert classify_intent("i need to report an accident") == "claims"

    def test_hours_location_variations(self):
        """Test multiple keywords that should map to hours_location."""
        assert classify_intent("when are you open") == "hours_location"
        assert classify_intent("what is your address") == "hours_location"
        assert classify_intent("how do i get directions to your office") == "hours_location"
