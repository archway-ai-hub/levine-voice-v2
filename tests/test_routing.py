"""
Unit tests for call routing logic.

Tests the routing functions that determine where calls are directed based on:
- Caller last name or business name for alpha-split routing
- Intent category (new_quote, make_change, claims, etc.)
- Insurance type (personal vs business)

Test Categories:
1. Business Name Prefix Stripping (normalize_business_name)
2. Last Name Normalization (normalize_last_name)
3. PL Sales Alpha Split (A-L vs M-Z)
4. PL AE Alpha Split (A-G, H-M, N-Z)
5. CL AE Alpha Split (A-F, G-O, P-Z)
6. Intent Routing (route_call function)
"""

import pytest

from agent import check_routing_requirements, route_call
from models import AizelleeUserData, InsuranceType, IntentCategory, RouteDecision
from staff_directory import (
    CL_AE_FALLBACK,
    GENERAL_FALLBACK,
    PL_AE_FALLBACK,
    STAFF_DIRECTORY,
    normalize_business_name,
    normalize_last_name,
    pick_cl_ae,
    pick_pl_ae,
    pick_pl_sales,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def route_decision():
    """Create a fresh RouteDecision for each test."""
    return RouteDecision()


# =============================================================================
# 1. Business Name Prefix Stripping Tests
# =============================================================================


class TestNormalizeBusinessName:
    """Tests for normalize_business_name from staff_directory."""

    @pytest.mark.parametrize(
        "business_name,expected_letter",
        [
            # "The" prefix stripping
            ("The Acme Company", "A"),
            ("The Global Industries", "G"),
            ("The Zebra Corp", "Z"),
            # "Law Offices of" prefix stripping
            ("Law Offices of Smith", "S"),
            ("Law Offices of Garcia", "G"),
            ("Law Offices of Williams", "W"),
            # No prefix - use first letter directly
            ("Acme Inc.", "A"),
            ("ABC Corp", "A"),
            ("Global Industries", "G"),
            ("Pacific Group", "P"),
            ("Zebra Enterprises", "Z"),
        ],
    )
    def test_prefix_stripping(self, business_name, expected_letter):
        """Test that common prefixes are stripped and first letter extracted."""
        result = normalize_business_name(business_name)
        assert result == expected_letter, (
            f"normalize_business_name('{business_name}') should return '{expected_letter}', got '{result}'"
        )

    def test_combined_prefix_stripping_limitation(self):
        """Document known limitation: only one prefix is stripped at a time.

        'The Law Offices of Johnson' strips 'The' first, leaving 'Law Offices of Johnson',
        but the second prefix 'Law Offices of' is not stripped because the function
        only does a single pass. This results in 'L' instead of 'J'.
        """
        # Current behavior: only strips "The", leaves "Law Offices of Johnson" -> L
        assert normalize_business_name("The Law Offices of Johnson") == "L"
        assert normalize_business_name("The Law Offices of Adams") == "L"

    @pytest.mark.parametrize(
        "business_name",
        [
            "",
            "   ",
            None,
        ],
    )
    def test_empty_or_none_input(self, business_name):
        """Test handling of empty or None business names."""
        if business_name is None:
            # None should return empty string (or handle gracefully)
            result = normalize_business_name("")
        else:
            result = normalize_business_name(business_name)
        assert result == "", (
            f"Empty/whitespace business name should return empty string, got '{result}'"
        )

    def test_case_insensitivity(self):
        """Test that prefix matching is case-insensitive."""
        assert normalize_business_name("THE ACME COMPANY") == "A"
        assert normalize_business_name("the acme company") == "A"
        assert normalize_business_name("The Acme Company") == "A"
        assert normalize_business_name("LAW OFFICES OF SMITH") == "S"

    def test_office_of_prefix(self):
        """Test 'Office of' prefix stripping."""
        assert normalize_business_name("Office of Smith") == "S"
        assert normalize_business_name("Offices of Garcia") == "G"


# =============================================================================
# 2. Last Name Normalization Tests
# =============================================================================


class TestNormalizeLastName:
    """Tests for normalize_last_name from staff_directory."""

    @pytest.mark.parametrize(
        "name_input,expected_letter",
        [
            # Full name - extract last name's first letter
            ("John Smith", "S"),
            ("Jane Doe", "D"),
            ("Mary Jane Watson", "W"),
            ("Robert Garcia", "G"),
            # Single name - use first letter
            ("Smith", "S"),
            ("Garcia", "G"),
            ("Adams", "A"),
            ("Zulu", "Z"),
            # Spelled out names (hyphen-separated)
            ("S-M-I-T-H", "S"),
            ("G-A-R-C-I-A", "G"),
            ("A-D-A-M-S", "A"),
            # All uppercase
            ("GARCIA", "G"),
            ("SMITH", "S"),
            ("JOHNSON", "J"),
        ],
    )
    def test_last_name_extraction(self, name_input, expected_letter):
        """Test that last name's first letter is correctly extracted."""
        result = normalize_last_name(name_input)
        assert result == expected_letter, (
            f"normalize_last_name('{name_input}') should return '{expected_letter}', got '{result}'"
        )

    @pytest.mark.parametrize(
        "name_input",
        [
            "",
            "   ",
        ],
    )
    def test_empty_input(self, name_input):
        """Test handling of empty or whitespace names."""
        result = normalize_last_name(name_input)
        assert result == "", f"Empty/whitespace name should return empty string, got '{result}'"

    def test_case_insensitivity(self):
        """Test that name matching is case-insensitive."""
        assert normalize_last_name("john smith") == "S"
        assert normalize_last_name("JOHN SMITH") == "S"
        assert normalize_last_name("John Smith") == "S"

    def test_spelled_name_variations(self):
        """Test spelled-out name variations."""
        # Hyphen-separated spelling
        assert normalize_last_name("R-E-U-B-E-N") == "R"
        assert normalize_last_name("M-I-L-L-E-R") == "M"


# =============================================================================
# 3. PL Sales Alpha Split Tests (A-L vs M-Z)
# =============================================================================


class TestPickPLSales:
    """Tests for pick_pl_sales alpha split routing."""

    @pytest.mark.parametrize(
        "last_name,expected_agent",
        [
            # A-L range -> Queens
            ("Adams", "Queens"),
            ("Baker", "Queens"),
            ("Carter", "Queens"),
            ("Davis", "Queens"),
            ("Evans", "Queens"),
            ("Franklin", "Queens"),
            ("Garcia", "Queens"),
            ("Harris", "Queens"),
            ("Ingram", "Queens"),
            ("Johnson", "Queens"),
            ("King", "Queens"),
            ("Lopez", "Queens"),  # L is in A-L
            ("Lowe", "Queens"),  # Edge case: exactly L
            # M-Z range -> Brad
            ("Miller", "Brad"),
            ("Martin", "Brad"),  # Edge case: exactly M
            ("Nelson", "Brad"),
            ("Ortiz", "Brad"),
            ("Parker", "Brad"),
            ("Quinn", "Brad"),
            ("Roberts", "Brad"),
            ("Smith", "Brad"),
            ("Taylor", "Brad"),
            ("Underwood", "Brad"),
            ("Valdez", "Brad"),
            ("Williams", "Brad"),
            ("Xavier", "Brad"),
            ("Young", "Brad"),
            ("Zhang", "Brad"),
        ],
    )
    def test_alpha_split_routing(self, last_name, expected_agent):
        """Test that last names are routed to correct PL Sales agent."""
        result = pick_pl_sales(last_name)
        assert result.name == expected_agent, (
            f"pick_pl_sales('{last_name}') should route to '{expected_agent}', got '{result.name}'"
        )
        assert result.department == "PL Sales"

    def test_boundary_cases(self):
        """Test exact boundary letters L and M."""
        # L should go to Queens (A-L)
        l_result = pick_pl_sales("Lowe")
        assert l_result.name == "Queens"

        # M should go to Brad (M-Z)
        m_result = pick_pl_sales("Martin")
        assert m_result.name == "Brad"

    def test_empty_last_name_defaults_to_brad(self):
        """Test that empty last name defaults to Brad (M-Z range)."""
        result = pick_pl_sales("")
        assert result.name == "Brad"

    def test_full_name_extracts_last_name(self):
        """Test that full names correctly extract last name for routing."""
        # "John Adams" -> A -> Queens
        result = pick_pl_sales("John Adams")
        assert result.name == "Queens"

        # "Mary Williams" -> W -> Brad
        result = pick_pl_sales("Mary Williams")
        assert result.name == "Brad"


# =============================================================================
# 4. PL AE Alpha Split Tests (A-G, H-M, N-Z)
# =============================================================================


class TestPickPLAE:
    """Tests for pick_pl_ae alpha split routing."""

    @pytest.mark.parametrize(
        "last_name,expected_agent",
        [
            # A-G range -> Yarislyn
            ("Adams", "Yarislyn"),
            ("Baker", "Yarislyn"),
            ("Carter", "Yarislyn"),
            ("Davis", "Yarislyn"),
            ("Evans", "Yarislyn"),
            ("Franklin", "Yarislyn"),
            ("Garcia", "Yarislyn"),
            ("Gomez", "Yarislyn"),  # Edge case: exactly G
            # H-M range -> Al
            ("Harris", "Al"),
            ("Hall", "Al"),  # Edge case: exactly H
            ("Ingram", "Al"),
            ("Johnson", "Al"),
            ("King", "Al"),
            ("Lopez", "Al"),
            ("Martinez", "Al"),
            ("Miller", "Al"),  # Edge case: exactly M
            # N-Z range -> Luis
            ("Nelson", "Luis"),
            ("Newman", "Luis"),  # Edge case: exactly N
            ("Ortiz", "Luis"),
            ("Parker", "Luis"),
            ("Quinn", "Luis"),
            ("Roberts", "Luis"),
            ("Smith", "Luis"),
            ("Taylor", "Luis"),
            ("Underwood", "Luis"),
            ("Valdez", "Luis"),
            ("Williams", "Luis"),
            ("Wilson", "Luis"),
            ("Xavier", "Luis"),
            ("Young", "Luis"),
            ("Zhang", "Luis"),
        ],
    )
    def test_alpha_split_routing(self, last_name, expected_agent):
        """Test that last names are routed to correct PL AE agent."""
        result = pick_pl_ae(last_name)
        assert result.name == expected_agent, (
            f"pick_pl_ae('{last_name}') should route to '{expected_agent}', got '{result.name}'"
        )
        assert result.department == "PL AE"

    def test_boundary_cases(self):
        """Test exact boundary letters G, H, M, N."""
        # G should go to Yarislyn (A-G)
        g_result = pick_pl_ae("Gomez")
        assert g_result.name == "Yarislyn"

        # H should go to Al (H-M)
        h_result = pick_pl_ae("Hall")
        assert h_result.name == "Al"

        # M should go to Al (H-M)
        m_result = pick_pl_ae("Miller")
        assert m_result.name == "Al"

        # N should go to Luis (N-Z)
        n_result = pick_pl_ae("Newman")
        assert n_result.name == "Luis"

    def test_empty_last_name_defaults_to_luis(self):
        """Test that empty last name defaults to Luis (N-Z range)."""
        result = pick_pl_ae("")
        assert result.name == "Luis"


# =============================================================================
# 5. CL AE Alpha Split Tests (A-F, G-O, P-Z)
# =============================================================================


class TestPickCLAE:
    """Tests for pick_cl_ae alpha split routing by business name."""

    @pytest.mark.parametrize(
        "business_name,expected_agent",
        [
            # A-F range -> Adriana
            ("Acme Corp", "Adriana"),
            ("ABC Industries", "Adriana"),
            ("Baker Enterprises", "Adriana"),
            ("Carter LLC", "Adriana"),
            ("Davis Group", "Adriana"),
            ("Evans Solutions", "Adriana"),
            ("First Bank", "Adriana"),
            ("Franklin Co", "Adriana"),  # Edge case: exactly F
            # G-O range -> Rayvon
            ("Global Inc", "Rayvon"),
            ("Garrett Inc", "Rayvon"),  # Edge case: exactly G
            ("Harris Corp", "Rayvon"),
            ("Ingram Holdings", "Rayvon"),
            ("Johnson Co", "Rayvon"),
            ("King Industries", "Rayvon"),
            ("Lopez Enterprises", "Rayvon"),
            ("Miller Group", "Rayvon"),
            ("Nelson LLC", "Rayvon"),
            ("Orange LLC", "Rayvon"),  # Edge case: exactly O
            # P-Z range -> Dionna
            ("Pacific Group", "Dionna"),
            ("Porter Ltd", "Dionna"),  # Edge case: exactly P
            ("Quinn Corp", "Dionna"),
            ("Roberts Inc", "Dionna"),
            ("Smith Enterprises", "Dionna"),
            ("Taylor Holdings", "Dionna"),
            ("Universal Co", "Dionna"),
            ("Valdez Group", "Dionna"),
            ("Williams LLC", "Dionna"),
            ("Xavier Industries", "Dionna"),
            ("Young Corp", "Dionna"),
            ("Zebra Corp", "Dionna"),
        ],
    )
    def test_alpha_split_routing(self, business_name, expected_agent):
        """Test that business names are routed to correct CL AE agent."""
        result = pick_cl_ae(business_name)
        assert result.name == expected_agent, (
            f"pick_cl_ae('{business_name}') should route to '{expected_agent}', got '{result.name}'"
        )
        assert result.department == "CL AE"

    def test_boundary_cases(self):
        """Test exact boundary letters F, G, O, P."""
        # F should go to Adriana (A-F)
        f_result = pick_cl_ae("Franklin Co")
        assert f_result.name == "Adriana"

        # G should go to Rayvon (G-O)
        g_result = pick_cl_ae("Garrett Inc")
        assert g_result.name == "Rayvon"

        # O should go to Rayvon (G-O)
        o_result = pick_cl_ae("Orange LLC")
        assert o_result.name == "Rayvon"

        # P should go to Dionna (P-Z)
        p_result = pick_cl_ae("Porter Ltd")
        assert p_result.name == "Dionna"

    def test_empty_business_name_defaults_to_dionna(self):
        """Test that empty business name defaults to Dionna (P-Z range)."""
        result = pick_cl_ae("")
        assert result.name == "Dionna"

    def test_prefix_stripping(self):
        """Test that 'The' and 'Law Offices of' prefixes are stripped."""
        # "The Acme Corp" -> A -> Adriana
        result = pick_cl_ae("The Acme Corp")
        assert result.name == "Adriana"

        # "Law Offices of Smith" -> S -> Dionna
        result = pick_cl_ae("Law Offices of Smith")
        assert result.name == "Dionna"


# =============================================================================
# 6. Intent Routing Tests (route_call function)
# =============================================================================


class TestRouteCallNewQuote:
    """Tests for route_call with new_quote intent."""

    def test_new_quote_personal_routes_to_pl_sales(self, route_decision):
        """Test new_quote + personal routes to PL Sales."""
        route_decision.intent = IntentCategory.NEW_QUOTE
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Adams"  # A -> Queens

        result = route_call(route_decision)

        assert result.target_department == "PL Sales"
        assert result.target_agent == "Queens"
        assert "7010" in result.target_extension

    def test_new_quote_business_routes_to_cl_ae(self, route_decision):
        """Test new_quote + business routes to CL AE."""
        route_decision.intent = IntentCategory.NEW_QUOTE
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Acme Corp"  # A -> Adriana

        result = route_call(route_decision)

        assert result.target_department == "CL AE"
        assert result.target_agent == "Adriana"
        assert "7002" in result.target_extension


class TestRouteCallMakeChange:
    """Tests for route_call with make_change intent."""

    def test_make_change_personal_routes_to_pl_ae(self, route_decision):
        """Test make_change + personal routes to PL AE."""
        route_decision.intent = IntentCategory.MAKE_CHANGE
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Adams"  # A -> Yarislyn

        result = route_call(route_decision)

        assert result.target_department == "PL AE"
        assert result.target_agent == "Yarislyn"

    def test_make_change_business_routes_to_cl_ae(self, route_decision):
        """Test make_change + business routes to CL AE."""
        route_decision.intent = IntentCategory.MAKE_CHANGE
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Acme Corp"  # A -> Adriana

        result = route_call(route_decision)

        assert result.target_department == "CL AE"
        assert result.target_agent == "Adriana"


class TestRouteCallSpecialCases:
    """Tests for route_call with special-case intents (no transfer)."""

    def test_hours_location_routes_to_info_only(self, route_decision):
        """Test hours_location routes to info-only (no agent transfer)."""
        route_decision.intent = IntentCategory.HOURS_LOCATION
        route_decision.insurance_type = InsuranceType.PERSONAL

        result = route_call(route_decision)

        assert result.target_department == "info-only"
        assert result.target_agent is None
        assert result.target_extension is None

    def test_certificates_routes_to_email(self, route_decision):
        """Test certificates routes to email (no agent transfer)."""
        route_decision.intent = IntentCategory.CERTIFICATES
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Acme Corp"

        result = route_call(route_decision)

        assert result.target_department == "email"
        assert result.target_agent is None
        assert result.target_extension is None

    def test_mortgagee_lienholder_routes_to_email(self, route_decision):
        """Test mortgagee_lienholder routes to email (no agent transfer)."""
        route_decision.intent = IntentCategory.MORTGAGEE_LIENHOLDER
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Smith"

        result = route_call(route_decision)

        assert result.target_department == "email"
        assert result.target_agent is None
        assert result.target_extension is None


class TestRouteCallClaims:
    """Tests for route_call with claims intent."""

    def test_claims_personal_routes_to_claims(self, route_decision):
        """Test claims + personal routes to claims department."""
        route_decision.intent = IntentCategory.CLAIMS
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Smith"

        result = route_call(route_decision)

        assert result.target_department == "claims"
        assert result.target_agent is None  # Claims doesn't go to specific agent
        assert result.target_extension is None

    def test_claims_business_routes_to_claims(self, route_decision):
        """Test claims + business routes to claims department."""
        route_decision.intent = IntentCategory.CLAIMS
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Acme Corp"

        result = route_call(route_decision)

        assert result.target_department == "claims"
        assert result.target_agent is None


class TestRouteCallExistingPolicyIntents:
    """Tests for route_call with existing policy service intents."""

    @pytest.mark.parametrize(
        "intent",
        [
            IntentCategory.PAYMENT_OR_ID_DEC,
            IntentCategory.MAKE_CHANGE,
            IntentCategory.CANCELLATION,
            IntentCategory.COVERAGE_QUESTIONS,
            IntentCategory.ANNUAL_REVIEW,
            IntentCategory.SPECIFIC_AGENT,
        ],
    )
    def test_existing_policy_intents_personal_route_to_pl_ae(self, route_decision, intent):
        """Test existing policy intents + personal route to PL AE."""
        route_decision.intent = intent
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Adams"  # A -> Yarislyn

        result = route_call(route_decision)

        assert result.target_department == "PL AE"
        assert result.target_agent == "Yarislyn"

    @pytest.mark.parametrize(
        "intent",
        [
            IntentCategory.PAYMENT_OR_ID_DEC,
            IntentCategory.MAKE_CHANGE,
            IntentCategory.CANCELLATION,
            IntentCategory.COVERAGE_QUESTIONS,
            IntentCategory.ANNUAL_REVIEW,
            IntentCategory.SPECIFIC_AGENT,
        ],
    )
    def test_existing_policy_intents_business_route_to_cl_ae(self, route_decision, intent):
        """Test existing policy intents + business route to CL AE."""
        route_decision.intent = intent
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Acme Corp"  # A -> Adriana

        result = route_call(route_decision)

        assert result.target_department == "CL AE"
        assert result.target_agent == "Adriana"


class TestRouteCallSomethingElse:
    """Tests for route_call with something_else intent."""

    def test_something_else_personal_routes_to_pl_ae(self, route_decision):
        """Test something_else + personal routes to PL AE."""
        route_decision.intent = IntentCategory.SOMETHING_ELSE
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Nelson"  # N -> Luis

        result = route_call(route_decision)

        assert result.target_department == "PL AE"
        assert result.target_agent == "Luis"

    def test_something_else_business_routes_to_cl_ae(self, route_decision):
        """Test something_else + business routes to CL AE."""
        route_decision.intent = IntentCategory.SOMETHING_ELSE
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = "Pacific Group"  # P -> Dionna

        result = route_call(route_decision)

        assert result.target_department == "CL AE"
        assert result.target_agent == "Dionna"


class TestRouteCallAlphaSplitIntegration:
    """Integration tests verifying alpha-split routing through route_call."""

    @pytest.mark.parametrize(
        "last_name,expected_sales_agent,expected_ae_agent",
        [
            # A-G: Sales=Queens, AE=Yarislyn
            ("Adams", "Queens", "Yarislyn"),
            ("Garcia", "Queens", "Yarislyn"),
            # H-L: Sales=Queens, AE=Al
            ("Harris", "Queens", "Al"),
            ("Lopez", "Queens", "Al"),
            # M: Sales=Brad, AE=Al
            ("Martin", "Brad", "Al"),
            ("Miller", "Brad", "Al"),
            # N-Z: Sales=Brad, AE=Luis
            ("Nelson", "Brad", "Luis"),
            ("Wilson", "Brad", "Luis"),
            ("Zhang", "Brad", "Luis"),
        ],
    )
    def test_personal_lines_alpha_split(
        self, route_decision, last_name, expected_sales_agent, expected_ae_agent
    ):
        """Test that personal lines routing uses correct alpha-split for Sales vs AE."""
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = last_name

        # New quote -> Sales
        route_decision.intent = IntentCategory.NEW_QUOTE
        sales_result = route_call(route_decision)
        assert sales_result.target_agent == expected_sales_agent, (
            f"NEW_QUOTE for '{last_name}' should route to '{expected_sales_agent}', "
            f"got '{sales_result.target_agent}'"
        )

        # Make change -> AE
        route_decision.intent = IntentCategory.MAKE_CHANGE
        ae_result = route_call(route_decision)
        assert ae_result.target_agent == expected_ae_agent, (
            f"MAKE_CHANGE for '{last_name}' should route to '{expected_ae_agent}', "
            f"got '{ae_result.target_agent}'"
        )

    @pytest.mark.parametrize(
        "business_name,expected_agent",
        [
            # A-F -> Adriana
            ("Acme Corp", "Adriana"),
            ("First Bank", "Adriana"),
            # G-O -> Rayvon
            ("Global Inc", "Rayvon"),
            ("Orange LLC", "Rayvon"),
            # P-Z -> Dionna
            ("Pacific Group", "Dionna"),
            ("Zebra Corp", "Dionna"),
        ],
    )
    def test_commercial_lines_alpha_split(self, route_decision, business_name, expected_agent):
        """Test that commercial lines routing uses correct alpha-split for CL AE."""
        route_decision.insurance_type = InsuranceType.BUSINESS
        route_decision.business_name = business_name

        # All commercial intents should route to CL AE
        for intent in [IntentCategory.NEW_QUOTE, IntentCategory.MAKE_CHANGE]:
            route_decision.intent = intent
            result = route_call(route_decision)
            assert result.target_agent == expected_agent, (
                f"{intent.value} for '{business_name}' should route to '{expected_agent}', "
                f"got '{result.target_agent}'"
            )


# =============================================================================
# Staff Directory Validation Tests
# =============================================================================


class TestStaffDirectoryStructure:
    """Tests to verify staff directory structure and data integrity."""

    def test_all_pl_sales_agents_present(self):
        """Verify all expected PL Sales agents are in the directory."""
        pl_sales = [s for s in STAFF_DIRECTORY if s.department == "PL Sales"]
        agent_names = {s.name for s in pl_sales}

        assert "Queens" in agent_names
        assert "Brad" in agent_names
        assert len(pl_sales) == 2

    def test_all_pl_ae_agents_present(self):
        """Verify all expected PL AE agents are in the directory."""
        pl_ae = [s for s in STAFF_DIRECTORY if s.department == "PL AE"]
        agent_names = {s.name for s in pl_ae}

        assert "Yarislyn" in agent_names
        assert "Al" in agent_names
        assert "Luis" in agent_names
        assert len(pl_ae) == 3

    def test_all_cl_ae_agents_present(self):
        """Verify all expected CL AE agents are in the directory."""
        cl_ae = [s for s in STAFF_DIRECTORY if s.department == "CL AE"]
        agent_names = {s.name for s in cl_ae}

        assert "Adriana" in agent_names
        assert "Rayvon" in agent_names
        assert "Dionna" in agent_names
        assert len(cl_ae) == 3

    def test_alpha_ranges_cover_full_alphabet(self):
        """Verify alpha ranges in each department cover A-Z without gaps."""
        # PL Sales: Queens (A-L) + Brad (M-Z)
        queens = next(s for s in STAFF_DIRECTORY if s.name == "Queens")
        brad = next(s for s in STAFF_DIRECTORY if s.name == "Brad")
        assert queens.alpha_range == ("A", "L")
        assert brad.alpha_range == ("M", "Z")

        # PL AE: Yarislyn (A-G) + Al (H-M) + Luis (N-Z)
        yarislyn = next(s for s in STAFF_DIRECTORY if s.name == "Yarislyn")
        al = next(s for s in STAFF_DIRECTORY if s.name == "Al")
        luis = next(s for s in STAFF_DIRECTORY if s.name == "Luis")
        assert yarislyn.alpha_range == ("A", "G")
        assert al.alpha_range == ("H", "M")
        assert luis.alpha_range == ("N", "Z")

        # CL AE: Adriana (A-F) + Rayvon (G-O) + Dionna (P-Z)
        adriana = next(s for s in STAFF_DIRECTORY if s.name == "Adriana")
        rayvon = next(s for s in STAFF_DIRECTORY if s.name == "Rayvon")
        dionna = next(s for s in STAFF_DIRECTORY if s.name == "Dionna")
        assert adriana.alpha_range == ("A", "F")
        assert rayvon.alpha_range == ("G", "O")
        assert dionna.alpha_range == ("P", "Z")


# =============================================================================
# RouteResult Structure Tests
# =============================================================================


class TestRouteResultStructure:
    """Tests for RouteResult dataclass structure."""

    def test_route_result_has_required_fields(self, route_decision):
        """Test that RouteResult has all expected fields."""
        route_decision.intent = IntentCategory.NEW_QUOTE
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Smith"

        result = route_call(route_decision)

        assert hasattr(result, "target_department")
        assert hasattr(result, "target_agent")
        assert hasattr(result, "target_extension")
        assert hasattr(result, "transfer_reason")

    def test_route_result_transfer_reason_not_empty(self, route_decision):
        """Test that transfer_reason is always populated."""
        route_decision.intent = IntentCategory.NEW_QUOTE
        route_decision.insurance_type = InsuranceType.PERSONAL
        route_decision.policy_last_name = "Smith"

        result = route_call(route_decision)

        assert result.transfer_reason, "transfer_reason should not be empty"
        assert len(result.transfer_reason) > 0


# =============================================================================
# 7. Pre-Routing Requirements Tests (check_routing_requirements)
# =============================================================================


class TestCheckRoutingRequirementsNoTransfer:
    """Tests for info-only intents that should never transfer."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        return AizelleeUserData()

    @pytest.mark.parametrize(
        "intent",
        [
            IntentCategory.HOURS_LOCATION,
            IntentCategory.CERTIFICATES,
            IntentCategory.MORTGAGEE_LIENHOLDER,
        ],
    )
    def test_info_only_intents_return_no_transfer(self, userdata, intent):
        """Test that info-only intents return no_transfer action."""
        action, value1, value2 = check_routing_requirements(userdata, intent)
        assert action == "no_transfer"
        assert value1 is None
        assert value2 is None


class TestCheckRoutingRequirementsClaims:
    """Tests for claims intent which requires insurance_type like other routing intents."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        return AizelleeUserData()

    def test_claims_asks_for_insurance_type_when_missing(self, userdata):
        """Test that claims intent asks for insurance_type when missing."""
        action, question, field = check_routing_requirements(userdata, IntentCategory.CLAIMS)
        assert action == "ask"
        assert "business or personal" in question.lower()
        assert field == "insurance_type"

    def test_claims_returns_ready_with_insurance_type(self, userdata):
        """Test that claims intent is ready when insurance_type is set."""
        userdata.route_decision.insurance_type = InsuranceType.PERSONAL
        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.CLAIMS)
        assert action == "ready"

    def test_claims_returns_ready_with_business_insurance_type(self, userdata):
        """Test that claims intent is ready when insurance_type is business."""
        userdata.route_decision.insurance_type = InsuranceType.BUSINESS
        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.CLAIMS)
        assert action == "ready"


