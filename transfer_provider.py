"""
Transfer Provider Abstraction for Phase 2.4.

This module provides an abstraction layer for call transfer operations,
enabling easy switching between mock, RingCentral, and SIP providers.

Usage:
    from transfer_provider import get_transfer_provider

    provider = get_transfer_provider()
    result = await provider.transfer(
        target_name="John Smith",
        target_extension="123",
        reason="New quote request",
        caller_info={"name": "Jane Doe", "phone": "5551234567"}
    )
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("aizellee.transfer")


@dataclass
class TransferResult:
    """Result of a transfer operation."""

    status: Literal["success", "failure"]
    provider: str  # e.g., "mock", "ringcentral", "sip"
    message: str


class TransferProvider(ABC):
    """Abstract base class for transfer providers."""

    @abstractmethod
    async def transfer(
        self,
        target_name: str,
        target_extension: str,
        reason: str,
        caller_info: dict,
    ) -> TransferResult:
        """
        Transfer the call to a target agent.

        Args:
            target_name: Name of the staff member to transfer to.
            target_extension: Extension number to dial.
            reason: Brief explanation of why transferring.
            caller_info: Dictionary with caller details (name, phone, etc.)

        Returns:
            TransferResult with status, provider name, and message.
        """
        pass


class MockTransferProvider(TransferProvider):
    """
    Mock transfer provider for development and testing.

    Logs all transfer attempts with full details.
    Can be configured to simulate failures via TRANSFER_MOCK_FAIL env var.
    """

    def __init__(self) -> None:
        self._fail_mode = os.getenv("TRANSFER_MOCK_FAIL", "").lower() in ("true", "1", "yes")
        if self._fail_mode:
            logger.info("MockTransferProvider initialized in FAIL mode")
        else:
            logger.info("MockTransferProvider initialized in SUCCESS mode")

    async def transfer(
        self,
        target_name: str,
        target_extension: str,
        reason: str,
        caller_info: dict,
    ) -> TransferResult:
        """
        Mock transfer operation.

        Logs the transfer attempt and returns success/failure based on
        the TRANSFER_MOCK_FAIL environment variable.

        Args:
            target_name: Name of the staff member to transfer to.
            target_extension: Extension number to dial.
            reason: Brief explanation of why transferring.
            caller_info: Dictionary with caller details.

        Returns:
            TransferResult with status based on TRANSFER_MOCK_FAIL env var.
        """
        # Log full transfer details
        logger.info(
            f"MOCK_TRANSFER: target={target_name} | ext={target_extension} | "
            f"reason={reason} | caller_info={caller_info}"
        )

        if self._fail_mode:
            logger.warning("MOCK_TRANSFER: Simulating failure (TRANSFER_MOCK_FAIL=true)")
            return TransferResult(
                status="failure",
                provider="mock",
                message="Simulated transfer failure (TRANSFER_MOCK_FAIL=true)",
            )

        logger.info("MOCK_TRANSFER: Simulating success")
        return TransferResult(
            status="success",
            provider="mock",
            message=f"Mock transfer to {target_name} (ext {target_extension}) succeeded",
        )


# Singleton instance for the current provider
_transfer_provider: TransferProvider | None = None


def get_transfer_provider() -> TransferProvider:
    """
    Factory function to get the configured transfer provider.

    Currently returns MockTransferProvider. Future implementations will
    check environment variables to select RingCentral or SIP providers.

    Returns:
        The configured TransferProvider instance.
    """
    global _transfer_provider
    if _transfer_provider is None:
        # TODO: Add provider selection based on env vars (e.g., TRANSFER_PROVIDER)
        # For now, always use mock provider
        _transfer_provider = MockTransferProvider()
    return _transfer_provider


def reset_transfer_provider() -> None:
    """
    Reset the transfer provider singleton.

    Useful for testing to ensure a fresh provider instance.
    """
    global _transfer_provider
    _transfer_provider = None
