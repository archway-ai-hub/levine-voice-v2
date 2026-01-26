"""
Unit tests for the transfer_provider module (Phase 2.4).

Tests cover:
1. TransferResult dataclass - creation with success/failure status
2. MockTransferProvider - success/failure modes based on TRANSFER_MOCK_FAIL env var
3. get_transfer_provider factory - singleton behavior
4. reset_transfer_provider - singleton reset for test isolation

Test Categories:
1. TransferResult Dataclass Tests
2. MockTransferProvider Success Mode Tests
3. MockTransferProvider Failure Mode Tests
4. Provider Factory Tests
5. Singleton Reset Tests
"""

import pytest

from transfer_provider import (
    MockTransferProvider,
    TransferResult,
    get_transfer_provider,
    reset_transfer_provider,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_provider_singleton():
    """Reset the provider singleton before and after each test."""
    reset_transfer_provider()
    yield
    reset_transfer_provider()


@pytest.fixture
def sample_caller_info():
    """Sample caller info for transfer tests."""
    return {
        "name": "Jane Doe",
        "phone": "5551234567",
        "insurance_type": "personal",
    }


# =============================================================================
# 1. TransferResult Dataclass Tests
# =============================================================================


class TestTransferResult:
    """Tests for TransferResult dataclass."""

    def test_create_with_success_status(self):
        """Test creating a TransferResult with success status."""
        result = TransferResult(
            status="success",
            provider="mock",
            message="Transfer completed successfully",
        )

        assert result.status == "success"
        assert result.provider == "mock"
        assert result.message == "Transfer completed successfully"

    def test_create_with_failure_status(self):
        """Test creating a TransferResult with failure status."""
        result = TransferResult(
            status="failure",
            provider="ringcentral",
            message="Connection timeout",
        )

        assert result.status == "failure"
        assert result.provider == "ringcentral"
        assert result.message == "Connection timeout"

    def test_contains_correct_fields(self):
        """Test that TransferResult has all expected fields."""
        result = TransferResult(
            status="success",
            provider="sip",
            message="Test message",
        )

        assert hasattr(result, "status")
        assert hasattr(result, "provider")
        assert hasattr(result, "message")

    def test_status_is_literal_type(self):
        """Test that status accepts only valid literal values."""
        # These should work
        result_success = TransferResult(status="success", provider="mock", message="ok")
        result_failure = TransferResult(status="failure", provider="mock", message="fail")

        assert result_success.status == "success"
        assert result_failure.status == "failure"


# =============================================================================
# 2. MockTransferProvider Success Mode Tests (Default)
# =============================================================================


class TestMockTransferProviderSuccessMode:
    """Tests for MockTransferProvider in default success mode."""

    @pytest.mark.asyncio
    async def test_returns_success_by_default(self, sample_caller_info):
        """Test that MockTransferProvider returns success by default (no env var)."""
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Queens",
            target_extension="7010",
            reason="New quote request",
            caller_info=sample_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"
        assert "Queens" in result.message
        assert "7010" in result.message

    @pytest.mark.asyncio
    async def test_returns_success_when_env_var_false(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns success when TRANSFER_MOCK_FAIL=false."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "false")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Al",
            target_extension="7015",
            reason="Policy change",
            caller_info=sample_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_success_when_env_var_empty(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns success when TRANSFER_MOCK_FAIL is empty."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Yarislyn",
            target_extension="7014",
            reason="Coverage question",
            caller_info=sample_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_success_when_env_var_no(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns success when TRANSFER_MOCK_FAIL=no."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "no")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Luis",
            target_extension="7016",
            reason="Annual review",
            caller_info=sample_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_logs_transfer_attempt(self, caplog, sample_caller_info):
        """Test that MockTransferProvider logs transfer attempts."""
        import logging

        # Capture logs from the specific logger used by transfer_provider
        with caplog.at_level(logging.INFO, logger="aizellee.transfer"):
            provider = MockTransferProvider()

            await provider.transfer(
                target_name="Brad",
                target_extension="7011",
                reason="New quote M-Z",
                caller_info=sample_caller_info,
            )

        # Check that transfer was logged
        assert "MOCK_TRANSFER" in caplog.text
        assert "Brad" in caplog.text
        assert "7011" in caplog.text
        assert "New quote M-Z" in caplog.text


# =============================================================================
# 3. MockTransferProvider Failure Mode Tests
# =============================================================================


class TestMockTransferProviderFailureMode:
    """Tests for MockTransferProvider in failure mode (TRANSFER_MOCK_FAIL=true)."""

    @pytest.mark.asyncio
    async def test_returns_failure_when_env_var_true(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns failure when TRANSFER_MOCK_FAIL=true."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "true")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Queens",
            target_extension="7010",
            reason="New quote request",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"
        assert "Simulated transfer failure" in result.message

    @pytest.mark.asyncio
    async def test_returns_failure_when_env_var_1(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns failure when TRANSFER_MOCK_FAIL=1."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "1")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Adriana",
            target_extension="7002",
            reason="Business quote",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_failure_when_env_var_yes(self, monkeypatch, sample_caller_info):
        """Test that MockTransferProvider returns failure when TRANSFER_MOCK_FAIL=yes."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "yes")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Rayvon",
            target_extension="7003",
            reason="Policy change",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_failure_case_insensitive_true(self, monkeypatch, sample_caller_info):
        """Test that TRANSFER_MOCK_FAIL is case-insensitive for 'TRUE'."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "TRUE")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Dionna",
            target_extension="7004",
            reason="Claims",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_failure_case_insensitive_yes(self, monkeypatch, sample_caller_info):
        """Test that TRANSFER_MOCK_FAIL is case-insensitive for 'YES'."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "YES")
        provider = MockTransferProvider()

        result = await provider.transfer(
            target_name="Luis",
            target_extension="7016",
            reason="Something else",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_logs_failure_warning(self, monkeypatch, caplog, sample_caller_info):
        """Test that MockTransferProvider logs failure warning in fail mode."""
        import logging

        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "true")

        # Capture logs from the specific logger used by transfer_provider
        with caplog.at_level(logging.WARNING, logger="aizellee.transfer"):
            provider = MockTransferProvider()

            await provider.transfer(
                target_name="Al",
                target_extension="7015",
                reason="Test failure",
                caller_info=sample_caller_info,
            )

        # Check that failure warning was logged
        assert "Simulating failure" in caplog.text
        assert "TRANSFER_MOCK_FAIL=true" in caplog.text


# =============================================================================
# 4. Provider Factory Tests (get_transfer_provider)
# =============================================================================


class TestGetTransferProvider:
    """Tests for get_transfer_provider factory function."""

    def test_returns_mock_transfer_provider_instance(self):
        """Test that get_transfer_provider returns a MockTransferProvider instance."""
        provider = get_transfer_provider()

        assert isinstance(provider, MockTransferProvider)

    def test_returns_same_instance_on_multiple_calls(self):
        """Test that get_transfer_provider returns the same singleton instance."""
        provider1 = get_transfer_provider()
        provider2 = get_transfer_provider()
        provider3 = get_transfer_provider()

        assert provider1 is provider2
        assert provider2 is provider3

    @pytest.mark.asyncio
    async def test_singleton_maintains_state(self, sample_caller_info):
        """Test that singleton maintains its state across calls."""
        provider1 = get_transfer_provider()
        provider2 = get_transfer_provider()

        # Both should reference the same provider
        result1 = await provider1.transfer(
            target_name="Queens",
            target_extension="7010",
            reason="Test",
            caller_info=sample_caller_info,
        )
        result2 = await provider2.transfer(
            target_name="Brad",
            target_extension="7011",
            reason="Test",
            caller_info=sample_caller_info,
        )

        # Both should succeed (same provider instance)
        assert result1.status == "success"
        assert result2.status == "success"


# =============================================================================
# 5. Singleton Reset Tests (reset_transfer_provider)
# =============================================================================


class TestResetTransferProvider:
    """Tests for reset_transfer_provider function."""

    def test_resets_the_singleton(self):
        """Test that reset_transfer_provider resets the singleton."""
        provider1 = get_transfer_provider()
        reset_transfer_provider()
        provider2 = get_transfer_provider()

        # Should be different instances after reset
        assert provider1 is not provider2

    def test_reset_allows_new_env_var_to_take_effect(self, monkeypatch, sample_caller_info):
        """Test that resetting allows new env var to take effect."""
        # First get provider in success mode
        provider1 = get_transfer_provider()
        assert provider1._fail_mode is False

        # Reset and set env var for failure
        reset_transfer_provider()
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "true")

        # New provider should be in fail mode
        provider2 = get_transfer_provider()
        assert provider2._fail_mode is True

    def test_multiple_resets_are_safe(self):
        """Test that calling reset_transfer_provider multiple times is safe."""
        # This should not raise any errors
        reset_transfer_provider()
        reset_transfer_provider()
        reset_transfer_provider()

        # Should still work after multiple resets
        provider = get_transfer_provider()
        assert isinstance(provider, MockTransferProvider)

    def test_reset_before_any_get_is_safe(self):
        """Test that calling reset before get_transfer_provider is safe."""
        # Reset before any provider is created
        reset_transfer_provider()

        # Should work fine
        provider = get_transfer_provider()
        assert isinstance(provider, MockTransferProvider)


# =============================================================================
# 6. Integration Tests
# =============================================================================


class TestTransferProviderIntegration:
    """Integration tests for the transfer provider module."""

    @pytest.mark.asyncio
    async def test_full_transfer_workflow_success(self, sample_caller_info):
        """Test complete transfer workflow in success mode."""
        provider = get_transfer_provider()

        result = await provider.transfer(
            target_name="Queens",
            target_extension="7010",
            reason="New personal lines quote for A-L last name",
            caller_info=sample_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"
        assert "Queens" in result.message
        assert "7010" in result.message

    @pytest.mark.asyncio
    async def test_full_transfer_workflow_failure(self, monkeypatch, sample_caller_info):
        """Test complete transfer workflow in failure mode."""
        monkeypatch.setenv("TRANSFER_MOCK_FAIL", "true")
        reset_transfer_provider()  # Reset to pick up new env var

        provider = get_transfer_provider()

        result = await provider.transfer(
            target_name="Adriana",
            target_extension="7002",
            reason="New business quote",
            caller_info=sample_caller_info,
        )

        assert result.status == "failure"
        assert result.provider == "mock"
        assert "Simulated transfer failure" in result.message

    @pytest.mark.asyncio
    async def test_transfer_with_minimal_caller_info(self):
        """Test transfer with minimal caller info."""
        provider = get_transfer_provider()

        result = await provider.transfer(
            target_name="Al",
            target_extension="7015",
            reason="Unknown reason",
            caller_info={},  # Empty caller info
        )

        assert result.status == "success"
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_transfer_with_complete_caller_info(self):
        """Test transfer with complete caller info."""
        provider = get_transfer_provider()

        complete_caller_info = {
            "name": "John Smith",
            "phone": "5559876543",
            "insurance_type": "personal",
            "last_name": "Smith",
            "intent": "new_quote",
            "callback_phone": "5559876543",
        }

        result = await provider.transfer(
            target_name="Brad",
            target_extension="7011",
            reason="New personal lines quote for M-Z last name",
            caller_info=complete_caller_info,
        )

        assert result.status == "success"
        assert result.provider == "mock"


# =============================================================================
# 7. Transfer Flow Integration Tests (transfer_to_agent function tool)
# =============================================================================


class TestTransferFlowIntegration:
    """
    Integration tests for the complete transfer flow.

    Tests that:
    1. On READY_TRANSFER directive, provider.transfer() is called exactly once
    2. TRANSFER_ATTEMPT and TRANSFER_RESULT logs are emitted
    3. RouteDecision has target fields populated (SSOT)
    """

    @pytest.fixture
    def mock_context(self):
        """Create a mock RunContext with AizelleeUserData."""
        from unittest.mock import MagicMock

        from models import AizelleeUserData, InsuranceType, IntentCategory

        # Set up userdata with populated RouteDecision (simulating SSOT)
        userdata = AizelleeUserData()
        userdata.route_decision.intent = IntentCategory.NEW_QUOTE
        userdata.route_decision.insurance_type = InsuranceType.PERSONAL
        userdata.route_decision.caller_name = "John Smith"
        userdata.route_decision.callback_phone = "5551234567"
        userdata.route_decision.policy_last_name = "Smith"
        # SSOT target fields (populated by get_ssot_directive)
        userdata.route_decision.target_agent_name = "Queens"
        userdata.route_decision.target_extension = "7010"
        userdata.route_decision.target_department = "PL Sales"
        userdata.route_decision.transfer_reason = "New personal lines quote"

        ctx = MagicMock()
        ctx.userdata = userdata
        return ctx

    @pytest.mark.asyncio
    async def test_transfer_to_agent_calls_provider_exactly_once(self, mock_context, caplog):
        """Test that transfer_to_agent calls provider.transfer() exactly once."""
        import logging
        from unittest.mock import AsyncMock, patch

        from agent import AizelleeAgent

        # Create agent instance
        agent = AizelleeAgent()

        # Create a spy on the transfer provider
        with patch("agent.get_transfer_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.transfer = AsyncMock(
                return_value=TransferResult(
                    status="success",
                    provider="mock",
                    message="Mock transfer succeeded",
                )
            )
            mock_get_provider.return_value = mock_provider

            with caplog.at_level(logging.INFO, logger="aizellee"):
                # Call transfer_to_agent directly
                await agent.transfer_to_agent(
                    mock_context,
                    target_name="Queens",
                    target_extension="7010",
                    reason="New personal lines quote",
                )

            # Assert provider.transfer() was called exactly once
            assert mock_provider.transfer.call_count == 1

            # Verify the call arguments
            call_kwargs = mock_provider.transfer.call_args.kwargs
            assert call_kwargs["target_name"] == "Queens"
            assert call_kwargs["target_extension"] == "7010"
            assert call_kwargs["reason"] == "New personal lines quote"
            assert call_kwargs["caller_info"]["name"] == "John Smith"
            assert call_kwargs["caller_info"]["phone"] == "5551234567"

    @pytest.mark.asyncio
    async def test_transfer_to_agent_emits_transfer_attempt_log(self, mock_context, caplog):
        """Test that TRANSFER_ATTEMPT log is emitted."""
        import logging
        from unittest.mock import AsyncMock, patch

        from agent import AizelleeAgent

        agent = AizelleeAgent()

        with patch("agent.get_transfer_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.transfer = AsyncMock(
                return_value=TransferResult(
                    status="success",
                    provider="mock",
                    message="Mock transfer succeeded",
                )
            )
            mock_provider.__class__.__name__ = "MockTransferProvider"
            mock_get_provider.return_value = mock_provider

            with caplog.at_level(logging.INFO, logger="aizellee"):
                await agent.transfer_to_agent(
                    mock_context,
                    target_name="Queens",
                    target_extension="7010",
                    reason="New personal lines quote",
                )

            # Assert TRANSFER_ATTEMPT log was emitted
            assert "TRANSFER_ATTEMPT" in caplog.text
            assert "Queens" in caplog.text
            assert "7010" in caplog.text

    @pytest.mark.asyncio
    async def test_transfer_to_agent_emits_transfer_result_log(self, mock_context, caplog):
        """Test that TRANSFER_RESULT log is emitted on success."""
        import logging
        from unittest.mock import AsyncMock, patch

        from agent import AizelleeAgent

        agent = AizelleeAgent()

        with patch("agent.get_transfer_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.transfer = AsyncMock(
                return_value=TransferResult(
                    status="success",
                    provider="mock",
                    message="Mock transfer succeeded",
                )
            )
            mock_get_provider.return_value = mock_provider

            with caplog.at_level(logging.INFO, logger="aizellee"):
                await agent.transfer_to_agent(
                    mock_context,
                    target_name="Queens",
                    target_extension="7010",
                    reason="New personal lines quote",
                )

            # Assert TRANSFER_RESULT log was emitted
            assert "TRANSFER_RESULT" in caplog.text
            assert "success" in caplog.text

    @pytest.mark.asyncio
    async def test_route_decision_has_target_fields_populated(self, mock_context):
        """Test that RouteDecision has target fields populated (SSOT)."""
        from unittest.mock import AsyncMock, patch

        from agent import AizelleeAgent

        agent = AizelleeAgent()

        with patch("agent.get_transfer_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.transfer = AsyncMock(
                return_value=TransferResult(
                    status="success",
                    provider="mock",
                    message="Mock transfer succeeded",
                )
            )
            mock_get_provider.return_value = mock_provider

            await agent.transfer_to_agent(
                mock_context,
                target_name="Queens",
                target_extension="7010",
                reason="New personal lines quote",
            )

        # Assert RouteDecision target fields are populated (SSOT)
        route_decision = mock_context.userdata.route_decision
        assert route_decision.target_agent_name == "Queens"
        assert route_decision.target_extension == "7010"
        assert route_decision.target_department == "PL Sales"
        assert route_decision.transfer_reason == "New personal lines quote"

    @pytest.mark.asyncio
    async def test_transfer_uses_ssot_values_over_llm_values(self, mock_context, caplog):
        """Test that SSOT values are used even if LLM provides different values."""
        import logging
        from unittest.mock import AsyncMock, patch

        from agent import AizelleeAgent

        agent = AizelleeAgent()

        with patch("agent.get_transfer_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.transfer = AsyncMock(
                return_value=TransferResult(
                    status="success",
                    provider="mock",
                    message="Mock transfer succeeded",
                )
            )
            mock_get_provider.return_value = mock_provider

            with caplog.at_level(logging.WARNING, logger="aizellee"):
                # LLM provides different values than SSOT
                await agent.transfer_to_agent(
                    mock_context,
                    target_name="Brad",  # LLM hallucinated different name
                    target_extension="7011",  # LLM hallucinated different ext
                    reason="Some other reason",
                )

            # Assert provider was called with SSOT values, not LLM values
            call_kwargs = mock_provider.transfer.call_args.kwargs
            assert call_kwargs["target_name"] == "Queens"  # SSOT value
            assert call_kwargs["target_extension"] == "7010"  # SSOT value

            # Assert mismatch warning was logged
            assert "LLM transfer mismatch" in caplog.text