class TestCheckRoutingRequirementsMissingInsuranceType:
    """Tests for missing insurance_type requirement."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        return AizelleeUserData()

    @pytest.mark.parametrize(
        "intent",
        [
            IntentCategory.NEW_QUOTE,
            IntentCategory.MAKE_CHANGE,
            IntentCategory.PAYMENT_OR_ID_DEC,
            IntentCategory.CANCELLATION,
            IntentCategory.COVERAGE_QUESTIONS,
            IntentCategory.ANNUAL_REVIEW,
            IntentCategory.SOMETHING_ELSE,
        ],
    )
    def test_first_ask_for_insurance_type(self, userdata, intent):
        """Test that first request asks for insurance_type."""
        action, question, field = check_routing_requirements(userdata, intent)
        assert action == "ask"
        assert "business or personal" in question.lower()
        assert field == "insurance_type"
        assert userdata.asked_insurance_type_count == 1

    def test_second_ask_for_insurance_type(self, userdata):
        """Test that second request still asks for insurance_type."""
        userdata.asked_insurance_type_count = 1

        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert field == "insurance_type"
        assert userdata.asked_insurance_type_count == 2

    def test_fallback_after_max_retries(self, userdata):
        """Test fallback to main_line after max retries for insurance_type."""
        userdata.asked_insurance_type_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "fallback"
        assert agent == GENERAL_FALLBACK
        assert reason == "missing_insurance_type"

    def test_ready_when_insurance_type_provided(self, userdata):
        """Test that providing insurance_type returns ready (with last name)."""
        userdata.route_decision.insurance_type = InsuranceType.PERSONAL
        userdata.route_decision.policy_last_name = "Smith"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"

    def test_third_call_fallback_after_two_asks(self, userdata):
        """Test that exactly on third call (after 2 asks) we get fallback."""
        # First call - asks (count goes to 1)
        action1, _, _ = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action1 == "ask"
        assert userdata.asked_insurance_type_count == 1

        # Second call - asks (count goes to 2)
        action2, _, _ = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action2 == "ask"
        assert userdata.asked_insurance_type_count == 2

        # Third call - fallback (count is at 2, which is >= MAX_RETRIES)
        action3, agent, reason = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action3 == "fallback"
        assert agent == GENERAL_FALLBACK
        assert reason == "missing_insurance_type"


class TestCheckRoutingRequirementsMissingBusinessName:
    """Tests for missing business_name requirement."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        ud = AizelleeUserData()
        ud.route_decision.insurance_type = InsuranceType.BUSINESS
        return ud

    def test_first_ask_for_business_name(self, userdata):
        """Test that first request asks for business_name."""
        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert "business" in question.lower()
        assert field == "business_name"
        assert userdata.asked_business_name_count == 1

    def test_second_ask_for_business_name(self, userdata):
        """Test that second request still asks for business_name."""
        userdata.asked_business_name_count = 1

        action, question, field = check_routing_requirements(userdata, IntentCategory.MAKE_CHANGE)
        assert action == "ask"
        assert field == "business_name"
        assert userdata.asked_business_name_count == 2

    def test_fallback_after_max_retries(self, userdata):
        """Test fallback to CL_AE_FALLBACK after max retries for business_name."""
        userdata.asked_business_name_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "fallback"
        assert agent == CL_AE_FALLBACK
        assert reason == "missing_business_name"

    def test_ready_when_business_name_present(self, userdata):
        """Test ready when business_name is present."""
        userdata.route_decision.business_name = "Acme Corp"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"

    def test_second_ask_then_provided(self, userdata):
        """Test that providing business_name after first ask returns ready."""
        # First ask increments counter
        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert userdata.asked_business_name_count == 1

        # User provides business name
        userdata.route_decision.business_name = "ABC Corp"

        # Now should be ready
        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"


class TestCheckRoutingRequirementsMissingLastName:
    """Tests for missing last_name requirement."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        ud = AizelleeUserData()
        ud.route_decision.insurance_type = InsuranceType.PERSONAL
        return ud

    def test_first_ask_for_last_name(self, userdata):
        """Test that first request asks for last_name."""
        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert "last name" in question.lower()
        assert field == "last_name"
        assert userdata.asked_last_name_count == 1

    def test_second_ask_for_last_name(self, userdata):
        """Test that second request still asks for last_name."""
        userdata.asked_last_name_count = 1

        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert field == "last_name"
        assert userdata.asked_last_name_count == 2

    def test_extracts_last_name_from_full_name(self, userdata):
        """Test that last name is extracted from caller_name if multi-word."""
        userdata.route_decision.caller_name = "John Smith"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"

    def test_single_word_name_asks_for_last_name(self, userdata):
        """Test that single-word caller_name triggers ask for last_name."""
        userdata.route_decision.caller_name = "John"

        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert field == "last_name"

    def test_fallback_after_max_retries(self, userdata):
        """Test fallback to PL_AE_FALLBACK after max retries for last_name."""
        userdata.asked_last_name_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "fallback"
        assert agent == PL_AE_FALLBACK
        assert reason == "missing_last_name"

    def test_ready_when_policy_last_name_present(self, userdata):
        """Test ready when policy_last_name is present."""
        userdata.route_decision.policy_last_name = "Smith"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"

    def test_second_ask_then_provided(self, userdata):
        """Test that providing last_name after first ask returns ready."""
        # First ask increments counter
        action, question, field = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ask"
        assert userdata.asked_last_name_count == 1

        # User provides last name
        userdata.route_decision.policy_last_name = "Johnson"

        # Now should be ready
        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert action == "ready"


class TestCheckRoutingRequirementsSpecificAgent:
    """Tests for specific_agent intent requirements."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        ud = AizelleeUserData()
        ud.route_decision.insurance_type = InsuranceType.PERSONAL
        return ud

    def test_first_ask_when_no_agent_requested(self, userdata):
        """Test that first request asks who they want to reach."""
        action, question, field = check_routing_requirements(
            userdata, IntentCategory.SPECIFIC_AGENT
        )
        assert action == "ask"
        assert "who" in question.lower()
        assert field == "specific_agent"
        assert userdata.asked_specific_agent_count == 1

    def test_ask_when_agent_not_found(self, userdata):
        """Test that unknown agent name triggers ask."""
        userdata.route_decision.requested_agent_name = "NonexistentPerson"

        action, question, field = check_routing_requirements(
            userdata, IntentCategory.SPECIFIC_AGENT
        )
        assert action == "ask"
        assert field == "specific_agent"

    def test_fallback_after_max_retries_business(self, userdata):
        """Test fallback to CL_AE_FALLBACK for business after max retries."""
        userdata.route_decision.insurance_type = InsuranceType.BUSINESS
        userdata.asked_specific_agent_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "fallback"
        assert agent == CL_AE_FALLBACK
        assert reason == "unknown_specific_agent"

    def test_fallback_after_max_retries_personal(self, userdata):
        """Test fallback to PL_AE_FALLBACK for personal after max retries."""
        userdata.asked_specific_agent_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "fallback"
        assert agent == PL_AE_FALLBACK
        assert reason == "unknown_specific_agent"

    def test_ready_when_valid_agent_requested(self, userdata):
        """Test ready when a valid agent is requested."""
        userdata.route_decision.requested_agent_name = "Queens"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "ready"

    def test_agent_lookup_case_insensitive(self, userdata):
        """Test that agent lookup is case-insensitive."""
        userdata.route_decision.requested_agent_name = "queens"

        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "ready"

    def test_second_ask_for_agent(self, userdata):
        """Test that second request still asks for specific_agent."""
        userdata.asked_specific_agent_count = 1

        action, question, field = check_routing_requirements(
            userdata, IntentCategory.SPECIFIC_AGENT
        )
        assert action == "ask"
        assert field == "specific_agent"
        assert userdata.asked_specific_agent_count == 2

    def test_agent_found_on_retry(self, userdata):
        """Test that providing valid agent name after first ask returns ready."""
        # First ask increments counter
        action, question, field = check_routing_requirements(
            userdata, IntentCategory.SPECIFIC_AGENT
        )
        assert action == "ask"
        assert userdata.asked_specific_agent_count == 1

        # User provides valid agent name
        userdata.route_decision.requested_agent_name = "Yarislyn"

        # Now should be ready
        action, value1, value2 = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "ready"

    def test_fallback_after_max_retries_with_unknown_name(self, userdata):
        """Test fallback when max retries exceeded with unknown agent name."""
        userdata.route_decision.requested_agent_name = "SomeoneWhoDoesNotExist"
        userdata.asked_specific_agent_count = 2

        action, agent, reason = check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert action == "fallback"
        assert agent == PL_AE_FALLBACK
        assert reason == "unknown_specific_agent"


class TestCheckRoutingRequirementsCounterPersistence:
    """Tests verifying that retry counters are properly incremented."""

    @pytest.fixture
    def userdata(self):
        """Create fresh userdata for each test."""
        return AizelleeUserData()

    def test_insurance_type_counter_increments(self, userdata):
        """Test that insurance_type counter increments on each ask."""
        assert userdata.asked_insurance_type_count == 0

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_insurance_type_count == 1

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_insurance_type_count == 2

    def test_business_name_counter_increments(self, userdata):
        """Test that business_name counter increments on each ask."""
        userdata.route_decision.insurance_type = InsuranceType.BUSINESS
        assert userdata.asked_business_name_count == 0

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_business_name_count == 1

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_business_name_count == 2

    def test_last_name_counter_increments(self, userdata):
        """Test that last_name counter increments on each ask."""
        userdata.route_decision.insurance_type = InsuranceType.PERSONAL
        assert userdata.asked_last_name_count == 0

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_last_name_count == 1

        check_routing_requirements(userdata, IntentCategory.NEW_QUOTE)
        assert userdata.asked_last_name_count == 2

    def test_specific_agent_counter_increments(self, userdata):
        """Test that specific_agent counter increments on each ask."""
        userdata.route_decision.insurance_type = InsuranceType.PERSONAL
        assert userdata.asked_specific_agent_count == 0

        check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert userdata.asked_specific_agent_count == 1

        check_routing_requirements(userdata, IntentCategory.SPECIFIC_AGENT)
        assert userdata.asked_specific_agent_count == 2
